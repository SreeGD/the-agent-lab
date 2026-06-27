"""Tests for labs/09b_voice_image_agents.py."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab

# Stub optional heavy dependencies so patch() can resolve their attributes
if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()
if "replicate" not in sys.modules:
    sys.modules["replicate"] = MagicMock()
if "elevenlabs" not in sys.modules:
    sys.modules["elevenlabs"] = MagicMock()
    sys.modules["elevenlabs.client"] = MagicMock()


def test_run_pipeline_budget_returns_required_keys(tmp_path: Path) -> None:
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="A surreal landscape with floating islands")]
    )
    with (
        patch("anthropic.Anthropic", return_value=mock_client),
        patch("openai.OpenAI") as mock_oai,
        patch("whisper.load_model") as mock_whisper,
    ):
        mock_whisper.return_value.transcribe.return_value = {"text": "paint me a sunset"}
        mock_oai.return_value.images.generate.return_value = MagicMock(
            data=[MagicMock(url="https://example.com/img.png")]
        )
        mock_oai.return_value.audio.speech.create.return_value = MagicMock()
        mock_oai.return_value.audio.speech.create.return_value.stream_to_file = MagicMock()
        lab = load_lab("09b_voice_image_agents")
        result = lab.run_pipeline(str(audio), "budget", mock_client)
    assert {"transcription", "refined_prompt", "image_url", "audio_path"} <= result.keys()
    assert result["transcription"] == "paint me a sunset"


def test_run_pipeline_unknown_track_raises(tmp_path: Path) -> None:
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    mock_client = MagicMock()
    with patch("anthropic.Anthropic", return_value=mock_client):
        lab = load_lab("09b_voice_image_agents")
        with pytest.raises(ValueError, match="Unknown track"):
            lab.run_pipeline(str(audio), "invalid_track", mock_client)
