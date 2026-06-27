"""Tests for labs/08b_inference_platforms.py."""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab


def test_cloud_comparison_shape():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="ok"))]
    mock_resp.usage = MagicMock(total_tokens=50)
    with patch("litellm.completion", return_value=mock_resp):
        lab = load_lab("08b_inference_platforms")
        providers = [{"name": "groq", "litellm_model": "groq/llama3-8b-8192", "cost_per_1m": 0.05}]
        results = lab.cloud_comparison("Hello", providers)
    assert len(results) == 1 and {"name", "latency_ms", "output"} <= results[0].keys()


def test_call_ollama_returns_string():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="hi"))]
    with patch("litellm.completion", return_value=mock_resp):
        lab = load_lab("08b_inference_platforms")
        result = lab.call_ollama("Hello", "llama3", "http://localhost:11434/v1")
    assert result == "hi"


def test_cloud_providers_list_non_empty():
    with patch("litellm.completion"):
        lab = load_lab("08b_inference_platforms")
        assert len(lab.CLOUD_PROVIDERS) >= 3
        assert all("name" in p and "litellm_model" in p for p in lab.CLOUD_PROVIDERS)
