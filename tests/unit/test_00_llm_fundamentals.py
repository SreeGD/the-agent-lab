"""Tests for labs/00_llm_fundamentals.py."""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.messages.count_tokens.return_value = MagicMock(input_tokens=5)
    return client


def test_visualize_tokens_contains_total(mock_client):
    """visualize_tokens output must contain the API token count."""
    lab = load_lab("00_llm_fundamentals")
    result = lab.visualize_tokens("Hello world", mock_client)
    assert "5" in result  # total token count present


def test_visualize_tokens_returns_string(mock_client):
    """visualize_tokens must return a str."""
    lab = load_lab("00_llm_fundamentals")
    result = lab.visualize_tokens("Hello", mock_client)
    assert isinstance(result, str)


def test_fill_percentage_range(mock_client):
    """fill_percentage must return a value between 0 and 1."""
    mock_client.messages.count_tokens.return_value = MagicMock(input_tokens=100)
    lab = load_lab("00_llm_fundamentals")
    pct = lab.fill_percentage("Some text", mock_client, "claude-sonnet-4-6", 200_000)
    assert 0.0 <= pct <= 1.0


def test_fill_percentage_math(mock_client):
    """fill_percentage should equal input_tokens / max_tokens."""
    mock_client.messages.count_tokens.return_value = MagicMock(input_tokens=1000)
    lab = load_lab("00_llm_fundamentals")
    pct = lab.fill_percentage("x", mock_client, "claude-sonnet-4-6", 200_000)
    assert abs(pct - 0.005) < 1e-9


def test_benchmark_table_structure():
    """benchmark_table rows must have model, mmlu, humaneval keys."""
    lab = load_lab("00_llm_fundamentals")
    rows = lab.benchmark_table()
    assert len(rows) >= 3
    for row in rows:
        assert "model" in row
        assert "mmlu" in row
        assert "humaneval" in row
        assert "lmsys_rank" in row


def test_benchmark_table_no_api_call():
    """benchmark_table must not call any API — it takes no client argument."""
    lab = load_lab("00_llm_fundamentals")
    import inspect

    sig = inspect.signature(lab.benchmark_table)
    # Hardcoded function takes zero parameters
    assert len(sig.parameters) == 0
    rows = lab.benchmark_table()
    assert isinstance(rows, list)


def test_sample_temperatures_length(mock_client):
    """sample_temperatures returns one entry per temperature value."""
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="response")]
    )
    lab = load_lab("00_llm_fundamentals")
    results = lab.sample_temperatures("Say one word", mock_client, [0.0, 0.7, 1.2])
    assert len(results) == 3
    assert all("temperature" in r and "output" in r for r in results)


def test_sample_temperatures_values(mock_client):
    """sample_temperatures preserves the temperature values in the output."""
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="ok")]
    )
    lab = load_lab("00_llm_fundamentals")
    temps = [0.0, 0.5]
    results = lab.sample_temperatures("ping", mock_client, temps)
    assert results[0]["temperature"] == 0.0
    assert results[1]["temperature"] == 0.5
