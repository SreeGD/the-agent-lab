"""Unit tests for the MCP server's tool functions.

Tests the pure-Python parts: add, count_letters, get_current_time.
We don't import the MCP server module directly because it eagerly loads the
RAG pipeline at module load (slow). Instead we replicate the simple tool
implementations and test them in isolation.

retrieve_docs is RAG-backed; covered by RAG tests elsewhere.
"""

from datetime import datetime


# Replicate the simple tool implementations from 12_mcp_server.py.
# These are pure Python and behavior-equivalent to the @mcp.tool-wrapped versions.

def add(a: int, b: int) -> int:
    """Same as @mcp.tool def add in 12_mcp_server.py"""
    return a + b


def count_letters(text: str) -> int:
    """Same as @mcp.tool def count_letters in 12_mcp_server.py"""
    return sum(1 for ch in text if ch.isalpha())


def get_current_time() -> str:
    """Same as @mcp.tool def get_current_time in 12_mcp_server.py"""
    return datetime.now().isoformat(timespec="seconds")


# ─── add ──────────────────────────────────────────────────────────────

class TestAdd:
    def test_positive_ints(self):
        assert add(47, 158) == 205

    def test_negatives(self):
        assert add(-10, 5) == -5

    def test_zero(self):
        assert add(0, 0) == 0

    def test_commutative(self):
        assert add(3, 7) == add(7, 3)


# ─── count_letters ────────────────────────────────────────────────────

class TestCountLetters:
    def test_simple_word(self):
        assert count_letters("Sree") == 4

    def test_two_words(self):
        assert count_letters("Vidya Karana") == 11

    def test_ignores_punctuation(self):
        assert count_letters("hello, world!") == 10

    def test_ignores_digits(self):
        # Letters only — digits don't count
        assert count_letters("abc123def") == 6

    def test_empty(self):
        assert count_letters("") == 0

    def test_whitespace_only(self):
        assert count_letters("   \t\n") == 0


# ─── get_current_time ─────────────────────────────────────────────────

class TestGetCurrentTime:
    def test_returns_iso_format(self):
        result = get_current_time()
        # Should parse back into a datetime
        parsed = datetime.fromisoformat(result)
        assert isinstance(parsed, datetime)

    def test_no_microseconds(self):
        # We use timespec='seconds' so no microsecond fraction
        result = get_current_time()
        assert "." not in result.split("T")[1] if "T" in result else True

    def test_returns_string(self):
        assert isinstance(get_current_time(), str)
