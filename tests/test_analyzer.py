from unittest.mock import MagicMock, patch

import pytest

from mcp_web_scraper.analyzer import AnalysisError, analyze_content, strip_thinking_blocks
from mcp_web_scraper.config import Settings

_THINK_OPEN = "<" + "redacted_thinking" + ">"
_THINK_CLOSE = "</" + "redacted_thinking" + ">"


def test_strip_thinking_blocks() -> None:
    raw = f"{_THINK_OPEN}internal reasoning{_THINK_CLOSE}\n\nFinal answer here."
    assert strip_thinking_blocks(raw) == "Final answer here."


def test_analyze_content_returns_cleaned_analysis() -> None:
    settings = Settings(OLLAMA_HOST="http://localhost:11434", OLLAMA_MODEL="deepseek-r1:7b")
    message = MagicMock()
    message.content = f"{_THINK_OPEN}thinking{_THINK_CLOSE}\n\nSummary text."
    response = MagicMock(message=message)

    with patch("mcp_web_scraper.analyzer.ollama.Client") as mock_client_cls:
        mock_client_cls.return_value.chat.return_value = response
        result = analyze_content("page text", "Summarize this", settings)

    assert result["model"] == "deepseek-r1:7b"
    assert result["analysis"] == "Summary text."
    mock_client_cls.return_value.chat.assert_called_once()


def test_analyze_content_wraps_ollama_errors() -> None:
    settings = Settings(OLLAMA_HOST="http://localhost:11434")

    with patch("mcp_web_scraper.analyzer.ollama.Client") as mock_client_cls:
        mock_client_cls.return_value.chat.side_effect = RuntimeError("connection refused")
        with pytest.raises(AnalysisError, match="Ollama request failed"):
            analyze_content("content", "Analyze", settings)
