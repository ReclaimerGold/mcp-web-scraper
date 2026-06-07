from __future__ import annotations

from mcp.server.transport_security import TransportSecuritySettings

from mcp_web_scraper.config import Settings


def build_transport_security(settings: Settings) -> TransportSecuritySettings:
    """Build MCP transport security settings for Streamable HTTP.

    Odysseus connects from its backend via ``streamablehttp_client`` without a
    browser Origin header. DNS rebinding protection stays disabled by default so
    Docker service names (``mcp-web-scraper:8000``) and ``host.docker.internal``
    work without extra host allowlists.
    """
    origins_raw = settings.allowed_origins.strip()
    if not origins_raw or origins_raw == "*":
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    origins = [part.strip() for part in origins_raw.split(",") if part.strip()]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_origins=origins,
        allowed_hosts=[],
    )
