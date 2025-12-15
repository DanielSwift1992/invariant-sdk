"""
engine.py — Shared "work" primitives (Locate + Map) for UI/CLI/MCP.

Goal: remove split-brain between SDK "brain" and UI "face" by having a single
implementation for:
  - file discovery from issue text (locate)
  - file structure outline (map)

This module is intentionally stdlib-only and deterministic.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .halo import hash8_hex
from .overlay import OverlayEdge, OverlayGraph
from .tokenize import dedupe_preserve_order, tokenize_simple

if TYPE_CHECKING:
    from .physics import HaloPhysics



@dataclass(frozen=True)
class DocStats:
    doc: str
    edges: int
    nodes: int


@dataclass
class OverlayIndex:
    """
    Derived indexes for an OverlayGraph.

    These structures are pure accelerators (Invariant III). They do not change
    truth, only reduce the energy cost of reading it.
    """

    incoming: Dict[str, List[Tuple[str, OverlayEdge]]]
    doc_stats: Dict[str, DocStats]
    known_hashes: set[str]
    label_to_hash: Dict[str, str]
    hash_to_docs: Dict[str, set[str]]  # For IDF: which docs contain each hash

    @classmethod
    def build(cls, overlay: OverlayGraph) -> "OverlayIndex":
        incoming: Dict[str, List[Tuple[str, OverlayEdge]]] = {}
        known_hashes: set[str] = set(overlay.edges.keys())
        doc_edges: Dict[str, int] = {}
        doc_nodes: Dict[str, set[str]] = {}
        hash_to_docs: Dict[str, set[str]] = {}  # IDF support

        for src, edge_list in overlay.edges.items():
            for edge in edge_list:
                known_hashes.add(edge.tgt)
                incoming.setdefault(edge.tgt, []).append((src, edge))

                if edge.doc:
                    doc_edges[edge.doc] = doc_edges.get(edge.doc, 0) + 1
                    s = doc_nodes.get(edge.doc)
                    if s is None:
                        s = set()
                        doc_nodes[edge.doc] = s
                    s.add(src)
                    s.add(edge.tgt)
                    
                    # Track docs per hash (for IDF scoring)
                    hash_to_docs.setdefault(src, set()).add(edge.doc)
                    hash_to_docs.setdefault(edge.tgt, set()).add(edge.doc)

        doc_stats: Dict[str, DocStats] = {}
        for doc, edges in doc_edges.items():
            nodes = len(doc_nodes.get(doc) or set())
            doc_stats[doc] = DocStats(doc=doc, edges=edges, nodes=nodes)

        label_to_hash: Dict[str, str] = {}
        for h8, label in (overlay.labels or {}).items():
            if not label:
                continue
            key = str(label).strip().lower()
            if not key:
                continue
            # Deterministic tie-break: keep first-seen.
            label_to_hash.setdefault(key, h8)

        return cls(
            incoming=incoming, 
            doc_stats=doc_stats, 
            known_hashes=known_hashes, 
            label_to_hash=label_to_hash,
            hash_to_docs=hash_to_docs,
        )


def tokenize_query(text: str) -> List[str]:
    return dedupe_preserve_order(tokenize_simple(text or ""))


def _resolve_query_hash(word: str, *, overlay: OverlayGraph, index: Optional[OverlayIndex]) -> str:
    """
    Resolve a surface word to the most likely overlay hash.

    In modern overlays, ingest uses `hash8_hex(f"Ġ{word}")` and defines a label
    equal to the surface form, so this is usually exact. The label fallback is
    for backward compatibility only.
    """
    w = (word or "").strip().lower()
    h8 = hash8_hex(f"Ġ{w}")
    if index and h8 in index.known_hashes:
        return h8
    if h8 in (overlay.labels or {}):
        return h8
    if index:
        by_label = index.label_to_hash.get(w)
        if by_label:
            return by_label
    # Slow fallback (rare).
    for node, label in (overlay.labels or {}).items():
        if label and str(label).strip().lower() == w:
            return node
    return h8


def _scan_file_for_words(
    *,
    path: Path,
    words: Sequence[str],
    max_occurrences: int,
    max_line_len: int = 320,
    word_weights: Optional[Dict[str, float]] = None,
) -> List[Dict]:
    """
    Cheap grep-like preview for top results only (Invariant III).

    Returns occurrences: [{line, content, matches:[...]}]
    """
    if not words or max_occurrences <= 0:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    needles = [w.strip().lower() for w in words if w and w.strip()]
    needles = [n for n in needles if n]
    # Dedupe needles while preserving order.
    if needles:
        seen = set()
        deduped = []
        for n in needles:
            if n in seen:
                continue
            seen.add(n)
            deduped.append(n)
        needles = deduped
    if not needles:
        return []

    needle_weights = {n: float((word_weights or {}).get(n, 1.0)) for n in needles}

    # Collect candidate hit lines with their "energy" and coverage.
    # Selection prefers lines that cover MORE distinct needles (intersection / bisection),
    # then higher energy, then earlier line number.
    lines = text.splitlines()
    candidates: List[Dict] = []
    for i, raw_line in enumerate(lines, 1):
        raw = raw_line.rstrip("\n")
        lower = raw.lower()
        hits = [n for n in needles if n in lower]
        if not hits:
            continue
        hits_set = set(hits)
        score = sum(needle_weights.get(n, 0.0) for n in hits_set)
        candidates.append({"line": i, "hits": sorted(hits_set), "score": score, "coverage": len(hits_set)})

    if not candidates:
        return []

    candidates.sort(key=lambda c: (-int(c.get("coverage") or 0), -float(c.get("score") or 0.0), int(c.get("line") or 0)))

    needle_set = set(needles)
    selected: List[Dict] = []
    covered: set[str] = set()
    selected_lines: set[int] = set()

    # First pass: pick lines that add new needle coverage (maximizes information gain).
    for c in candidates:
        if len(selected) >= max_occurrences:
            break
        hits_set = set(c.get("hits") or [])
        if not hits_set:
            continue
        if hits_set - covered:
            selected.append(c)
            selected_lines.add(int(c.get("line") or 0))
            covered |= hits_set
        if covered == needle_set:
            break

    # Second pass: fill remaining slots with strongest remaining lines.
    if len(selected) < max_occurrences:
        for c in candidates:
            if len(selected) >= max_occurrences:
                break
            line_no = int(c.get("line") or 0)
            if not line_no or line_no in selected_lines:
                continue
            selected.append(c)
            selected_lines.add(line_no)

    # Render snippets for selected lines only.
    out: List[Dict] = []
    for c in selected:
        line_no = int(c.get("line") or 0)
        if not line_no or line_no < 1 or line_no > len(lines):
            continue
        raw = lines[line_no - 1].rstrip("\n")
        lower = raw.lower()
        hits = [str(h) for h in (c.get("hits") or []) if h]

        best_pos = None
        best_len = 0
        for n in hits:
            pos = lower.find(n)
            if pos < 0:
                continue
            if best_pos is None or pos < best_pos or (pos == best_pos and len(n) > best_len):
                best_pos = pos
                best_len = len(n)

        content = raw
        if max_line_len > 0 and len(content) > max_line_len:
            pos = best_pos or 0
            start = max(0, pos - (max_line_len // 4))
            end = min(len(content), start + max_line_len)
            if end - start < max_line_len and start > 0:
                start = max(0, end - max_line_len)
            snippet = content[start:end]
            if start > 0:
                snippet = "…" + snippet
            if end < len(content):
                snippet = snippet + "…"
            content = snippet

        out.append(
            {
                "line": line_no,
                "content": content,
                "matches": hits[:8],
                "score": float(c.get("score") or 0.0),
                "coverage": int(c.get("coverage") or 0),
            }
        )

    # Deterministic ordering: best coverage/score first.
    out.sort(key=lambda o: (-int(o.get("coverage") or 0), -float(o.get("score") or 0.0), int(o.get("line") or 0)))
    return out


def locate_files(
    issue_text: str,
    *,
    overlay: OverlayGraph,
    index: Optional[OverlayIndex] = None,
    physics: Optional["HaloPhysics"] = None,  # NEW: enables Query Lensing
    doc_filter: str = "",
    max_results: int = 0,
    preview_files: int = 8,
    preview_occurrences: int = 6,
    resolve_doc_path: Optional[Callable[[str], Optional[Path]]] = None,
) -> Dict:
    """
    File discovery from issue text.
    
    When `physics` is provided, enables **Query Lensing**:
      - Expands query words through Halo neighbors
      - Searches for synonyms/related concepts, not just direct matches
      - Example: "Админ" finds files with "admin", "superuser", "permission"

    Returns a SERP-style result:
      - ranked files
      - why each file matched (matching_words)
      - a small number of preview occurrences for top files
    """
    query_words = tokenize_query(issue_text)
    if not query_words:
        return {"error": "No words found in query"}

    doc_filter = (doc_filter or "").strip()
    idx = index or OverlayIndex.build(overlay)

    # === QUERY LENSING ===
    # Expand query through Halo neighbors (when physics is available).
    if physics is not None:
        expanded = physics.expand_query(query_words)
    else:
        expanded = {}
        for w in query_words:
            h8 = _resolve_query_hash(w, overlay=overlay, index=idx)
            expanded.setdefault(
                h8,
                {
                    "label": w,
                    "source_word": w,
                    "is_direct": True,
                    "weight": 1.0,
                    "mass": 1.0,
                },
            )

    file_scores: Dict[str, Dict] = {}  # doc -> {hashes:set, lines:set}

    def _touch(doc: str, h8: str, line: Optional[int]) -> None:
        if not doc:
            return
        if doc_filter and doc != doc_filter:
            return
        entry = file_scores.get(doc)
        if entry is None:
            entry = {"hashes": set(), "lines": set()}
            file_scores[doc] = entry
        entry["hashes"].add(h8)
        if line:
            entry["lines"].add(int(line))

    # Outgoing (term is src)
    for h8 in expanded.keys():
        for edge in overlay.edges.get(h8, []):
            if not edge.doc:
                continue
            _touch(edge.doc, h8, edge.line)

    # Incoming (term is tgt)
    for h8 in expanded.keys():
        for _src, edge in idx.incoming.get(h8, []):
            if not edge.doc:
                continue
            _touch(edge.doc, h8, edge.line)

    # === SCORING LAW (INVARIANTS V.2) ===
    # Score = Σ Mass × IDF × Coupling
    # Mass = global importance (α)
    # IDF = local discriminativeness (σ) = log(N_docs / df)
    # Coupling = lens conductivity (α weight), 1.0 for direct matches
    import math

    n_docs = len(idx.doc_stats) or 1

    ranked: List[Tuple[str, Dict]] = []
    for doc, info in file_scores.items():
        matched_hashes = [h8 for h8 in expanded.keys() if h8 in (info.get("hashes") or set())]
        if not matched_hashes:
            continue

        word_contributions: List[Dict] = []
        total_score = 0.0

        for h8 in matched_hashes:
            term = expanded.get(h8) or {}

            df = len(idx.hash_to_docs.get(h8, set()))
            idf = math.log(n_docs / df) if df and df < n_docs else 0.0

            mass = float(term.get("mass") or 1.0)
            coupling = 1.0 if bool(term.get("is_direct")) else abs(float(term.get("weight") or 0.0))

            contribution = mass * idf * coupling
            total_score += contribution

            word_contributions.append(
                {
                    "hash8": h8,
                    "word": str(term.get("label") or h8[:8]),
                    "source_word": str(term.get("source_word") or ""),
                    "is_direct": bool(term.get("is_direct")),
                    "mass": mass,
                    "df": df,
                    "idf": idf,
                    "weight": coupling,
                    "contribution": contribution,
                }
            )

        for wc in word_contributions:
            wc["percent"] = round(wc["contribution"] / total_score * 100, 1) if total_score > 0 else 0.0

        word_contributions.sort(key=lambda x: (-float(x.get("contribution") or 0.0), str(x.get("word") or "").lower()))
        sorted_matches = [wc["word"] for wc in word_contributions]

        ranked.append(
            (
                doc,
                {
                    "file": doc,
                    "n_matches": len(matched_hashes),
                    "matching_words": sorted_matches,
                    "word_contributions": word_contributions,
                    "score": round(total_score, 6),
                },
            )
        )

    ranked.sort(key=lambda x: (-float(x[1].get("score") or 0.0), -int(x[1].get("n_matches") or 0), x[0].lower()))

    # Apply max_results (0 = "all").
    results: List[Dict] = []
    for doc, info in ranked:
        if max_results > 0 and len(results) >= max_results:
            break
        results.append(info)

    # Preview occurrences for top files (bounded file reads).
    if resolve_doc_path:
        for i, r in enumerate(results[: max(0, int(preview_files))]):
            path = resolve_doc_path(r["file"])
            if not path:
                continue
            contributions = list(r.get("word_contributions") or [])
            n = len(contributions)
            threshold_pct = (100.0 / n) if n else 0.0
            signal_words = [
                str(wc.get("word") or "")
                for wc in contributions
                if float(wc.get("percent") or 0.0) >= threshold_pct and float(wc.get("contribution") or 0.0) > 0.0
            ]
            weights: Dict[str, float] = {}
            for wc in contributions:
                w = str(wc.get("word") or "").strip().lower()
                if not w:
                    continue
                weights[w] = weights.get(w, 0.0) + float(wc.get("contribution") or 0.0)
            occ = _scan_file_for_words(
                path=path,
                words=signal_words or (r.get("matching_words") or []),
                max_occurrences=int(preview_occurrences),
                word_weights=weights or None,
            )
            if occ:
                r["occurrences"] = occ
                r["signal_words"] = signal_words

    return {
        "query_words": query_words,
        "files_found": len(results),
        "results": results,
    }


def map_file(path: Path) -> Dict:
    """
    Return a compact file outline.

    - Python: AST-based (classes/functions with line ranges)
    - Other: heuristic scan for signature lines in first 200 lines
    """
    path = Path(path)
    if not path.exists():
        return {"error": f"File not found: {path}"}
    if not path.is_file():
        return {"error": f"Not a file: {path}"}

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"error": f"Error reading file: {e}"}

    lines_total = len(content.splitlines())
    out: Dict = {
        "path": str(path),
        "name": path.name,
        "suffix": path.suffix,
        "lines_total": lines_total,
        "items": [],
    }

    if path.suffix == ".py":
        try:
            tree = ast.parse(content)
            items: List[Dict] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    items.append(
                        {
                            "type": "function",
                            "name": node.name,
                            "line": int(getattr(node, "lineno", 0) or 0),
                            "end_line": int(getattr(node, "end_lineno", 0) or getattr(node, "lineno", 0) or 0),
                        }
                    )
                elif isinstance(node, ast.AsyncFunctionDef):
                    items.append(
                        {
                            "type": "async_function",
                            "name": node.name,
                            "line": int(getattr(node, "lineno", 0) or 0),
                            "end_line": int(getattr(node, "end_lineno", 0) or getattr(node, "lineno", 0) or 0),
                        }
                    )
                elif isinstance(node, ast.ClassDef):
                    items.append(
                        {
                            "type": "class",
                            "name": node.name,
                            "line": int(getattr(node, "lineno", 0) or 0),
                            "end_line": int(getattr(node, "end_lineno", 0) or getattr(node, "lineno", 0) or 0),
                        }
                    )
            items.sort(key=lambda x: (x.get("line") or 0, x.get("type") or "", x.get("name") or ""))
            out["items"] = items
            out["language"] = "python"
            return out
        except SyntaxError as e:
            out["language"] = "python"
            out["parse_error"] = str(e)
            # Fall through to heuristic below.

    # Heuristic outline (first N lines).
    out["language"] = "text"
    sig_prefixes = ("def ", "class ", "async def ", "function ", "const ", "let ", "var ")
    items: List[Dict] = []
    for i, line in enumerate(content.splitlines()[:200], 1):
        stripped = line.strip()
        if not stripped.startswith(sig_prefixes):
            continue
        items.append({"type": "signature", "name": stripped[:80], "line": i, "end_line": i})
    out["items"] = items
    return out
