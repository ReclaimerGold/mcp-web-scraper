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

from mcp_web_scraper.config import Settings, get_settings
from mcp_web_scraper.scraper import ScrapeError, extract_from_html, scrape_url
from mcp_web_scraper.transport import build_transport_security


def create_mcp_server(cfg: Settings) -> FastMCP:
    server = FastMCP(
        "mcp-web-scraper",
        stateless_http=True,
        json_response=True,
        transport_security=build_transport_security(cfg),
    )

    @server.tool(
        name="scrape_url",
        description=(
            "Fetch a web page over HTTP/HTTPS and return its title, plain text, "
            "optional CSS selector matches, and links. Static HTML only."
        ),
    )
    async def scrape_url_tool(
        url: str,
        css_selectors: dict[str, str] | None = None,
        include_links: bool = False,
        max_chars: int = 50000,
    ) -> dict[str, Any]:
        try:
            return await scrape_url(
                url,
                cfg,
                css_selectors=css_selectors,
                include_links=include_links,
                max_chars=max_chars,
            )
        except ScrapeError as exc:
            return {"error": str(exc), "url": url}
        except Exception as exc:
            return {"error": f"Unexpected scrape failure: {exc}", "url": url}

    @server.tool(
        name="extract_from_html",
        description="Extract visible text from an HTML string using a CSS selector.",
    )
    def extract_from_html_tool(html: str, css_selector: str) -> dict[str, Any]:
        try:
            values = extract_from_html(html, css_selector)
            return {"css_selector": css_selector, "values": values, "count": len(values)}
        except Exception as exc:
            return {"error": str(exc), "css_selector": css_selector}

    return server


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Optional API key guard for /mcp.

    Returns 403 (not 401) on failure so Odysseus does not misinterpret a missing
    static API key as an OAuth challenge and enter the browser auth flow.
    """

    def __init__(self, app: Any, api_key: str) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not self.api_key or not request.url.path.startswith("/mcp"):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        expected = f"Bearer {self.api_key}"
        if auth != expected:
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        return await call_next(request)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app(cfg: Settings | None = None) -> Starlette:
    cfg = cfg or get_settings()
    mcp = create_mcp_server(cfg)
    middleware: list[Middleware] = []
    if cfg.mcp_api_key:
        middleware.append(Middleware(BearerAuthMiddleware, api_key=cfg.mcp_api_key))

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    # Odysseus expects the Streamable HTTP endpoint at the configured URL,
    # e.g. http://mcp-web-scraper:8000/mcp (transport "http" in Settings → MCP).
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
    settings = get_settings()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
