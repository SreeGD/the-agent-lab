"""Tests for labs/00_llm_fundamentals.py."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

LAB_PATH = Path("/Users/srmallip/projects/AgenticCourse/labs/00_llm_fundamentals.py")


def _load_lab():
    """Load the lab module fresh, bypassing any cached import."""
    mod_name = "llm_fundamentals_00"
    sys.modules.pop(mod_name, None)
    spec = importlib.util.spec_from_file_location(mod_name, LAB_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.messages.count_tokens.return_value = MagicMock(input_tokens=5)
    return client


def test_visualize_tokens_contains_total(mock_client):
    """visualize_tokens output must contain the API token count."""
    lab = _load_lab()
    result = lab.visualize_tokens("Hello world", mock_client)
    assert "5" in result  # total token count present


def test_visualize_tokens_returns_string(mock_client):
    """visualize_tokens must return a str."""
    lab = _load_lab()
    result = lab.visualize_tokens("Hello", mock_client)
    assert isinstance(result, str)


def test_fill_percentage_range(mock_client):
    """fill_percentage must return a value between 0 and 1."""
    mock_client.messages.count_tokens.return_value = MagicMock(input_tokens=100)
    lab = _load_lab()
    pct = lab.fill_percentage("Some text", mock_client, "claude-sonnet-4-6", 200_000)
    assert 0.0 <= pct <= 1.0


def test_fill_percentage_math(mock_client):
    """fill_percentage should equal input_tokens / max_tokens."""
    mock_client.messages.count_tokens.return_value = MagicMock(input_tokens=1000)
    lab = _load_lab()
    pct = lab.fill_percentage("x", mock_client, "claude-sonnet-4-6", 200_000)
    assert abs(pct - 0.005) < 1e-9


def test_benchmark_table_structure():
    """benchmark_table rows must have model, mmlu, humaneval keys."""
    lab = _load_lab()
    rows = lab.benchmark_table()
    assert len(rows) >= 3
    for row in rows:
        assert "model" in row
        assert "mmlu" in row
        assert "humaneval" in row
        assert "lmsys_rank" in row


def test_benchmark_table_no_api_call():
    """benchmark_table must not call any API — it takes no client argument."""
    lab = _load_lab()
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
    lab = _load_lab()
    results = lab.sample_temperatures("Say one word", mock_client, [0.0, 0.7, 1.2])
    assert len(results) == 3
    assert all("temperature" in r and "output" in r for r in results)


def test_sample_temperatures_values(mock_client):
    """sample_temperatures preserves the temperature values in the output."""
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="ok")]
    )
    lab = _load_lab()
    temps = [0.0, 0.5]
    results = lab.sample_temperatures("ping", mock_client, temps)
    assert results[0]["temperature"] == 0.0
    assert results[1]["temperature"] == 0.5
