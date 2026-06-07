from __future__ import annotations

import re
from typing import Any

import ollama

from mcp_web_scraper.config import Settings

_THINK_OPEN = "<" + "redacted_thinking" + ">"
_THINK_CLOSE = "</" + "redacted_thinking" + ">"
_THINKING_RE = re.compile(
    re.escape(_THINK_OPEN) + r".*?" + re.escape(_THINK_CLOSE),
    re.DOTALL,
)


class AnalysisError(Exception):
    """Raised when Ollama analysis fails."""


def strip_thinking_blocks(text: str) -> str:
    return _THINKING_RE.sub("", text).strip()


def analyze_content(
    content: str,
    prompt: str,
    settings: Settings,
    *,
    model: str | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    chosen_model = model or settings.ollama_model
    user_message = (
        f"{prompt.strip()}\n\n"
        "---\n"
        "Content to analyze:\n"
        f"{content.strip()}"
    )

    try:
        client = ollama.Client(host=settings.ollama_host)
        response = client.chat(
            model=chosen_model,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as exc:
        raise AnalysisError(f"Ollama request failed: {exc}") from exc

    raw = response.message.content
    analysis = strip_thinking_blocks(raw)

    result: dict[str, Any] = {
        "model": chosen_model,
        "analysis": analysis,
    }
    if include_raw:
        result["raw"] = raw
    return result
