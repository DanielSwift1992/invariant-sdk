"""
Invariant MCP Server — Semantic Search for LLM Agents

WHAT THIS DOES:
Instead of reading every file to find relevant code, use these tools to:
1. FIND files matching your task (locate) — 14ms vs minutes of grep
2. UNDERSTAND file structure without reading content (semantic_map)
3. VERIFY connections exist before claiming them (prove_path)

RECOMMENDED WORKFLOW:

  1. status() — Check what's indexed, how many edges
  
  2. locate(issue_text) — Finds files ranked by interference score (2^n)
     Input: paste the error, issue, or task description
     Output: ranked files (score=32 means 5 concepts matched, very relevant)
     
  3. semantic_map(file) — Get file skeleton (10x cheaper than reading)
     Shows: key concepts, connections, line numbers
     
  4. prove_path(A, B) — Verify "A relates to B" before stating it
     Returns: exists=True/False + witness path
     
  5. ingest(file) — Add new files to the index

WHY USE THIS INSTEAD OF GREP/FILE READ:
- locate() gives ONE ranked list, not N separate grep results
- semantic_map() costs ~50 tokens, full file costs ~5000 tokens
- prove_path() prevents hallucinations about connections

THEORY:
σ-edges = proven in documents, λ-edges = inferred connections
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
    Check if Invariant is ready and what's indexed.
    
    CALL THIS FIRST to see:
    - How many files are indexed (overlay_docs)
    - How many connections exist (overlay_edges)
    - If crystal server is connected
    
    Example output:
    {
      "overlay_edges": 25402,
      "overlay_docs": 3,
      "overlay_labels": 2786
    }
    
    If overlay_edges = 0, run ingest() on your project first.
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
def locate(issue_text: str, max_results: int = 0) -> str:
    """
    Find relevant files from an issue, error, or task description.
    
    USE INSTEAD OF: grep, ripgrep, file search
    ADVANTAGE: Returns ONE ranked list with interference scoring (2^n)
    
    Example:
        locate("TypeError in user authentication module")
        → Returns ranked files: auth.py (score=16), user.py (score=8)
    
    How scoring works:
        score = 2^n where n = number of matching concepts
        score=32 means 5 concepts matched → very relevant
        score=2 means 1 concept matched → weak match
    
    Args:
        issue_text: Paste the error message, bug report, or task description
        max_results: How many files to return. Choose based on your needs:
                     - For focused debugging: 3
                     - For broad exploration: 10
                     Default: all files with score > 1
    
    Returns:
        JSON with ranked files, matching concepts, and candidate line numbers
    """
    _ensure_initialized()
    
    import re
    import math
    from invariant_sdk.cli import hash8_hex
    
    # Extract ALL words from issue text (universal tokenization)
    # Let the crystal classify them by mass (solid vs gas)
    # NO heuristics: no stopwords, no programming-specific patterns
    
    words = []
    for m in re.finditer(r'\b[a-zA-Z]{3,}\b', issue_text):
        words.append(m.group().lower())
    
    # Deduplicate, keep order
    seen = set()
    unique_words = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique_words.append(w)
    
    if not unique_words:
        return json.dumps({"error": "No words found in issue_text"})
    
    # Hash words and get mass from crystal
    word_hashes = {w: hash8_hex(f"Ġ{w}") for w in unique_words}
    
    # Classify by mass: solid (anchor) vs gas (noise)
    # Theory: Mass = 1/log(2+degree), Solid = mass > mean_mass
    # Words not in crystal = unknown (we cannot judge them)
    solid_seeds = []
    gas_seeds = []
    unknown_words = []
    
    try:
        batch_results = _physics._client.get_halo_pages(word_hashes.values(), limit=0)
        for word, h8 in word_hashes.items():
            result = batch_results.get(h8) or {}
            if result.get('exists'):
                meta = result.get('meta') or {}
                degree = int(meta.get('degree_total') or 0)
                mass = 1.0 / math.log(2 + max(0, degree)) if degree > 0 else 0
                if mass > _physics.mean_mass:
                    solid_seeds.append((word, h8, mass))
                else:
                    gas_seeds.append((word, h8, mass))
            else:
                unknown_words.append(word)
    except Exception as e:
        return json.dumps({"error": f"Crystal connection failed: {e}"})
    
    # Create lookup for ALL query words (not just crystal-classified)
    # Crystal classification is OPTIONAL (provides mass), not a filter
    all_word_hashes = word_hashes  # All query words
    word_mass_lookup = {word: mass for word, h8, mass in solid_seeds + gas_seeds}
    
    # Search overlay for ALL query words
    file_scores = {}  # doc -> {words, lines}
    
    for word, h8 in all_word_hashes.items():
        # Check if this word has edges in overlay
        for edge in _overlay.edges.get(h8, []):
            if not edge.doc:
                continue
            if edge.doc not in file_scores:
                file_scores[edge.doc] = {"words": set(), "lines": []}
            file_scores[edge.doc]["words"].add(word)
            if edge.line and edge.line not in file_scores[edge.doc]["lines"]:
                file_scores[edge.doc]["lines"].append(edge.line)
    
    # Calculate score: solid matches = 2^n, gas matches add 1 each
    # This is theory: solid = high information, gas = low information
    for doc in file_scores:
        info = file_scores[doc]
        n_words = len(info["words"])
        # Score based on number of UNIQUE words matched
        info["score"] = 2 ** n_words
        info["words"] = list(info["words"])
        info["lines"] = sorted(info["lines"])[:10]
    
    # Rank results
    ranked = sorted(file_scores.items(), key=lambda x: x[1]["score"], reverse=True)
    
    # Filter: only files with score > 1 (at least 1 matching seed)
    # max_results=0 means return all matching files
    results = []
    for doc, info in ranked:
        if info["score"] <= 1:
            continue  # No real match
        if max_results > 0 and len(results) >= max_results:
            break
        results.append({
            "file": doc,
            "score": info["score"],
            "matching_words": info["words"],
            "n_matches": len(info["words"]),
            "candidate_lines": info["lines"],
        })
    
    return json.dumps({
        "query_words": unique_words,
        "solid_count": len(solid_seeds),
        "gas_count": len(gas_seeds),
        "unknown_count": len(unknown_words),
        "files_found": len(results),
        "results": results,
    }, indent=2)


@mcp.tool()
def semantic_map(file_path: str) -> str:
    """
    Get file structure without reading the whole file.
    
    USE INSTEAD OF: reading the entire file into context
    COST: ~50 tokens vs ~5000 tokens for full file
    
    Returns:
        - anchors: key concepts with importance (mass)
        - edges: connections between concepts with line numbers
    
    Example use case:
        After locate() finds "auth.py", use semantic_map("auth.py")
        to see its structure before deciding which lines to read.
    
    Args:
        file_path: Path to the file
    """
    _ensure_initialized()
    
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    
    result = {
        "file": file_path,
        "type": path.suffix,
    }
    
    # Count total lines for context
    try:
        with open(path, 'r', encoding='utf-8') as f:
            result["lines_total"] = sum(1 for _ in f)
    except Exception:
        result["lines_total"] = 0

    
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
    Verify a connection exists before claiming it.
    
    USE BEFORE: stating "A is related to B" or "A affects B"
    PREVENTS: hallucinating connections that don't exist
    
    Example:
        prove_path("user", "database")
        → {"exists": true, "path": ["user", "auth", "database"], "ring": "sigma"}
        
        prove_path("coffee", "database")  
        → {"exists": false} — don't claim this connection!
    
    Ring types:
        "sigma" = proven in documents (strong evidence)
        "lambda" = inferred from language patterns (weaker)
    
    Args:
        source: First concept (e.g., "user", "authentication")
        target: Second concept to check connection to
        max_hops: Search depth. Most real connections are within 3 hops.
                  Use higher values only for exploring distant connections.
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
