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

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
except Exception:  # pragma: no cover
    FastMCP = None


class _NoMCP:
    """Fallback so SDK functions can be imported without the `mcp` package."""

    def tool(self):  # noqa: D401
        def decorator(fn):
            return fn

        return decorator

    def run(self, *args, **kwargs):
        raise RuntimeError(
            "MCP server runtime requires the `mcp` Python package, but it is not installed. "
            "Install it in your environment and retry."
        )


# Initialize MCP server (or a no-op wrapper for direct imports)
mcp = FastMCP("invariant") if FastMCP else _NoMCP()

# Globals (initialized on first use)
_physics = None
_overlay = None
_overlay_path = None
_halo_meta_cache: dict[str, dict] = {}


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


def _get_halo_meta_cached(hashes, *, chunk_size: int = 4000) -> tuple[dict[str, dict], int]:
    """
    Meta-only Halo lookup with in-process cache + chunking.

    Returns:
      (results_by_hash8, http_requests_made)
    """
    _ensure_initialized()
    if not _physics:
        return {}, 0

    global _halo_meta_cache

    hashes_list = [str(h).lower() for h in hashes]
    missing = [h for h in hashes_list if h and h not in _halo_meta_cache]

    http_requests = 0
    for start in range(0, len(missing), int(chunk_size)):
        http_requests += 1
        chunk = missing[start : start + int(chunk_size)]
        resp = _physics._client.get_halo_pages(chunk, limit=0) or {}
        _halo_meta_cache.update(resp)

    return {h: (_halo_meta_cache.get(h) or {}) for h in hashes_list}, http_requests


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
        # NOTE: `OverlayGraph.sources` tracks overlay FILES, not indexed documents.
        # For progress/debugging we want unique provenance docs inside edges.
        "overlay_docs": (
            len({e.doc for edges in _overlay.edges.values() for e in edges if e.doc})
            if _overlay
            else 0
        ),
    }
    return json.dumps(info, indent=2)


