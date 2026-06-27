"""Tests for labs/21b_portfolio_generator.py."""
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_lab


def test_scan_labs_extracts_docstrings(tmp_path):
    lab = tmp_path / "05_structured_output.py"
    lab.write_text(textwrap.dedent('''\
        """Session 05 — Structured output using Pydantic models."""
        from pydantic import BaseModel
    '''))
    with patch("anthropic.Anthropic"):
        mod = load_lab("21b_portfolio_generator")
        entries = mod.scan_labs(str(tmp_path))
    assert len(entries) == 1
    assert "Structured output" in entries[0]["docstring"]


def test_scan_labs_skips_files_without_docstring(tmp_path):
    (tmp_path / "no_doc.py").write_text("x = 1\n")
    with patch("anthropic.Anthropic"):
        mod = load_lab("21b_portfolio_generator")
        entries = mod.scan_labs(str(tmp_path))
    assert len(entries) == 0


def test_build_portfolio_contains_skills_section(tmp_path):
    lab = tmp_path / "05_structured_output.py"
    lab.write_text(textwrap.dedent('''\
        """Session 05 — Structured output using Pydantic models."""
        x = 1
    '''))
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="**Session 05**: Structured output demo")]
    )
    with patch("anthropic.Anthropic", return_value=mock_client):
        mod = load_lab("21b_portfolio_generator")
        entries = mod.scan_labs(str(tmp_path))
        cards = [mod.generate_project_card(e, mock_client) for e in entries]
        portfolio = mod.build_portfolio(entries, cards)
    assert "Skills" in portfolio or "skills" in portfolio.lower()
    assert "Session 05" in portfolio or "structured" in portfolio.lower()
