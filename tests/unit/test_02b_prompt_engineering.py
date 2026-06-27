"""Tests for labs/02b_prompt_engineering.py."""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab


def _mock_client():
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="4")],
        usage=MagicMock(input_tokens=100, output_tokens=10),
    )
    return client


def test_run_strategy_returns_required_keys():
    with patch("anthropic.Anthropic"):
        lab = load_lab("02b_prompt_engineering")
        result = lab.run_strategy("Classify sentiment", "zero_shot", _mock_client())
    assert {"strategy", "output", "input_tokens", "output_tokens", "cost_usd"} <= result.keys()


def test_all_strategies_covered():
    with patch("anthropic.Anthropic"):
        lab = load_lab("02b_prompt_engineering")
        for strategy in lab.STRATEGIES:
            result = lab.run_strategy("test task", strategy, _mock_client())
            assert result["strategy"] == strategy


def test_score_output_returns_int_in_range():
    with patch("anthropic.Anthropic"):
        lab = load_lab("02b_prompt_engineering")
        score = lab.score_output("task", "output text", _mock_client())
    assert isinstance(score, int)
    assert 1 <= score <= 5