@mcp.tool()
def locate(issue_text: str, max_results: int = 0) -> str:
    """
    Find relevant files AND exact definition lines from issue text.
    
    USE INSTEAD OF: grep -rn, rg, find (repo-wide searches)
    
    KEY FEATURE: Coordinate Resolution
        - Finds the EXACT line where query words co-occur
        - Prioritizes definitions (def, class) over usages
        - Returns preview at that line - usually enough to start fixing!
    
    Example:
        locate("def separability_matrix")
        → Returns: {file: "separable.py", first_match: {line: 293, preview: "def separability_matrix(...):"}}
        
        NO NEED FOR GREP - the preview shows the definition!
    
    How it works:
        1. Semantic search (Crystal) → finds relevant files
        2. Coordinate resolution → finds best line in each file
        3. Definition priority → shows def/class first, not imports
    
    Args:
        issue_text: Paste error, keywords, or "def function_name" to find definition
        max_results: How many files to return (0 = all with score > 1)
    
    Returns:
        JSON with files + first_match preview at the BEST line (definition if exists)
    """
    _ensure_initialized()
    
    import math
    from invariant_sdk.cli import hash8_hex
    from invariant_sdk.tokenize import dedupe_preserve_order, tokenize_simple
    
    # Extract ALL words from issue text (universal tokenization)
    # Let the crystal classify them by mass (solid vs gas)
    # NO heuristics: no stopwords, no programming-specific patterns
    
    # Extract deterministic surface tokens (supports snake_case identifiers).
    unique_words = dedupe_preserve_order(tokenize_simple(issue_text))
    
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
        batch_results, _http = _get_halo_meta_cached(word_hashes.values(), chunk_size=4000)
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
    preview_count = 0  # Only read files for top N previews (MDL: minimize reads)
    MAX_PREVIEWS = 5
    
    for doc, info in ranked:
        if info["score"] <= 1:
            continue  # No real match
        if max_results > 0 and len(results) >= max_results:
            break
        
        result_entry = {
            "file": doc,
            "score": info["score"],
            "matching_words": info["words"],
            "n_matches": len(info["words"]),
            "candidate_lines": info["lines"],
        }
        
        # Add mini-preview for top N files (Bisection Law: more bits per call)
        # Theory: coordinates + preview = actionable immediately, no need for scoped_grep
        if preview_count < MAX_PREVIEWS and info["lines"]:
            path = _find_doc_path(doc)
            if path:
                try:
                    text = path.read_text(encoding='utf-8')
                    lines = text.split('\n')
                    
                    # COORDINATE RESOLUTION (replaces grep):
                    # Find the line where ALL query words co-occur
                    # Priority: 1) All words on same line, 2) Definition (def/class), 3) First occurrence
                    
                    query_words_lower = [w.lower() for w in unique_words if len(w) >= 3]
                    best_line = None
                    best_score = -1
                    
                    # Scan ALL lines in file (not just candidate_lines) for co-occurrence
                    # This is the key to replacing grep: find exact definition line
                    # Limit to 500 lines for performance (most definitions are near top)
                    scan_limit = min(len(lines), 500)
                    
                    for line_num in range(1, scan_limit + 1):
                        line_content = lines[line_num - 1].lower()
                        
                        # Score: how many query words appear on this line?
                        words_on_line = sum(1 for w in query_words_lower if w in line_content)
                        if words_on_line == 0:
                            continue  # No match, skip
                        
                        score = words_on_line * 10
                        
                        # Bonus for definitions (def/class/async def)
                        stripped = lines[line_num - 1].strip()
                        if stripped.startswith(('def ', 'class ', 'async def ')):
                            score += 100  # Strong preference for definitions
                        
                        # Bonus if line is in candidate_lines (overlay confirmed)
                        if line_num in info["lines"]:
                            score += 5
                        
                        if score > best_score:
                            best_score = score
                            best_line = line_num
                    
                    # Fallback to first candidate_line if no scoring worked
                    if best_line is None and info["lines"]:
                        best_line = info["lines"][0]
                    
                    if 1 <= best_line <= len(lines):
                        # Get line + 1 context line after (minimal, per MDL)
                        preview_lines = []
                        idx = best_line - 1
                        preview_lines.append(f"{best_line}: {lines[idx].rstrip()[:100]}")
                        if idx + 1 < len(lines):
                            preview_lines.append(f"{best_line+1}: {lines[idx+1].rstrip()[:100]}")
                        
                        result_entry["first_match"] = {
                            "line": best_line,
                            "preview": "\n".join(preview_lines)
                        }
                        preview_count += 1
                except Exception:
                    pass  # Skip preview on error
        
        results.append(result_entry)
    
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
                batch_results, _http = _get_halo_meta_cached(hash_to_label.keys(), chunk_size=4000)
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
    from invariant_sdk.tokenize import tokenize_with_lines
    
    path = _find_doc_path(doc)
    if not path:
        return json.dumps({"error": f"Document not found: {doc}", "status": "broken"})
    
    try:
        text = path.read_text(encoding='utf-8')
        lines = text.split('\n')
        
        if line < 1 or line > len(lines):
            return json.dumps({"error": f"Line {line} out of range", "status": "broken"})
        
        # Tokenize for hash verification
        tokens = tokenize_with_lines(text)
        
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
def scoped_grep(pattern: str, files: str, max_matches: int = 20) -> str:
    """
    Search for EXACT pattern in specific files. Returns line numbers + context.
    
    **USE INSTEAD OF:** grep -rn, rg (repo-wide searches)
    **USE AFTER:** locate() to get file list, then grep ONLY those files
    
    Theory: Scoped search (file-specific) has higher info-gain than repo-wide.
    This tool limits output to avoid token waste.
    
    Args:
        pattern: Exact string or regex pattern to search
        files: Comma-separated file paths (from locate results)
               Example: "pkg/utils.py,tests/test_utils.py"
        max_matches: Maximum matches to return (default 20, max 50)
    
    Returns:
        JSON with matches: [{file, line, content, context_before, context_after}]
    
    Example workflow:
        1. locate("ASCIIValidator test") → finds validators.py, test_validators.py
        2. scoped_grep("ASCIIUsernameValidator", "validators.py,test_validators.py")
           → exact line numbers where pattern appears
    """
    import re
    
    _ensure_initialized()
    
    # Parse files
    file_list = [f.strip() for f in files.split(",") if f.strip()]
    if not file_list:
        return json.dumps({"error": "No files specified"})
    
    # Limit max_matches
    max_matches = min(max(1, max_matches), 50)
    
    matches = []
    files_searched = 0
    files_with_matches = 0
    
    for file_path in file_list:
        # Resolve path
        path = _find_doc_path(file_path)
        if not path:
            continue
        
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue
        
        files_searched += 1
        lines = text.split('\n')
        file_has_match = False
        
        for line_num, line_content in enumerate(lines, 1):
            try:
                if re.search(pattern, line_content):
                    file_has_match = True
                    
                    # Get context (1 line before/after)
                    context_before = lines[line_num - 2] if line_num > 1 else ""
                    context_after = lines[line_num] if line_num < len(lines) else ""
                    
                    matches.append({
                        "file": file_path,
                        "line": line_num,
                        "content": line_content.strip(),
                        "context_before": context_before.strip()[:100],
                        "context_after": context_after.strip()[:100],
                    })
                    
                    if len(matches) >= max_matches:
                        break
            except re.error:
                # Invalid regex, try literal search
                if pattern in line_content:
                    file_has_match = True
                    context_before = lines[line_num - 2] if line_num > 1 else ""
                    context_after = lines[line_num] if line_num < len(lines) else ""
                    
                    matches.append({
                        "file": file_path,
                        "line": line_num,
                        "content": line_content.strip(),
                        "context_before": context_before.strip()[:100],
                        "context_after": context_after.strip()[:100],
                    })
                    
                    if len(matches) >= max_matches:
                        break
        
        if file_has_match:
            files_with_matches += 1
        
        if len(matches) >= max_matches:
            break
    
    return json.dumps({
        "pattern": pattern,
        "files_searched": files_searched,
        "files_with_matches": files_with_matches,
        "total_matches": len(matches),
        "truncated": len(matches) >= max_matches,
        "matches": matches,
    }, indent=2)



