"""Shared pytest fixtures for AgenticCourse test suite."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Make labs/ importable as a package
sys.path.insert(0, str(Path(__file__).parent.parent / "labs"))


def load_lab(filename: str):
    """Load a lab module from labs/<filename>.py regardless of digit prefix.

    Args:
        filename: Lab file name without .py extension (e.g., "01_model_wrapper")

    Returns:
        The loaded module object
    """
    path = Path(__file__).parent.parent / "labs" / f"{filename}.py"
    spec = importlib.util.spec_from_file_location(filename, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load lab module from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[filename] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patch anthropic.Anthropic everywhere with a mock client."""
    mock = MagicMock()
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: mock)
    return mock


@pytest.fixture
def mock_chat_anthropic(monkeypatch):
    """Patch ChatAnthropic for LangChain-based labs."""
    mock = MagicMock()
    monkeypatch.setattr("langchain_anthropic.ChatAnthropic", lambda **kw: mock)
    return mock
