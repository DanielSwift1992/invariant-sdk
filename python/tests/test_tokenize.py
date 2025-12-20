"""
test_tokenize.py — Tests for v1.8 numeric observability

Gate tests for σ-presence wins on ALL token types:
- PURE_NUM: 258505, 2001
- DATE_LIKE: 01/15/2001 → 20010115 (YYYYMMDD canonical)
- ALNUM_ID: FERC123, EOL2001
- WORD: deal, agreement
"""

import pytest
from invariant_sdk.tokenize import tokenize_simple, _normalize


# =============================================================================
# P0 GATE TESTS: Numeric Observability
# =============================================================================

def test_numeric_token_kept():
    """GATE: Pure numeric tokens are indexed."""
    tokens = tokenize_simple("deal 258505 closes")
    assert "258505" in tokens, f"258505 not found in {tokens}"


def test_date_normalized():
    """GATE: Date-like tokens are normalized to YYYYMMDD."""
    tokens = tokenize_simple("meeting on 01/15/2001")
    # v1.8.1: YYYYMMDD canonical format
    assert "20010115" in tokens, f"20010115 not found in {tokens}"


def test_year_kept():
    """GATE: 4-digit years are indexed."""
    tokens = tokenize_simple("in 2001 we")
    assert "2001" in tokens, f"2001 not found in {tokens}"


def test_single_digit_dropped():
    """GATE: Single digits are too short to index."""
    tokens = tokenize_simple("version 2 is ok")
    assert "2" not in tokens, f"2 should NOT be in {tokens}"


def test_alnum_id_kept():
    """GATE: Alphanumeric IDs are indexed."""
    tokens = tokenize_simple("FERC123 filing")
    assert "ferc123" in tokens, f"ferc123 not found in {tokens}"


def test_eol_id_kept():
    """GATE: Common Enron IDs like EOL2001 are indexed."""
    tokens = tokenize_simple("EOL2001 trade")
    assert "eol2001" in tokens, f"eol2001 not found in {tokens}"


def test_word_still_works():
    """GATE: Regular words still work."""
    tokens = tokenize_simple("deal agreement")
    assert "deal" in tokens
    assert "agreement" in tokens


def test_short_word_dropped():
    """GATE: Words < 3 chars are dropped."""
    tokens = tokenize_simple("is it ok")
    assert "is" not in tokens
    assert "it" not in tokens
    assert "ok" not in tokens  # "ok" is only 2 chars


def test_underscore_preserved():
    """GATE: Underscores are preserved for code identifiers."""
    tokens = tokenize_simple("call get_data function")
    assert "get_data" in tokens


# =============================================================================
# UNIT TESTS: _normalize function
# =============================================================================

def test_normalize_pure_num():
    """PURE_NUM: digits only → returned as-is."""
    assert _normalize("258505") == "258505"
    assert _normalize("2001") == "2001"


def test_normalize_date():
    """DATE_LIKE: normalized to YYYYMMDD."""
    assert _normalize("01/15/2001") == "20010115"  # MM/DD/YYYY → YYYYMMDD
    assert _normalize("2001-01-15") == "20010115"  # YYYY-MM-DD → YYYYMMDD


def test_date_format_consistency():
    """GATE: Different date formats normalize to SAME surface-class."""
    # This is the key fix: 1/5/2001 vs 01/05/2001 must be identical
    assert _normalize("1/5/2001") == _normalize("01/05/2001"), \
        "Date format inconsistency: 1/5/2001 vs 01/05/2001"
    
    # ISO vs US format for same date
    assert _normalize("2001-01-05") == _normalize("01/05/2001"), \
        "Date format inconsistency: ISO vs US"


def test_normalize_alnum():
    """ALNUM_ID: lowercase, separators cleaned."""
    assert _normalize("FERC123") == "ferc123"
    assert _normalize("EOL-2001") == "eol2001"


def test_normalize_word():
    """WORD: standard lowercase."""
    assert _normalize("Deal") == "deal"
    assert _normalize("AGREEMENT") == "agreement"


def test_normalize_rejects_short():
    """Short tokens rejected."""
    assert _normalize("1") is None  # Single digit
    assert _normalize("ab") is None  # 2 chars word


# =============================================================================
# v1.9.2: Edge case tokenization tests (Enron patterns)
# =============================================================================

def test_tokenize_hash_prefixed_id():
    """GATE: #258505 tokenizes to 258505 (hash stripped)."""
    from invariant_sdk.tokenize import tokenize_simple
    
    words = tokenize_simple("#258505 is the deal")
    
    # 258505 should be captured (hash is not part of token regex)
    assert "258505" in words, f"#ID should tokenize to ID: {words}"


def test_tokenize_hyphenated_id():
    """GATE: deal-258505 tokenizes to components or combined."""
    from invariant_sdk.tokenize import tokenize_simple
    
    words = tokenize_simple("deal-258505 agreement")
    
    # Either deal258505 combined OR separate deal + 258505
    has_combined = "deal258505" in words
    has_separate = "deal" in words and "258505" in words
    
    assert has_combined or has_separate, (
        f"Hyphenated ID should be captured: {words}"
    )



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
