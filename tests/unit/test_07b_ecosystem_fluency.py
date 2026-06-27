"""Tests for labs/07b_ecosystem_fluency.py."""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab


def test_search_hf_models_returns_list():
    mock_api = MagicMock()
    mock_api.list_models.return_value = [
        MagicMock(modelId="meta-llama/Llama-3-8B", downloads=100000, tags=["text-generation"]),
    ]
    with patch("huggingface_hub.HfApi", return_value=mock_api):
        lab = load_lab("07b_ecosystem_fluency")
        results = lab.search_hf_models("text-generation", limit=1)
    assert isinstance(results, list)
    assert results[0]["model_id"] == "meta-llama/Llama-3-8B"


def test_benchmark_scores_known_model():
    with patch("huggingface_hub.HfApi"):
        lab = load_lab("07b_ecosystem_fluency")
        row = lab.benchmark_scores("gpt-4o", lab.BENCHMARK_REFERENCE)
    assert row is not None and "mmlu" in row


def test_benchmark_scores_unknown_model():
    with patch("huggingface_hub.HfApi"):
        lab = load_lab("07b_ecosystem_fluency")
        row = lab.benchmark_scores("not-a-real-model", lab.BENCHMARK_REFERENCE)
    assert row is None


def test_provider_shootout_structure():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="response"))]
    with patch("litellm.completion", return_value=mock_resp):
        with patch("huggingface_hub.HfApi"):
            lab = load_lab("07b_ecosystem_fluency")
            results = lab.provider_shootout("Hello", ["openai/gpt-4o-mini"])
    assert len(results) == 1 and "provider" in results[0] and "latency_ms" in results[0]
