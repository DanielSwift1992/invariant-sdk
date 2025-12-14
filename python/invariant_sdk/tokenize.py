"""
tokenize.py — Deterministic surface tokenization

This module intentionally implements a small, deterministic tokenizer for:
  - issue text (locate)
  - document ingestion (ingest)
  - provenance hashing windows (ctx_hash)

Important: do NOT use `\\b...\\b` word-boundaries for code identifiers.
Regex `\\b` treats `_` as a word-char, so snake_case like `separability_matrix`
would produce zero matches with patterns like `\\b[a-zA-Z]{3,}\\b`.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple


# "Identifier-ish" surface tokens: letters/digits/underscore, length >= 3.
# We normalize (lowercase + strip edge underscores) and require ≥1 letter.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}")


def _normalize(raw: str) -> str | None:
    token = raw.strip("_").lower()
    if len(token) < 3:
        return None
    if not any("a" <= c <= "z" for c in token):
        return None
    return token


def tokenize_simple(text: str) -> List[str]:
    """Extract normalized tokens from arbitrary text (may include duplicates)."""
    out: List[str] = []
    for m in _TOKEN_RE.finditer(text):
        token = _normalize(m.group(0))
        if token:
            out.append(token)
    return out


def dedupe_preserve_order(tokens: Iterable[str]) -> List[str]:
    """Deduplicate tokens while preserving first-seen order."""
    seen = set()
    out: List[str] = []
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def tokenize_with_lines(text: str) -> List[Tuple[str, int]]:
    """Tokenize text and attach 1-based line numbers: [(token, line), ...]."""
    out: List[Tuple[str, int]] = []
    for line_num, line in enumerate(text.split("\n"), 1):
        for m in _TOKEN_RE.finditer(line):
            token = _normalize(m.group(0))
            if token:
                out.append((token, line_num))
    return out


def tokenize_with_positions(text: str) -> List[Tuple[str, int, int, int]]:
    """
    Tokenize text with coarse character offsets.

    Returns: [(token, line, char_start, char_end), ...]
    """
    out: List[Tuple[str, int, int, int]] = []
    char_offset = 0
    for line_num, line in enumerate(text.split("\n"), 1):
        for m in _TOKEN_RE.finditer(line):
            token = _normalize(m.group(0))
            if not token:
                continue
            out.append((token, line_num, char_offset + m.start(), char_offset + m.end()))
        char_offset += len(line) + 1
    return out

