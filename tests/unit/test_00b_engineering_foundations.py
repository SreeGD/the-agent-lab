"""Tests for labs/00b_engineering_foundations.py."""
from unittest.mock import MagicMock, patch

from tests.conftest import load_lab


def test_chat_endpoint_returns_text() -> None:
    """POST /chat with a valid message returns 200 and the Claude reply."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Hello from Claude")]
    )
    with patch("anthropic.Anthropic", return_value=mock_client):
        lab = load_lab("00b_engineering_foundations")
        from fastapi.testclient import TestClient

        client = TestClient(lab.create_app())
    resp = client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Hello from Claude"


def test_chat_endpoint_rejects_empty_message() -> None:
    """POST /chat with an empty string must return HTTP 422."""
    with patch("anthropic.Anthropic"):
        lab = load_lab("00b_engineering_foundations")
        from fastapi.testclient import TestClient

        client = TestClient(lab.create_app())
    resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422
