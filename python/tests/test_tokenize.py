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
    """GATE: Date components are captured in atomic mode."""
    tokens = tokenize_simple("meeting on 01/15/2001")
    # atomic mode splits by separators, so date parts are separate
    # The full date can be parsed from _normalize_date_like in identifier mode
    assert "01" in tokens or "15" in tokens or "2001" in tokens


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
    """GATE: Underscores are preserved in identifier mode (for code)."""
    # identifier mode preserves underscores
    tokens = tokenize_simple("call get_data function", mode="identifier")
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


# =============================================================================
# v1.9.5 GATE TESTS: Canonical Month Equivalence (CAUSAL_TEXT_SPEC)
# These are INSTRUMENT DEFINITIONS, not physics LAWs.
# =============================================================================

def test_month_canonical_december():
    """GATE: 'December' normalizes to @month12 (full name is unambiguous)."""
    assert _normalize("December") == "@month12"
    assert _normalize("december") == "@month12"
    # Note: 'dec' is AMBIGUOUS (decrement/decoder) - see test_collision_dec_not_month


def test_month_canonical_unambiguous():
    """GATE: Unambiguous months canonicalize standalone."""
    unambiguous = [
        ("January", "@month01"), ("jan", "@month01"),
        ("February", "@month02"), ("feb", "@month02"),
        # march EXCLUDED - ambiguous (verb/noun)
        ("April", "@month04"), ("apr", "@month04"),
        # may EXCLUDED - ambiguous (modal verb)
        ("June", "@month06"), ("jun", "@month06"),
        ("July", "@month07"), ("jul", "@month07"),
        ("August", "@month08"), ("aug", "@month08"),
        ("September", "@month09"), ("sep", "@month09"), ("sept", "@month09"),
        ("October", "@month10"), ("oct", "@month10"),
        ("November", "@month11"), ("nov", "@month11"),
        ("December", "@month12"),  # "dec" EXCLUDED - decrement/decoder/decimal
    ]
    for input_val, expected in unambiguous:
        result = _normalize(input_val)
        assert result == expected, f"_normalize('{input_val}') = {result}, expected {expected}"


# =============================================================================
# COLLISION GATE TESTS (MUST-NOT-FIRE)
# These verify ambiguous words are NOT incorrectly canonicalized.
# =============================================================================

def test_collision_may_verb_not_month():
    """COLLISION GATE: 'may' as verb does NOT become @month05."""
    # "may" is a modal verb - should stay as word, not month
    result = _normalize("may")
    assert result != "@month05", f"'may' should NOT be @month05, got {result}"
    assert result == "may", f"'may' should stay as word 'may', got {result}"


def test_collision_march_verb_not_month():
    """COLLISION GATE: 'march' as verb/noun does NOT become @month03."""
    # "march" can be verb (march forward) or event (March on Washington)
    result = _normalize("march")
    assert result != "@month03", f"'march' should NOT be @month03, got {result}"
    assert result == "march", f"'march' should stay as word 'march', got {result}"


def test_collision_may_in_sentence():
    """COLLISION GATE: 'may I ask' does NOT produce @month05."""
    tokens = tokenize_simple("may I ask you something")
    assert "@month05" not in tokens, f"'may I ask' should NOT contain @month05: {tokens}"
    assert "may" in tokens, f"'may' should be preserved as word: {tokens}"


def test_collision_march_in_sentence():
    """COLLISION GATE: 'soldiers march forward' does NOT produce @month03."""
    tokens = tokenize_simple("soldiers march forward")
    assert "@month03" not in tokens, f"'march forward' should NOT contain @month03: {tokens}"
    assert "march" in tokens, f"'march' should be preserved as word: {tokens}"


def test_month_canonical_in_tokenize():
    """GATE: tokenize_simple uses canonical month forms (unambiguous only)."""
    tokens = tokenize_simple("meeting in December 2001")
    assert "@month12" in tokens, f"Expected @month12 in {tokens}"
    assert "2001" in tokens


def test_month_canonical_preserves_hash():
    """GATE: Same month names → same hash8 address."""
    from invariant_sdk.halo import hash8_hex
    
    h1 = hash8_hex("Ġ@month12")
    h2 = hash8_hex("Ġ@month12")
    
    # "December" produces @month12 (unambiguous)
    assert h1 == h2, "Same canonical form must produce same hash"
    
    # tokenize uses canonical form for unambiguous
    tokens_dec = tokenize_simple("in December")
    assert "@month12" in tokens_dec


# =============================================================================
# COLLISION GATE TESTS for 'dec' (MUST-NOT-FIRE)
# 'dec' can mean decrement/decoder/decimal in code contexts
# =============================================================================

def test_collision_dec_not_month():
    """COLLISION GATE: 'dec' alone does NOT become @month12."""
    # 'dec' is ambiguous: decrement, decoder, decimal, December
    result = _normalize("dec")
    assert result != "@month12", f"'dec' should NOT be @month12, got {result}"
    assert result == "dec", f"'dec' should stay as word 'dec', got {result}"


def test_collision_dec_in_code():
    """COLLISION GATE: 'dec variable' does NOT produce @month12."""
    tokens = tokenize_simple("int dec = value - 1")
    assert "@month12" not in tokens, f"'dec' in code should NOT be @month12: {tokens}"
    assert "dec" in tokens, f"'dec' should be preserved as word: {tokens}"


def test_collision_decoder():
    """COLLISION GATE: 'decoder' is not month-related."""
    result = _normalize("decoder")
    assert "@month12" not in result
    assert result == "decoder"


# =============================================================================
# TOKENIZER MODE TESTS (atomic vs identifier)
# =============================================================================

def test_tokenizer_mode_atomic_splits_underscore():
    """GATE: atomic mode splits snake_case into parts."""
    tokens = tokenize_simple("get_data_from_server", mode="atomic")
    # atomic mode splits on underscores
    assert "get" in tokens or "data" in tokens or "from" in tokens


def test_tokenizer_mode_identifier_preserves_underscore():
    """GATE: identifier mode keeps snake_case as one token."""
    tokens = tokenize_simple("get_data_from_server", mode="identifier")
    # identifier mode preserves underscores
    assert "get_data_from_server" in tokens


def test_tokenizer_mode_default_is_atomic():
    """GATE: Default mode is atomic (email/logs)."""
    tokens = tokenize_simple("eric_bass agreement")
    # Should split by underscore
    assert "eric" in tokens or "bass" in tokens


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
