"""Tests for minor additions to existing sessions."""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab


# ── Task 8: Guardrails ────────────────────────────────────────────────────────

def test_guardrails_check_blocks_invalid():
    """guardrails_check raises ValueError when validation_passed is False."""
    mock_guard = MagicMock()
    mock_guard.validate.return_value = MagicMock(validation_passed=False, error="blocked")
    with patch("langchain_anthropic.ChatAnthropic"):
        lab = load_lab("10_guardrails")
        with pytest.raises(ValueError, match="blocked"):
            lab.guardrails_check("bad input", mock_guard)


def test_guardrails_check_passes_valid():
    """guardrails_check returns the original text when validation passes."""
    mock_guard = MagicMock()
    mock_guard.validate.return_value = MagicMock(validation_passed=True)
    with patch("langchain_anthropic.ChatAnthropic"):
        lab = load_lab("10_guardrails")
        result = lab.guardrails_check("valid input", mock_guard)
    assert result == "valid input"


# ── Task 9: HyDE ──────────────────────────────────────────────────────────────

def test_hyde_retrieve_calls_llm_then_vectorstore():
    """hyde_retrieve generates a hypothetical answer then searches the vectorstore."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Photosynthesis converts sunlight to glucose.")]
    )
    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search.return_value = [MagicMock(page_content="doc")]
    with patch("anthropic.Anthropic", return_value=mock_client):
        lab = load_lab("22_hybrid_rag")
        results = lab.hyde_retrieve("What is photosynthesis?", mock_vectorstore, mock_client)
    mock_client.messages.create.assert_called_once()
    mock_vectorstore.similarity_search.assert_called_once()
    assert len(results) >= 1


# ── Task 10: Langfuse ─────────────────────────────────────────────────────────

def test_trace_with_langfuse_returns_trace_id():
    """trace_with_langfuse logs a Q&A pair and returns the trace ID."""
    mock_langfuse = MagicMock()
    mock_trace = MagicMock()
    mock_trace.id = "trace-abc-123"
    mock_langfuse.trace.return_value = mock_trace
    with patch("langchain_anthropic.ChatAnthropic"):
        lab = load_lab("25_evaluation")
        trace_id = lab.trace_with_langfuse("test question", "test answer", mock_langfuse)
    assert trace_id == "trace-abc-123"
    mock_langfuse.trace.assert_called_once()


# ── Task 11: Parallel tool calls ──────────────────────────────────────────────

def test_dispatch_tools_parallel_calls_all():
    """dispatch_tools_parallel returns one result dict per tool_use block."""
    mock_block_1 = MagicMock()
    mock_block_1.type = "tool_use"
    mock_block_1.id = "t1"
    mock_block_1.name = "add"
    mock_block_1.input = {"a": 1, "b": 2}
    mock_block_2 = MagicMock()
    mock_block_2.type = "tool_use"
    mock_block_2.id = "t2"
    mock_block_2.name = "get_current_time"
    mock_block_2.input = {}
    with patch("langchain_anthropic.ChatAnthropic"):
        lab = load_lab("03_agent_manual")
        results = lab.dispatch_tools_parallel([mock_block_1, mock_block_2])
    assert len(results) == 2
    assert all("tool_use_id" in r for r in results)
