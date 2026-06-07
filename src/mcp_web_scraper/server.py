from __future__ import annotations

import contextlib
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcp_web_scraper.analyzer import AnalysisError, analyze_content
from mcp_web_scraper.config import Settings, get_settings
from mcp_web_scraper.scraper import ScrapeError, extract_from_html, scrape_url

settings = get_settings()

mcp = FastMCP(
    "mcp-web-scraper",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def scrape_url_tool(
    url: str,
    css_selectors: dict[str, str] | None = None,
    include_links: bool = False,
    max_chars: int = 50000,
) -> dict[str, Any]:
    """Fetch a URL and extract page title, text, optional CSS matches, and links."""
    try:
        return await scrape_url(
            url,
            settings,
            css_selectors=css_selectors,
            include_links=include_links,
            max_chars=max_chars,
        )
    except ScrapeError as exc:
        return {"error": str(exc), "url": url}
    except Exception as exc:
        return {"error": f"Unexpected scrape failure: {exc}", "url": url}


@mcp.tool()
def extract_from_html_tool(html: str, css_selector: str) -> dict[str, Any]:
    """Extract text from HTML using a CSS selector."""
    try:
        values = extract_from_html(html, css_selector)
        return {"css_selector": css_selector, "values": values, "count": len(values)}
    except Exception as exc:
        return {"error": str(exc), "css_selector": css_selector}


@mcp.tool()
def analyze_content_tool(
    content: str,
    prompt: str,
    model: str | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Analyze text content with an Ollama-hosted DeepSeek model."""
    try:
        return analyze_content(
            content,
            prompt,
            settings,
            model=model,
            include_raw=include_raw,
        )
    except AnalysisError as exc:
        return {"error": str(exc), "model": model or settings.ollama_model}


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, api_key: str) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not self.api_key or not request.url.path.startswith("/mcp"):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        expected = f"Bearer {self.api_key}"
        if auth != expected:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app(cfg: Settings | None = None) -> Starlette:
    cfg = cfg or settings
    middleware: list[Middleware] = []
    if cfg.mcp_api_key:
        middleware.append(Middleware(BearerAuthMiddleware, api_key=cfg.mcp_api_key))

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    mcp.settings.streamable_http_path = "/"

    return Starlette(
        routes=[
            Route("/health", health),
            Mount("/mcp", app=mcp.streamable_http_app()),
        ],
        lifespan=lifespan,
        middleware=middleware,
    )


def main() -> None:
    app = create_app()
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
