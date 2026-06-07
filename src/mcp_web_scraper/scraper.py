from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from mcp_web_scraper.config import Settings


class ScrapeError(Exception):
    """Raised when a URL cannot be fetched or parsed."""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ", strip=True).split())


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(
            {
                "href": absolute,
                "text": anchor.get_text(strip=True),
            }
        )
    return links


def _extract_selected(soup: BeautifulSoup, css_selectors: dict[str, str]) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    for name, selector in css_selectors.items():
        elements = soup.select(selector)
        selected[name] = [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
    return selected


def extract_from_html(html: str, css_selector: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [el.get_text(strip=True) for el in soup.select(css_selector) if el.get_text(strip=True)]


async def scrape_url(
    url: str,
    settings: Settings,
    *,
    css_selectors: dict[str, str] | None = None,
    include_links: bool = False,
    max_chars: int = 50_000,
) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ScrapeError("URL must use http or https")

    headers = {"User-Agent": settings.user_agent}
    timeout = httpx.Timeout(settings.scrape_timeout_s)

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower() and "text" not in content_type.lower():
                raise ScrapeError(f"Unsupported content type: {content_type or 'unknown'}")

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > settings.scrape_max_bytes:
                    raise ScrapeError(
                        f"Response exceeds max size of {settings.scrape_max_bytes} bytes"
                    )
                chunks.append(chunk)

            final_url = str(response.url)
            encoding = response.encoding or "utf-8"

    html = b"".join(chunks).decode(encoding, errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    result: dict[str, Any] = {
        "url": final_url,
        "title": title,
        "text": _truncate(_extract_text(soup), max_chars),
    }

    if css_selectors:
        result["selected"] = _extract_selected(soup, css_selectors)

    if include_links:
        result["links"] = _extract_links(soup, final_url)

    return result