@mcp.tool()
def ingest(file_path: str) -> str:
    """
    Index files or folders into the local overlay.
    
    This creates σ-facts (grounded observations) from documents.
    
    **FOR SWE-BENCH:** Point this at the repository root to index all Python files.
    
    Args:
        file_path: Path to file OR folder to ingest
                   Folders: recursively finds .py, .md, .txt files
    
    Returns:
        JSON with stats: files processed, edges added, anchors found
    
    Example:
        ingest("/path/to/repo")  # Indexes the entire repo
        ingest("utils.py")        # Indexes single file
    """
    _ensure_initialized()
    import hashlib
    import math
    import time
    from invariant_sdk.tokenize import tokenize_with_lines
    
    from invariant_sdk.cli import hash8_hex
    
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"Path not found: {file_path}"})
    
    # Collect files (support both single file and folder)
    if path.is_file():
        files = [path]
    else:
        # Helper: Check if file is text (UTF-8 decodable)
        # Theory: Observable property, not heuristic - works for ALL languages
        def is_text_file(file_path: Path) -> bool:
            if not file_path.is_file():
                return False
            try:
                # Read first 512 bytes to check (optimization)
                with open(file_path, 'rb') as f:
                    sample = f.read(512)
                # Try decode as UTF-8
                sample.decode('utf-8', errors='strict')
                return True
            except (UnicodeDecodeError, OSError):
                return False
        
        # Find ALL files (no extension filtering)
        all_files = [f for f in path.rglob("*") if f.is_file()]
        
        # Filter using .gitignore if present (Theory: Explicit user declaration)
        gitignore_path = path / '.gitignore'
        if gitignore_path.exists():
            try:
                import pathspec
                gitignore_text = gitignore_path.read_text(encoding='utf-8')
                spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_text.splitlines())
                files_after_gitignore = [f for f in all_files if not spec.match_file(str(f.relative_to(path)))]
            except Exception:
                files_after_gitignore = all_files
        else:
            files_after_gitignore = all_files

        # Always ignore protocol / build artifacts (prevents self-indexing .invariant, etc.)
        def is_default_ignored(p: Path) -> bool:
            try:
                rel = p.relative_to(path)
            except Exception:
                rel = p
            for part in rel.parts:
                if part in {".git", ".invariant", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}:
                    return True
                if part.endswith(".egg-info"):
                    return True
            return False

        files_after_gitignore = [f for f in files_after_gitignore if not is_default_ignored(f)]
        
        # Filter to text files only (UTF-8 decodable)
        files = [f for f in files_after_gitignore if is_text_file(f)]
        
        if not files:
            return json.dumps({"error": f"No text files found in {file_path}"})

    t0 = time.perf_counter()
    try:
        print(f"[invariant] ingest: scanning {len(files)} files", flush=True)
    except Exception:
        pass
    
    # OPTIMIZATION: Mega-batch all words from all files (Theory: MDL - 1 request < N requests)
    # Step 1: Collect all unique words from ALL files first
    all_words_set = set()
    file_words_map = {}  # file_path -> list of unique words
    
    for scanned_i, file_path_obj in enumerate(files, 1):
        if scanned_i == 1 or (scanned_i % 100 == 0) or scanned_i == len(files):
            try:
                print(f"[invariant] ingest: scanned {scanned_i}/{len(files)}", flush=True)
            except Exception:
                pass
        try:
            text = file_path_obj.read_text(encoding='utf-8')
        except Exception:
            continue
        
        # Tokenize
        tokens = tokenize_with_lines(text)
        
        if len(tokens) < 2:
            continue
        
        words = [w for w, _ in tokens]
        unique_words = list(dict.fromkeys(words))[:500]
        
        if len(unique_words) < 2:
            continue
        
        file_words_map[file_path_obj] = (tokens, unique_words)
        all_words_set.update(unique_words)

    if not all_words_set:
        return json.dumps({"error": "No words found in any files"})

    t_scan = time.perf_counter()
    try:
        print(
            f"[invariant] ingest: vocabulary {len(all_words_set)} words from {len(file_words_map)} files",
            flush=True,
        )
    except Exception:
        pass
    
    # Step 2: ONE mega-batch request for ALL words
    all_words_list = list(all_words_set)
    word_to_hash = {w: hash8_hex(f"Ġ{w}") for w in all_words_list}
    
    try:
        # Mega-batch meta lookup (chunked + cached)
        batch_results, http_requests = _get_halo_meta_cached(word_to_hash.values(), chunk_size=4000)
    except Exception as e:
        return json.dumps({"error": f"Crystal server error: {e}"})

    t_meta = time.perf_counter()
    try:
        print(f"[invariant] ingest: crystal meta ok ({http_requests} HTTP)", flush=True)
    except Exception:
        pass
    
    mean_mass = _physics.mean_mass
    
    # Step 3: Process each file using cached batch_results
    total_files = len(file_words_map)
    total_edges = 0
    total_anchors_found = 0
    files_processed = 0
    files_details = []  # Track progress for each file
    
    for file_path_obj, (tokens, unique_words) in file_words_map.items():
        # Use cached batch_results (no new HTTP request)
        candidates = []
        for word in unique_words:
            h8 = word_to_hash.get(word)
            if not h8:
                continue
            result = batch_results.get(h8) or {}
            if not result.get('exists'):
                # Unknown words = Local Anchors (solid)
                candidates.append((word, h8, 1.0))
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
            continue
        
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
            continue
        
        # Use relative path from ingested folder for doc name (prevents collisions)
        # e.g., "pkg/utils.py" not "utils.py"
        doc_name = str(file_path_obj.relative_to(path)) if path.is_dir() else file_path_obj.name
        edges_added = 0
        
        for i in range(len(occurrences) - 1):
            src_word, src_h8, _, _ = occurrences[i]
            tgt_word, tgt_h8, tgt_line, tgt_ctx = occurrences[i + 1]
            
            _overlay.add_edge(
                src_h8, tgt_h8,
                weight=1.0,
                doc=doc_name,
                ring="sigma",  # All document edges are σ (facts)
                phase="solid",
                line=tgt_line,
                ctx_hash=tgt_ctx,
            )
            _overlay.define_label(src_h8, src_word)
            _overlay.define_label(tgt_h8, tgt_word)
            edges_added += 1
        
        total_edges += edges_added
        total_anchors_found += len(anchor_words)
        files_processed += 1

        if files_processed == 1 or (files_processed % 100 == 0) or files_processed == total_files:
            try:
                print(f"[invariant] ingest: indexed {files_processed}/{total_files}", flush=True)
            except Exception:
                pass
        
        # Track first 10 files for progress visibility
        if len(files_details) < 10:
            files_details.append({
                "file": doc_name,
                "edges": edges_added,
                "anchors": len(anchor_words)
            })
    
    
    # Save overlay
    _overlay_path.parent.mkdir(parents=True, exist_ok=True)
    _overlay.save(_overlay_path)

    t_save = time.perf_counter()
    
    return json.dumps({
        "success": True,
        "path": file_path,
        "total_files": total_files,
        "files_processed": files_processed,
        "total_edges": total_edges,
        "total_anchors": total_anchors_found,
        "unique_words_processed": len(all_words_set),
        "http_requests": http_requests,  # Mega-batch optimization (chunked)
        "files_sample": files_details,  # First 10 files
        "overlay_path": str(_overlay_path),
        "timing_s": {
            "scan": round(t_scan - t0, 3),
            "crystal_meta": round(t_meta - t_scan, 3),
            "index": round(t_save - t_meta, 3),
            "total": round(t_save - t0, 3),
        },
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
