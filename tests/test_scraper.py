import httpx
import pytest
import respx

from mcp_web_scraper.config import Settings
from mcp_web_scraper.scraper import ScrapeError, extract_from_html, scrape_url

HTML = """
<html>
  <head><title>Example Page</title></head>
  <body>
    <h1 class="title">Hello</h1>
    <p>First paragraph.</p>
    <a href="/about">About</a>
    <a href="https://example.org">External</a>
  </body>
</html>
"""


@pytest.fixture
def settings() -> Settings:
    return Settings(
        SCRAPE_TIMEOUT_S=5,
        SCRAPE_MAX_BYTES=1_048_576,
        USER_AGENT="test-agent",
    )


@respx.mock
@pytest.mark.asyncio
async def test_scrape_url_extracts_title_and_text(settings: Settings) -> None:
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200,
            text=HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    result = await scrape_url("https://example.com", settings)

    assert result["title"] == "Example Page"
    assert "Hello" in result["text"]
    assert "First paragraph." in result["text"]


@respx.mock
@pytest.mark.asyncio
async def test_scrape_url_with_selectors_and_links(settings: Settings) -> None:
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200,
            text=HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    result = await scrape_url(
        "https://example.com",
        settings,
        css_selectors={"headings": "h1.title"},
        include_links=True,
    )

    assert result["selected"]["headings"] == ["Hello"]
    assert len(result["links"]) == 2
    assert result["links"][0]["href"] == "https://example.com/about"


@respx.mock
@pytest.mark.asyncio
async def test_scrape_url_rejects_non_http_scheme(settings: Settings) -> None:
    with pytest.raises(ScrapeError, match="http or https"):
        await scrape_url("file:///etc/passwd", settings)


@respx.mock
@pytest.mark.asyncio
async def test_scrape_url_rejects_oversized_response(settings: Settings) -> None:
    settings.scrape_max_bytes = 10
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200,
            content=b"x" * 20,
            headers={"content-type": "text/html"},
        )
    )

    with pytest.raises(ScrapeError, match="max size"):
        await scrape_url("https://example.com", settings)


def test_extract_from_html() -> None:
    values = extract_from_html(HTML, "h1.title")
    assert values == ["Hello"]
