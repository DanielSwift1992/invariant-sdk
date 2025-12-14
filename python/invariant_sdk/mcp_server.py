"""
Invariant MCP Server — Semantic Kernel for LLM Agents

This is the MCP (Model Context Protocol) interface to the Invariant SDK.
It exposes semantic tools that let LLMs understand code/documents without
reading every file — they get the "semantic skeleton" instead.

Usage:
    python -m invariant_sdk.mcp_server

For Claude Desktop / Cursor, add to config:
    {
        "mcpServers": {
            "invariant": {
                "command": "python",
                "args": ["-m", "invariant_sdk.mcp_server"],
                "cwd": "/path/to/your/project"
            }
        }
    }

Theory:
    See INVARIANTS.md for the physics behind this.
    - σ-facts = grounded in documents (provable)
    - α-facts = global crystal (axioms)
    - ctx_hash = semantic checksum for drift detection
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("invariant")

# Globals (initialized on first use)
_physics = None
_overlay = None
_overlay_path = None


def _ensure_initialized():
    """Lazy initialization of physics and overlay."""
    global _physics, _overlay, _overlay_path
    
    if _physics is not None:
        return
    
    from invariant_sdk.physics import HaloPhysics
    from invariant_sdk.overlay import OverlayGraph
    
    # Connect to crystal server
    server_url = os.environ.get("INVARIANT_SERVER", "http://165.22.145.158:8080")
    _physics = HaloPhysics(server_url)
    
    # Load overlay if exists
    overlay_candidates = [
        Path("./.invariant/overlay.jsonl"),
        Path("./overlay.jsonl"),
    ]
    for candidate in overlay_candidates:
        if candidate.exists():
            _overlay = OverlayGraph.load(candidate)
            _overlay_path = candidate
            break
    
    if _overlay is None:
        _overlay = OverlayGraph()
        _overlay_path = Path("./.invariant/overlay.jsonl")


# ============================================================================
# TOOLS — Actions that LLM can take
# ============================================================================

@mcp.tool()
def status() -> str:
    """
    Get Invariant status: crystal connection, overlay stats, project info.
    
    Use this first to check if Invariant is ready and what's indexed.
    """
    _ensure_initialized()
    
    info = {
        "crystal_id": _physics.crystal_id if _physics else "Not connected",
        "mean_mass": round(_physics.mean_mass, 4) if _physics else 0,
        "overlay_path": str(_overlay_path) if _overlay_path else None,
        "overlay_edges": _overlay.n_edges if _overlay else 0,
        "overlay_labels": len(_overlay.labels) if _overlay else 0,
        "overlay_docs": len(_overlay.sources) if _overlay else 0,
    }
    return json.dumps(info, indent=2)


@mcp.tool()
def locate(issue_text: str, max_results: int = 5) -> str:
    """
    FIND: Locate relevant files from problem description (issue, traceback, error).
    
    This is the Bisection Maximizer — collapses 1000 files to ~5 candidates
    using Interference (A ∩ B) on seed terms.
    
    Physics: Each word in issue_text is a "seed". Files that contain
    intersections of multiple seeds are ranked higher.
    
    Args:
        issue_text: Bug report, error message, or problem description
        max_results: Maximum files to return (default 5)
    
    Returns:
        JSON with ranked files: path, score, matching concepts, provenance
    """
    _ensure_initialized()
    
    import re
    import math
    from invariant_sdk.cli import hash8_hex
    
    # Extract seed terms from issue text
    # Prefer: class names (CamelCase), function names, module paths
    # Filter: stopwords, short words
    
    seeds = []
    
    # CamelCase (likely class names): SomethingError, MyClass
    for m in re.finditer(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', issue_text):
        seeds.append(m.group().lower())
    
    # snake_case (likely function/method names): some_function
    for m in re.finditer(r'\b[a-z]+(?:_[a-z]+)+\b', issue_text):
        seeds.append(m.group())
    
    # Module paths: foo.bar.baz
    for m in re.finditer(r'\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+\b', issue_text):
        parts = m.group().split('.')
        seeds.extend(parts)
    
    # Regular words (3+ chars, not stopwords)
    stopwords = {'the', 'and', 'for', 'are', 'was', 'were', 'been', 'being', 
                 'have', 'has', 'had', 'does', 'did', 'will', 'would', 'could',
                 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
                 'this', 'that', 'these', 'those', 'with', 'from', 'into',
                 'during', 'before', 'after', 'above', 'below', 'between',
                 'but', 'not', 'only', 'same', 'than', 'too', 'very'}
    
    for m in re.finditer(r'\b[a-zA-Z]{4,}\b', issue_text):
        word = m.group().lower()
        if word not in stopwords:
            seeds.append(word)
    
    # Deduplicate, keep order
    seen = set()
    unique_seeds = []
    for s in seeds:
        if s not in seen:
            seen.add(s)
            unique_seeds.append(s)
    
    if not unique_seeds:
        return json.dumps({"error": "No searchable terms found in issue_text"})
    
    # Hash seeds
    seed_hashes = {s: hash8_hex(f"Ġ{s}") for s in unique_seeds[:30]}  # Limit seeds
    
    # Classify seeds by mass (solid vs gas)
    solid_seeds = []
    gas_seeds = []
    
    try:
        batch_results = _physics._client.get_halo_pages(seed_hashes.values(), limit=0)
        for seed, h8 in seed_hashes.items():
            result = batch_results.get(h8) or {}
            if result.get('exists'):
                meta = result.get('meta') or {}
                degree = int(meta.get('degree_total') or 0)
                mass = 1.0 / math.log(2 + max(0, degree)) if degree > 0 else 0
                if mass > _physics.mean_mass:
                    solid_seeds.append((seed, h8, mass))
                else:
                    gas_seeds.append((seed, h8, mass))
    except Exception:
        # Fallback: treat all as solid
        solid_seeds = [(s, h, 0.5) for s, h in seed_hashes.items()]
    
    # Interference: find files containing multiple seeds
    # Score = number of distinct solid seeds found
    file_scores = {}  # doc -> {score, seeds, lines}
    
    for src, edges in _overlay.edges.items():
        src_label = _overlay.get_label(src) or ""
        for edge in edges:
            if not edge.doc:
                continue
            tgt_label = _overlay.get_label(edge.tgt) or ""
            
            # Check which seeds match
            matched_seeds = []
            for seed, h8, mass in solid_seeds:
                if seed == src_label.lower() or seed == tgt_label.lower():
                    matched_seeds.append(seed)
                elif src == h8 or edge.tgt == h8:
                    matched_seeds.append(seed)
            
            if matched_seeds:
                if edge.doc not in file_scores:
                    file_scores[edge.doc] = {"score": 0, "seeds": set(), "lines": []}
                file_scores[edge.doc]["seeds"].update(matched_seeds)
                if edge.line and edge.line not in file_scores[edge.doc]["lines"]:
                    file_scores[edge.doc]["lines"].append(edge.line)
    
    # Calculate interference score: more seeds = exponentially better
    # This is the Bisection Law: 2^n where n = number of matching seeds
    for doc in file_scores:
        n_seeds = len(file_scores[doc]["seeds"])
        file_scores[doc]["score"] = 2 ** n_seeds
        file_scores[doc]["seeds"] = list(file_scores[doc]["seeds"])
        file_scores[doc]["lines"] = sorted(file_scores[doc]["lines"])[:10]
    
    # Rank results
    ranked = sorted(file_scores.items(), key=lambda x: x[1]["score"], reverse=True)
    
    results = []
    for doc, info in ranked[:max_results]:
        results.append({
            "file": doc,
            "score": info["score"],
            "matching_seeds": info["seeds"],
            "n_matches": len(info["seeds"]),
            "candidate_lines": info["lines"],
        })
    
    return json.dumps({
        "query_seeds": unique_seeds[:10],
        "solid_seeds": len(solid_seeds),
        "gas_seeds": len(gas_seeds),
        "files_found": len(results),
        "results": results,
    }, indent=2)


@mcp.tool()
def semantic_map(file_path: str) -> str:
    """
    UNDERSTAND: Get semantic skeleton of a file — structure, not content.
    
    For Python: returns classes, functions, imports, signatures.
    For all files: returns overlay edges and key concepts.
    
    This is 10-100x cheaper than reading the whole file.
    
    Args:
        file_path: Path to the file (relative or absolute)
    
    Returns:
        JSON with:
        - ast_skeleton (Python only): classes, functions, imports
        - anchors: key concepts with mass/phase
        - edges: connections in reading order
    """
    _ensure_initialized()
    
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    
    result = {
        "file": file_path,
        "type": path.suffix,
    }
    
    # AST skeleton for Python files
    if path.suffix == '.py':
        try:
            import ast
            source = path.read_text(encoding='utf-8')
            tree = ast.parse(source)
            
            skeleton = {
                "imports": [],
                "classes": [],
                "functions": [],
            }
            
            for node in ast.walk(tree):
                # Imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        skeleton["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        skeleton["imports"].append(f"{module}.{alias.name}")
                
                # Classes (top-level only)
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            args = [a.arg for a in item.args.args]
                            methods.append({
                                "name": item.name,
                                "args": args,
                                "line": item.lineno,
                            })
                    
                    skeleton["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": methods,
                        "bases": [ast.unparse(b) if hasattr(ast, 'unparse') else 
                                 getattr(b, 'id', str(b)) for b in node.bases],
                    })
                
                # Top-level functions
                elif isinstance(node, ast.FunctionDef) and not isinstance(getattr(node, '_parent', None), ast.ClassDef):
                    # Mark parent for nested check
                    for child in ast.walk(node):
                        if child is not node:
                            child._parent = node
            
            # Collect top-level functions (not methods)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    args = [a.arg for a in node.args.args]
                    skeleton["functions"].append({
                        "name": node.name,
                        "args": args,
                        "line": node.lineno,
                    })
            
            result["ast_skeleton"] = skeleton
            result["lines_total"] = len(source.split('\n'))
            
        except Exception as e:
            result["ast_error"] = str(e)
    
    # Get all edges from this doc in overlay
    doc_name = path.name
    edges_from_doc = []
    nodes_in_doc = set()
    
    for src, edge_list in _overlay.edges.items():
        for edge in edge_list:
            if edge.doc and (edge.doc == doc_name or edge.doc.endswith(f"/{doc_name}")):
                src_label = _overlay.get_label(src) or src[:8]
                tgt_label = _overlay.get_label(edge.tgt) or edge.tgt[:8]
                edges_from_doc.append({
                    "src": src_label,
                    "tgt": tgt_label,
                    "line": edge.line,
                    "ring": edge.ring,
                })
                nodes_in_doc.add(src_label)
                nodes_in_doc.add(tgt_label)
    
    # Sort by line number for reading order
    edges_from_doc.sort(key=lambda e: e.get("line") or 0)
    
    # Get mass info for key concepts
    anchors = []
    if _physics and nodes_in_doc:
        # Collect hashes for batch lookup
        hash_to_label = {}
        for node_label in list(nodes_in_doc)[:20]:
            for h, l in _overlay.labels.items():
                if l == node_label:
                    hash_to_label[h] = node_label
                    break
        
        if hash_to_label:
            try:
                import math
                batch_results = _physics._client.get_halo_pages(hash_to_label.keys(), limit=0)
                for h8, label in hash_to_label.items():
                    res = batch_results.get(h8) or {}
                    if res.get('exists'):
                        meta = res.get('meta') or {}
                        degree_total = int(meta.get('degree_total') or 0)
                        mass = 1.0 / math.log(2 + max(0, degree_total)) if degree_total > 0 else 0
                        phase = "solid" if mass > _physics.mean_mass else "gas"
                        anchors.append({
                            "word": label,
                            "mass": round(mass, 4),
                            "phase": phase,
                        })
            except Exception:
                pass
    
    anchors.sort(key=lambda a: a["mass"], reverse=True)
    
    result["total_edges"] = len(edges_from_doc)
    result["unique_concepts"] = len(nodes_in_doc)
    result["anchors"] = anchors[:10]  # Top 10 heavy concepts
    result["edges"] = edges_from_doc[:30]  # First 30 edges (in order)
    
    return json.dumps(result, indent=2)


@mcp.tool()
def prove_path(source: str, target: str, max_hops: int = 5) -> str:
    """
    Check if there's a proven connection between two concepts.
    
    This is the anti-hallucination tool. Before making claims about
    relationships, verify them here.
    
    Args:
        source: Source concept (word or phrase)
        target: Target concept (word or phrase)
        max_hops: Maximum path length to search (default 5)
    
    Returns:
        JSON with exists (bool), witness path if found, and ring type (σ or λ)
    """
    _ensure_initialized()
    
    from invariant_sdk.cli import hash8_hex
    
    # Hash the concepts
    src_hash = hash8_hex(f"Ġ{source.lower()}")
    tgt_hash = hash8_hex(f"Ġ{target.lower()}")
    
    # BFS for path
    visited = {src_hash}
    queue = [(src_hash, [source])]
    
    for _ in range(max_hops):
        if not queue:
            break
        
        next_queue = []
        for current, path in queue:
            # Check overlay edges
            for edge in _overlay.edges.get(current, []):
                if edge.tgt == tgt_hash:
                    # Found!
                    final_path = path + [_overlay.get_label(edge.tgt) or target]
                    return json.dumps({
                        "exists": True,
                        "ring": edge.ring,
                        "path": final_path,
                        "doc": edge.doc,
                        "line": edge.line,
                        "provenance": f"{edge.doc}:{edge.line}" if edge.doc and edge.line else None,
                    }, indent=2)
                
                if edge.tgt not in visited:
                    visited.add(edge.tgt)
                    label = _overlay.get_label(edge.tgt) or edge.tgt[:8]
                    next_queue.append((edge.tgt, path + [label]))
            
            # Check halo edges (if physics available)
            if _physics:
                try:
                    neighbors = _physics.get_neighbors(current, limit=50)
                    for n in neighbors:
                        n_hash = n.get("hash8")
                        if n_hash == tgt_hash:
                            final_path = path + [_overlay.get_label(n_hash) or target]
                            return json.dumps({
                                "exists": True,
                                "ring": "lambda",  # From halo = ghost edge
                                "path": final_path,
                                "doc": None,
                                "line": None,
                                "provenance": None,
                            }, indent=2)
                        
                        if n_hash and n_hash not in visited:
                            visited.add(n_hash)
                            label = _overlay.get_label(n_hash) or n_hash[:8]
                            next_queue.append((n_hash, path + [label]))
                except Exception:
                    pass
        
        queue = next_queue
    
    return json.dumps({
        "exists": False,
        "ring": None,
        "path": None,
        "message": f"No path found from '{source}' to '{target}' within {max_hops} hops",
    }, indent=2)


@mcp.tool()
def prove_paths_batch(pairs: list) -> str:
    """
    Verify multiple concept connections at once (batch version of prove_path).
    
    More efficient than calling prove_path multiple times.
    
    Args:
        pairs: List of [source, target] pairs to verify, e.g. [["user", "auth"], ["api", "database"]]
    
    Returns:
        JSON with results for each pair: {pair: [src, tgt], exists: bool, ring: str|null}
    """
    _ensure_initialized()
    
    results = []
    for pair in pairs:
        if len(pair) != 2:
            results.append({"pair": pair, "error": "Invalid pair format"})
            continue
        
        src, tgt = pair
        result = json.loads(prove_path(src, tgt, max_hops=4))
        results.append({
            "pair": [src, tgt],
            "exists": result.get("exists", False),
            "ring": result.get("ring"),
            "path": result.get("path"),
            "provenance": result.get("provenance"),
        })
    
    return json.dumps({
        "total": len(results),
        "proven": sum(1 for r in results if r.get("exists")),
        "results": results,
    }, indent=2)


@mcp.tool()
def search_concept(concept: str, limit: int = 20) -> str:
    """
    Find all documents and locations where a concept appears.
    
    Use this to understand where a term is used across the project.
    
    Args:
        concept: Word or phrase to search for
        limit: Maximum results (default 20)
    
    Returns:
        JSON with all occurrences: doc, line, related concepts
    """
    _ensure_initialized()
    
    from invariant_sdk.cli import hash8_hex
    
    concept_hash = hash8_hex(f"Ġ{concept.lower()}")
    occurrences = []
    
    # Find edges where this concept is source or target
    for src, edges in _overlay.edges.items():
        for edge in edges:
            src_label = _overlay.get_label(src) or ""
            tgt_label = _overlay.get_label(edge.tgt) or ""
            
            if concept.lower() in src_label.lower() or concept.lower() in tgt_label.lower():
                occurrences.append({
                    "doc": edge.doc,
                    "line": edge.line,
                    "src": src_label,
                    "tgt": tgt_label,
                    "ring": edge.ring,
                })
            
            if len(occurrences) >= limit:
                break
        if len(occurrences) >= limit:
            break
    
    # Group by document
    by_doc = {}
    for occ in occurrences:
        doc = occ.get("doc") or "unknown"
        if doc not in by_doc:
            by_doc[doc] = []
        by_doc[doc].append(occ)
    
    return json.dumps({
        "concept": concept,
        "total_occurrences": len(occurrences),
        "documents": len(by_doc),
        "by_document": by_doc,
    }, indent=2)


@mcp.tool()
def list_docs() -> str:
    """
    List all indexed documents with their stats.
    
    Use this to see what's in the knowledge base.
    
    Returns:
        JSON with documents: path, edge count, key concepts
    """
    _ensure_initialized()
    
    docs = {}
    for src, edges in _overlay.edges.items():
        for edge in edges:
            doc = edge.doc or "unknown"
            if doc not in docs:
                docs[doc] = {"edges": 0, "concepts": set()}
            docs[doc]["edges"] += 1
            
            src_label = _overlay.get_label(src)
            tgt_label = _overlay.get_label(edge.tgt)
            if src_label:
                docs[doc]["concepts"].add(src_label)
            if tgt_label:
                docs[doc]["concepts"].add(tgt_label)
    
    result = []
    for doc, info in sorted(docs.items(), key=lambda x: x[1]["edges"], reverse=True):
        result.append({
            "doc": doc,
            "edges": info["edges"],
            "concepts": len(info["concepts"]),
            "top_concepts": list(info["concepts"])[:5],
        })
    
    return json.dumps({
        "total_documents": len(result),
        "total_edges": sum(d["edges"] for d in result),
        "documents": result,
    }, indent=2)



@mcp.tool()
def list_conflicts() -> str:
    """
    Get all detected conflicts in the overlay.
    
    Conflicts arise when the same edge (A → B) appears with different
    weights or from different documents. This is critical for legal/compliance.
    
    Returns:
        JSON list of conflicts with sources and details
    """
    _ensure_initialized()
    
    conflicts = []
    for old_edge, new_edge in _overlay.conflicts:
        conflicts.append({
            "old": {
                "doc": old_edge.doc,
                "weight": old_edge.weight,
                "line": old_edge.line,
            },
            "new": {
                "doc": new_edge.doc,
                "weight": new_edge.weight,
                "line": new_edge.line,
            },
            "target": _overlay.get_label(old_edge.tgt) or old_edge.tgt[:8],
        })
    
    return json.dumps({
        "total": len(conflicts),
        "conflicts": conflicts,
    }, indent=2)


@mcp.tool()
def context(doc: str, line: int, ctx_hash: Optional[str] = None) -> str:
    """
    Get semantic context around a specific line in a document.
    
    Uses Anchor Integrity Protocol for self-healing:
    - If ctx_hash matches at line: fresh (exact match)
    - If ctx_hash found nearby: relocated (file changed, we found it)
    - If ctx_hash not found: broken (content deleted/changed significantly)
    
    Args:
        doc: Document path
        line: Line number (1-indexed)
        ctx_hash: Optional semantic checksum for verification
    
    Returns:
        JSON with content, status (fresh/relocated/broken/unchecked), actual_line
    """
    _ensure_initialized()
    import hashlib
    import re
    
    path = _find_doc_path(doc)
    if not path:
        return json.dumps({"error": f"Document not found: {doc}", "status": "broken"})
    
    try:
        text = path.read_text(encoding='utf-8')
        lines = text.split('\n')
        
        if line < 1 or line > len(lines):
            return json.dumps({"error": f"Line {line} out of range", "status": "broken"})
        
        # Tokenize for hash verification
        tokens = []
        for line_num, line_text in enumerate(lines, 1):
            for match in re.finditer(r'\b[a-zA-Z]{3,}\b', line_text):
                tokens.append((match.group().lower(), line_num))
        
        status = "unchecked"
        actual_line = line
        
        if ctx_hash:
            # Verify hash at expected line
            line_hashes = _compute_hashes_at_line(tokens, line)
            if ctx_hash in line_hashes:
                status = "fresh"
            else:
                # Scan ±50 lines for relocated content
                found = None
                for offset in range(1, 51):
                    for check in [line - offset, line + offset]:
                        if 1 <= check <= len(lines):
                            if ctx_hash in _compute_hashes_at_line(tokens, check):
                                found = check
                                break
                    if found:
                        break
                
                if found:
                    status = "relocated"
                    actual_line = found
                else:
                    status = "broken"
        
        # Extract semantic block
        target_idx = actual_line - 1
        start_idx = target_idx
        end_idx = target_idx
        
        # Find block boundaries
        while start_idx > 0 and (target_idx - start_idx) < 5:
            if not lines[start_idx - 1].strip():
                break
            start_idx -= 1
        
        while end_idx < len(lines) - 1 and (end_idx - target_idx) < 5:
            if not lines[end_idx + 1].strip():
                break
            end_idx += 1
        
        block = lines[start_idx:end_idx + 1]
        
        return json.dumps({
            "doc": doc,
            "requested_line": line,
            "actual_line": actual_line,
            "status": status,
            "block_start": start_idx + 1,
            "block_end": end_idx + 1,
            "content": "\n".join(block),
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e), "status": "broken"})


@mcp.tool()
def ingest(file_path: str) -> str:
    """
    Index a file into the local overlay.
    
    This creates σ-facts (grounded observations) from the document.
    Use this when you want to add a new file to the knowledge base.
    
    Args:
        file_path: Path to the file to ingest
    
    Returns:
        JSON with stats: edges added, anchors found, etc.
    """
    _ensure_initialized()
    import hashlib
    import re
    import math
    
    from invariant_sdk.cli import hash8_hex
    
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    
    try:
        text = path.read_text(encoding='utf-8')
    except Exception as e:
        return json.dumps({"error": f"Cannot read file: {e}"})
    
    # Tokenize with positions
    tokens = []
    lines = text.split('\n')
    for line_num, line_text in enumerate(lines, 1):
        for match in re.finditer(r'\b[a-zA-Z]{3,}\b', line_text):
            tokens.append((match.group().lower(), line_num))
    
    words = [w for w, _ in tokens]
    unique_words = list(dict.fromkeys(words))[:500]
    
    if len(unique_words) < 2:
        return json.dumps({"error": "Too few words in document"})
    
    # Find anchors via crystal
    word_to_hash = {w: hash8_hex(f"Ġ{w}") for w in unique_words}
    
    try:
        batch_results = _physics._client.get_halo_pages(word_to_hash.values(), limit=0)
    except Exception as e:
        return json.dumps({"error": f"Crystal server error: {e}"})
    
    mean_mass = _physics.mean_mass
    candidates = []
    for word in unique_words:
        h8 = word_to_hash.get(word)
        if not h8:
            continue
        result = batch_results.get(h8) or {}
        if not result.get('exists'):
            continue
        meta = result.get('meta') or {}
        degree_total = int(meta.get('degree_total') or 0)
        mass = 1.0 / math.log(2 + max(0, degree_total)) if degree_total > 0 else 0
        candidates.append((word, h8, mass))
    
    # Select anchors
    solid = [(w, h8) for w, h8, m in candidates if m > mean_mass]
    if len(solid) >= 2:
        anchors = solid
    else:
        top = sorted(candidates, key=lambda x: x[2], reverse=True)[:64]
        top_set = {h8 for _, h8, _ in top}
        anchors = [(w, h8) for w, h8, _ in candidates if h8 in top_set]
    
    if len(anchors) < 2:
        return json.dumps({"error": "Too few anchors found"})
    
    anchor_words = {w for w, _ in anchors}
    
    # Collect occurrences
    def compute_ctx_hash(idx: int, k: int = 2) -> str:
        start = max(0, idx - k)
        end = min(len(tokens), idx + k + 1)
        window = [tokens[i][0] for i in range(start, end)]
        normalized = ' '.join(w.lower() for w in window)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
    
    occurrences = []
    for idx, (word, line_num) in enumerate(tokens):
        if word in anchor_words:
            h8 = word_to_hash.get(word) or hash8_hex(f"Ġ{word}")
            occurrences.append((word, h8, line_num, compute_ctx_hash(idx)))
    
    if len(occurrences) < 2:
        return json.dumps({"error": "Too few anchor occurrences"})
    
    # Create edges
    doc_name = path.name
    edges_added = 0
    
    for i in range(len(occurrences) - 1):
        src_word, src_h8, _, _ = occurrences[i]
        tgt_word, tgt_h8, tgt_line, tgt_ctx = occurrences[i + 1]
        
        _overlay.add_edge(
            src_h8, tgt_h8,
            weight=1.0,
            doc=doc_name,
            line=tgt_line,
            ctx_hash=tgt_ctx,
        )
        _overlay.define_label(src_h8, src_word)
        _overlay.define_label(tgt_h8, tgt_word)
        edges_added += 1
    
    # Save
    _overlay_path.parent.mkdir(parents=True, exist_ok=True)
    _overlay.save(_overlay_path)
    
    return json.dumps({
        "success": True,
        "file": file_path,
        "edges": edges_added,
        "anchors": len(anchor_words),
        "overlay_path": str(_overlay_path),
    }, indent=2)


@mcp.tool()
def ingest_python(file_path: str) -> str:
    """
    Index a Python file with structure-aware edges (DEF, IMP).
    
    NOTE: Creates advisory edges (not σ-proof). AST is structural/Liquid,
    not semantic/Crystal. Use text-based ingest for σ-edges.
    
    Creates edges for:
    - Δ_DEF: class_name → file:line, function_name → file:line
    - Δ_IMP: module → imports
    
    Args:
        file_path: Path to Python file
    
    Returns:
        JSON with edges added, symbols indexed, etc.
    """
    _ensure_initialized()
    import ast
    import hashlib
    from invariant_sdk.cli import hash8_hex
    
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    
    if path.suffix != '.py':
        return json.dumps({"error": f"Not a Python file: {file_path}"})
    
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except Exception as e:
        return json.dumps({"error": f"Parse error: {e}"})
    
    doc_name = path.name
    edges_added = 0
    symbols = []
    
    # Create file hash as the "file node"
    file_h8 = hash8_hex(f"Ġ{doc_name.lower()}")
    _overlay.define_label(file_h8, doc_name)
    
    def ctx_hash_for_line(line_num: int) -> str:
        """Create ctx_hash for a specific line."""
        lines = source.split('\n')
        if 0 < line_num <= len(lines):
            content = lines[line_num - 1].strip()
            return hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]
        return ""
    
    # Process AST nodes
    for node in ast.walk(tree):
        # Class definitions
        if isinstance(node, ast.ClassDef):
            name = node.name.lower()
            h8 = hash8_hex(f"Ġ{name}")
            ctx = ctx_hash_for_line(node.lineno)
            
            # Edge: class → file (DEF relationship)
            _overlay.add_edge(
                h8, file_h8,
                weight=1.0,
                doc=doc_name,
                line=node.lineno,
                ctx_hash=ctx,
                ring="advisory",
            )
            _overlay.define_label(h8, name)
            symbols.append({"type": "class", "name": name, "line": node.lineno})
            edges_added += 1
            
            # Process methods
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_name = item.name.lower()
                    method_h8 = hash8_hex(f"Ġ{method_name}")
                    method_ctx = ctx_hash_for_line(item.lineno)
                    
                    # Edge: method → class (belongs to)
                    _overlay.add_edge(
                        method_h8, h8,
                        weight=1.0,
                        doc=doc_name,
                        line=item.lineno,
                        ctx_hash=method_ctx,
                        ring="advisory",
                    )
                    _overlay.define_label(method_h8, method_name)
                    edges_added += 1
        
        # Top-level functions
        elif isinstance(node, ast.FunctionDef):
            # Check if top-level (parent is Module)
            parent = getattr(node, '_parent', None)
            if parent is None or isinstance(parent, ast.Module):
                name = node.name.lower()
                h8 = hash8_hex(f"Ġ{name}")
                ctx = ctx_hash_for_line(node.lineno)
                
                # Edge: function → file
                _overlay.add_edge(
                    h8, file_h8,
                    weight=1.0,
                    doc=doc_name,
                    line=node.lineno,
                    ctx_hash=ctx,
                    ring="advisory",
                )
                _overlay.define_label(h8, name)
                symbols.append({"type": "function", "name": name, "line": node.lineno})
                edges_added += 1
        
        # Imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.lower()
                mod_h8 = hash8_hex(f"Ġ{mod_name}")
                ctx = ctx_hash_for_line(node.lineno)
                
                # Edge: file → imports module
                _overlay.add_edge(
                    file_h8, mod_h8,
                    weight=1.0,
                    doc=doc_name,
                    line=node.lineno,
                    ctx_hash=ctx,
                    ring="advisory",
                )
                _overlay.define_label(mod_h8, mod_name)
                edges_added += 1
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_name = node.module.lower()
                mod_h8 = hash8_hex(f"Ġ{mod_name}")
                ctx = ctx_hash_for_line(node.lineno)
                
                _overlay.add_edge(
                    file_h8, mod_h8,
                    weight=1.0,
                    doc=doc_name,
                    line=node.lineno,
                    ctx_hash=ctx,
                    ring="advisory",
                )
                _overlay.define_label(mod_h8, mod_name)
                edges_added += 1
    
    # Mark parents for nested check (needed for top-level function detection)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node
    
    # Save
    _overlay_path.parent.mkdir(parents=True, exist_ok=True)
    _overlay.save(_overlay_path)
    
    return json.dumps({
        "success": True,
        "file": file_path,
        "edges": edges_added,
        "symbols": symbols,
        "overlay_path": str(_overlay_path),
    }, indent=2)


# ============================================================================
# HELPERS
# ============================================================================

def _find_doc_path(doc: str) -> Optional[Path]:
    """Find document in project."""
    candidates = [
        Path(doc),
        Path(".") / doc,
        Path(".invariant") / doc,
        Path(".invariant/uploads") / doc,
        Path("docs") / doc,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _compute_hashes_at_line(tokens: list, target_line: int, k: int = 2) -> list:
    """Compute all ctx_hashes for tokens at a given line."""
    import hashlib
    
    line_tokens = [(i, t) for i, t in enumerate(tokens) if t[1] == target_line]
    hashes = []
    
    for anchor_idx, _ in line_tokens:
        start = max(0, anchor_idx - k)
        end = min(len(tokens), anchor_idx + k + 1)
        window = [tokens[i][0] for i in range(start, end)]
        normalized = ' '.join(window)
        h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
        hashes.append(h)
    
    return hashes


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the MCP server."""
    mcp.run(transport='stdio')


if __name__ == "__main__":
    main()
