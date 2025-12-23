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
from typing import Iterable, List, Literal, Tuple

# DEFINITION: Two tokenizer modes (measurement instrument choice)
# This is NOT multiple "profiles" — it's two classes of measurement.
TokenizerMode = Literal["atomic", "identifier"]


# "Identifier-ish" surface tokens: letters/digits/underscore, length >= 2.
# v1.8: Also captures numeric IDs and dates.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]{2,}")

# Date-like pattern: 2-3 groups of digits separated by / - or .
_DATE_PATTERN = re.compile(r"^(\d{1,4})[\-/.](\d{1,2})[\-/.](\d{1,4})$")

# =============================================================================
# DEFINITION: Canonical Equivalence Classes (CAUSAL_TEXT_SPEC)
# These are INSTRUMENT DEFINITIONS, not physics LAWs.
# They must be date-context gated for ambiguous tokens.
# =============================================================================

# UNAMBIGUOUS months: Safe to canonicalize as standalone tokens.
# These words are almost exclusively month references.
_MONTH_CANONICAL_SAFE = {
    "january": "@month01", "jan": "@month01",
    "february": "@month02", "feb": "@month02",
    # "march" EXCLUDED - also a verb/noun (march forward)
    # "mar" - too short/ambiguous
    "april": "@month04", "apr": "@month04",
    # "may" EXCLUDED - modal verb (may I ask)
    "june": "@month06", "jun": "@month06",
    "july": "@month07", "jul": "@month07",
    "august": "@month08", "aug": "@month08",
    "september": "@month09", "sep": "@month09", "sept": "@month09",
    "october": "@month10", "oct": "@month10",
    "november": "@month11", "nov": "@month11",
    "december": "@month12",  # "dec" EXCLUDED - decrement/decoder/decimal
}

# AMBIGUOUS months: Only canonicalize in DATE CONTEXT.
# These require adjacent year/day to be treated as months.
_MONTH_AMBIGUOUS = {
    "march": "@month03", "mar": "@month03",
    "may": "@month05",
    "dec": "@month12",  # Can be decrement/decoder/decimal in code
}



def _normalize_date_like(token: str) -> str | None:
    """
    Normalize date-like tokens to consistent YYYYMMDD format.
    
    Handles:
      - MM/DD/YYYY → YYYYMMDD
      - YYYY-MM-DD → YYYYMMDD
      - M/D/YYYY → YYYYMMDD (with padding)
    
    Returns None if not a date-like token.
    """
    m = _DATE_PATTERN.match(token)
    if not m:
        return None
    
    g1, g2, g3 = m.group(1), m.group(2), m.group(3)
    
    # Determine format: YYYY-MM-DD vs MM/DD/YYYY
    if len(g1) == 4:
        # YYYY-MM-DD format
        year, month, day = g1, g2, g3
    elif len(g3) == 4:
        # MM/DD/YYYY or DD/MM/YYYY format
        # Assume MM/DD/YYYY (US format common in Enron)
        month, day, year = g1, g2, g3
    else:
        # Ambiguous, just join with padding
        return f"{g1.zfill(2)}{g2.zfill(2)}{g3.zfill(2)}"
    
    # Canonical: YYYYMMDD
    return f"{year}{month.zfill(2)}{day.zfill(2)}"


def _normalize(raw: str) -> str | None:
    """
    Normalize token for indexing.
    
    v1.9.5: Supports token types with canonical equivalence classes:
      - DATE_LIKE: recognized dates → YYYYMMDD (e.g., "1/5/2001" → "20010105")
      - MONTH: month names → @month01..@month12 (e.g., "December" → "@month12")
      - PURE_NUM: digits only, length >= 2 (e.g., "258505")
      - ALNUM_ID: mixed letters+digits, length >= 3 (e.g., "FERC123")
      - WORD: letters only, length >= 3 (e.g., "deal")
    """
    token = raw.lower()
    
    # Strip common separators from edges
    token = token.strip(".-/_")
    
    if not token:
        return None
    
    # Check for date-like pattern FIRST (before stripping separators)
    date_result = _normalize_date_like(token)
    if date_result:
        return date_result
    
    # DEFINITION: Canonical month equivalence (INSTRUMENT, not LAW)
    # Only UNAMBIGUOUS months canonicalize standalone.
    # Ambiguous months (may, march) require date context.
    if token in _MONTH_CANONICAL_SAFE:
        return _MONTH_CANONICAL_SAFE[token]
    
    has_alpha = any("a" <= c <= "z" for c in token)
    has_digit = any(c.isdigit() for c in token)
    
    # PURE_NUM: only digits (after cleaning separators), length >= 2
    digits_only = "".join(c for c in token if c.isdigit())
    if not has_alpha and has_digit and len(digits_only) >= 2:
        return digits_only  # Canonical form: just digits
    
    # ALNUM_ID: both letters and digits, length >= 3
    alnum_only = "".join(c for c in token if c.isalnum() or c == "_")
    if has_alpha and has_digit and len(alnum_only) >= 3:
        return alnum_only
    
    # WORD: letters only (may have underscore), length >= 3
    if has_alpha and len(token) >= 3:
        return token
    
    return None


def normalize_for_hash(text: str) -> str:
    """
    Normalize text for ctx_hash and dt calculation.
    
    MUST match operators.py:normalize_text() exactly!
    Uses lowercase + strip punctuation + whitespace collapse.
    
    This shared normalization ensures:
      - ctx_hash is stable under edits
      - dt calculation is consistent with ctx_hash
    """
    text = text.lower()
    # Remove all non-word, non-space characters
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.split())


def tokenize_simple(text: str, mode: TokenizerMode = "atomic") -> List[str]:
    """
    Extract normalized tokens from arbitrary text (may include duplicates).
    
    Args:
        text: Input text to tokenize
        mode: Tokenizer mode (DEFINITION, not POLICY)
            - "atomic": Split by [_./-] — for email, logs, prose
            - "identifier": Preserve _ in tokens — for code repositories
    
    Note: ingest and query MUST use the same mode to avoid split-brain.
    """
    out: List[str] = []
    
    # Mode-specific regex (DEFINITION, not POLICY)
    if mode == "identifier":
        # Preserve underscores as part of identifiers (for code)
        pattern = re.compile(r"[A-Za-z0-9_]{2,}")
    else:
        # Atomic mode: split by separators including underscore (for email/logs)
        # This splits snake_case into parts: get_data → [get, data]
        pattern = re.compile(r"[A-Za-z0-9]{2,}")
    
    for m in pattern.finditer(text):
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

