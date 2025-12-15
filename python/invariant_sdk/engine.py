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
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .halo import hash8_hex
from .overlay import OverlayEdge, OverlayGraph
from .tokenize import dedupe_preserve_order, tokenize_simple


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

    @classmethod
    def build(cls, overlay: OverlayGraph) -> "OverlayIndex":
        incoming: Dict[str, List[Tuple[str, OverlayEdge]]] = {}
        known_hashes: set[str] = set(overlay.edges.keys())
        doc_edges: Dict[str, int] = {}
        doc_nodes: Dict[str, set[str]] = {}

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

        return cls(incoming=incoming, doc_stats=doc_stats, known_hashes=known_hashes, label_to_hash=label_to_hash)


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
    max_line_len: int = 200,
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
    if not needles:
        return []

    out: List[Dict] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        lower = line.lower()
        hits = [n for n in needles if n in lower]
        if not hits:
            continue
        out.append(
            {
                "line": line_no,
                "content": line.rstrip()[:max_line_len],
                "matches": hits[:8],
            }
        )
        if len(out) >= max_occurrences:
            break
    return out


def locate_files(
    issue_text: str,
    *,
    overlay: OverlayGraph,
    index: Optional[OverlayIndex] = None,
    doc_filter: str = "",
    max_results: int = 0,
    preview_files: int = 8,
    preview_occurrences: int = 6,
    resolve_doc_path: Optional[Callable[[str], Optional[Path]]] = None,
) -> Dict:
    """
    File discovery from issue text, using only σ-overlay.

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

    # Build query hashes (deterministic, overlay-compatible).
    word_hashes: Dict[str, str] = {}
    for w in query_words:
        word_hashes[w] = _resolve_query_hash(w, overlay=overlay, index=idx)

    file_scores: Dict[str, Dict] = {}  # doc -> {words:set, lines:set}

    def _touch(doc: str, word: str, line: Optional[int]) -> None:
        if not doc:
            return
        if doc_filter and doc != doc_filter:
            return
        entry = file_scores.get(doc)
        if entry is None:
            entry = {"words": set(), "lines": set()}
            file_scores[doc] = entry
        entry["words"].add(word)
        if line:
            entry["lines"].add(int(line))

    # Outgoing (word is src)
    for word, h8 in word_hashes.items():
        for edge in overlay.edges.get(h8, []):
            if not edge.doc:
                continue
            _touch(edge.doc, word, edge.line)

    # Incoming (word is tgt)
    for word, h8 in word_hashes.items():
        for _src, edge in idx.incoming.get(h8, []):
            if not edge.doc:
                continue
            _touch(edge.doc, word, edge.line)

    # Rank: deterministic and simple (bits per unique match).
    ranked: List[Tuple[str, Dict]] = []
    for doc, info in file_scores.items():
        matches = sorted(info["words"])
        ranked.append(
            (
                doc,
                {
                    "file": doc,
                    "n_matches": len(matches),
                    "matching_words": matches,
                    "candidate_lines": sorted(info["lines"])[:12],
                    "score": 2 ** len(matches),
                },
            )
        )
    ranked.sort(key=lambda x: (-int(x[1]["score"]), x[0].lower()))

    # Apply max_results (0 = "all").
    results: List[Dict] = []
    for doc, info in ranked:
        if info["score"] <= 1:
            continue
        if max_results > 0 and len(results) >= max_results:
            break
        results.append(info)

    # Preview occurrences for top files (bounded file reads).
    if resolve_doc_path:
        for i, r in enumerate(results[: max(0, int(preview_files))]):
            path = resolve_doc_path(r["file"])
            if not path:
                continue
            occ = _scan_file_for_words(
                path=path,
                words=r.get("matching_words") or [],
                max_occurrences=int(preview_occurrences),
            )
            if occ:
                r["occurrences"] = occ

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

