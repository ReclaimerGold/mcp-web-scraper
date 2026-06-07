# MCP Web Scraper

A standalone [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that scrapes static HTML with BeautifulSoup. LLM analysis is handled by your MCP client (e.g. [Odysseus](https://github.com/pewdiepie-archdaemon/odysseus) with Ollama, or [Open WebUI](https://docs.openwebui.com/features/extensibility/mcp/)) — this server only provides scraping tools.

Designed for container deployment over **Streamable HTTP**.

## What it does

Exposes two MCP tools:

| Tool | Description |
|------|-------------|
| `scrape_url` | Fetch a URL and return title, text, optional CSS matches, and links |
| `extract_from_html` | Parse existing HTML with a CSS selector |

**Limitations:** static HTML only (no JavaScript rendering), no anti-bot bypass. Respect site terms and rate limits.

## Prerequisites

- Docker

## Quick start (GHCR image)

After your first GitHub Release, pull the published image:

```bash
docker pull ghcr.io/<owner>/mcp-web-scraper:latest

docker run -d \
  --name mcp-web-scraper \
  -p 127.0.0.1:8000:8000 \
  ghcr.io/<owner>/mcp-web-scraper:latest
```

Verify health:

```bash
curl http://127.0.0.1:8000/health
```

MCP endpoint: `http://127.0.0.1:8000/mcp`

### Make the GHCR package public

1. Go to your GitHub profile → **Packages** → `mcp-web-scraper`
2. **Package settings** → **Change visibility** → Public

## Local build

```bash
cp .env.example .env
docker compose up --build -d
```

## Connect to Odysseus

Odysseus uses native Streamable HTTP MCP (transport `http`) via the Python SDK's `streamablehttp_client`. No MCPO bridge required.

### Odysseus requirements this server meets

| Requirement | How this server satisfies it |
|-------------|------------------------------|
| Transport `http` | Streamable HTTP at `/mcp` with `stateless_http=True` and `json_response=True` |
| MCP URL | Use `http://<host>:8000/mcp` exactly (Odysseus `McpManager._connect_http`) |
| No OAuth | Server does not return `401`; Odysseus only starts OAuth on `401` responses |
| Tool discovery | `initialize` + `list_tools` expose `scrape_url` and `extract_from_html` with JSON Schema |
| Tool calls | Agent invokes `mcp__{server_id}__scrape_url` via `session.call_tool` |
| Fast connect | Startup completes within Odysseus's 8s HTTP connect window |

**Important:** Leave `MCP_API_KEY` empty when using Odysseus. Odysseus does not send a Bearer token for HTTP MCP servers, and a `401` response would trigger its OAuth flow.

1. Run this MCP server (publish port `8000` or attach to the same Docker network as Odysseus).
2. In Odysseus **Settings → MCP** (admin), add a server:

| Field | Value |
|-------|-------|
| Name | `web-scraper` |
| Transport | `http` |
| URL | `http://mcp-web-scraper:8000/mcp` (shared compose network) or `http://host.docker.internal:8000/mcp` (MCP on host) |

3. Configure your LLM in Odysseus separately — the agent uses scraping tools from this server and its own model for analysis.

### Compose overlay with Odysseus

Add to your Odysseus `docker-compose.yml` or an override file:

```yaml
services:
  mcp-web-scraper:
    image: ghcr.io/<owner>/mcp-web-scraper:latest
    ports:
      - "127.0.0.1:8000:8000"
    restart: unless-stopped

  odysseus:
    depends_on:
      - mcp-web-scraper
```

Use `http://mcp-web-scraper:8000/mcp` as the MCP URL inside Odysseus.

### Shared network overlay (separate compose projects)

If Odysseus and this server run in **different** `docker compose` projects, attach this service to the Odysseus network:

```bash
# Confirm the Odysseus network name (usually odysseus_default)
docker network ls | rg odysseus

docker compose -f docker-compose.yml -f docker-compose.odysseus.yml up -d
```

Register URL: `http://mcp-web-scraper:8000/mcp`

### Odysseus in Docker (most common)

Odysseus's backend resolves the MCP URL **inside its container**. The hostname `mcp-web-scraper` only works when both containers share a Docker network; otherwise you get `Temporary failure in name resolution` and Odysseus may return HTTP 500.

**Quickest fix** — MCP published on the host (`MCP_BIND=0.0.0.0`, the default):

| Field | Value |
|-------|-------|
| Transport | `http` (Streamable HTTP) |
| URL | `http://host.docker.internal:8000/mcp` |

Odysseus's `docker-compose.yml` already sets `extra_hosts: host.docker.internal:host-gateway`. Verify from the Odysseus container:

```bash
docker exec -it odysseus-odysseus-1 curl -sf http://host.docker.internal:8000/health
```

**Shared-network fix** — use the service name instead of the host:

```bash
docker network ls | rg odysseus   # e.g. odysseus_default
docker compose -f docker-compose.yml -f docker-compose.odysseus.yml up -d
```

Then register `http://mcp-web-scraper:8000/mcp`.

### Which MCP URL to use

| Odysseus runs… | MCP runs… | URL in Odysseus |
|----------------|-----------|-----------------|
| In Docker (same compose/network) | In Docker (same network) | `http://mcp-web-scraper:8000/mcp` |
| In Docker (separate compose) | In Docker | `docker-compose.odysseus.yml` overlay, then `http://mcp-web-scraper:8000/mcp` |
| In Docker | On Docker host (`MCP_BIND=0.0.0.0`) | `http://host.docker.internal:8000/mcp` |
| On host | In Docker (`127.0.0.1:8000` publish) | `http://127.0.0.1:8000/mcp` |
| On host | In Docker (`0.0.0.0:8000` publish) | `http://127.0.0.1:8000/mcp` or your host LAN IP |

**Do not** use your host LAN IP unless `MCP_BIND` publishes port 8000 on `0.0.0.0`. The default compose file uses `0.0.0.0`; set `MCP_BIND=127.0.0.1` only if you want host-local access.

### Troubleshooting Odysseus `POST /api/mcp/servers` → 500

The browser error is reported by **Odysseus** (`localhost:7000`), not this MCP server. A failed MCP connection normally returns HTTP 200 with `"status": "error"` in the JSON body — a **500** means Odysseus raised an unhandled exception.

1. **Read Odysseus logs** while saving the server (replace the container name if different):

   ```bash
   docker logs -f odysseus-odysseus-1 2>&1 | rg -i "mcp|error|traceback"
   ```

   Or, if Odysseus runs directly on the host, check the terminal where `app.py` is running.

2. **Test reachability from Odysseus** (run inside the Odysseus container):

   ```bash
   docker exec -it odysseus-odysseus-1 curl -sf http://mcp-web-scraper:8000/health
   # or, MCP on host:
   docker exec -it odysseus-odysseus-1 curl -sf http://host.docker.internal:8000/health
   ```

   Expect `{"status":"ok"}`. If this fails, fix networking before re-saving in the UI.

3. **Confirm this server is up** on the host:

   ```bash
   curl -sf http://127.0.0.1:8000/health
   ```

4. **Leave `MCP_API_KEY` empty** for Odysseus (see `.env.example`). Odysseus does not send Bearer tokens.

5. **Use the exact path** `/mcp` — not `/` or `/sse`.

6. **Pull or rebuild** the latest image after compatibility fixes:

   ```bash
   docker compose pull && docker compose up -d --build
   ```

Common log messages:

| Odysseus / client error | Fix |
|-------------------------|-----|
| `Name or service not known` | Shared Docker network missing — use `docker-compose.odysseus.yml` |
| `Connection refused` | Wrong URL, or MCP published only on `127.0.0.1` while Odysseus is in another container |
| `no such column: oauth_tokens` | Run Odysseus once so DB migrations apply, or upgrade Odysseus |
| `403 Forbidden` on `/mcp` | Unset `MCP_API_KEY` in this server's `.env` |

## Connect to Open WebUI

Open WebUI v0.6.31+ supports MCP Streamable HTTP natively.

1. **Admin Settings → External Tools → Add Server**
2. **Type:** MCP (Streamable HTTP)
3. **URL:** `http://host.docker.internal:8000/mcp`
4. **Auth:** None (or Bearer if `MCP_API_KEY` is set)
5. Enable **Function Calling: Native** on your model

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `8000` | HTTP port |
| `SCRAPE_TIMEOUT_S` | `30` | HTTP fetch timeout (seconds) |
| `SCRAPE_MAX_BYTES` | `2097152` | Max download size (2 MB) |
| `MCP_API_KEY` | _(empty)_ | Optional Bearer token for `/mcp` (incompatible with Odysseus) |
| `ALLOWED_ORIGINS` | `*` | Origin allowlist; `*` disables DNS rebinding checks (recommended for Odysseus/Docker) |
| `USER_AGENT` | `mcp-web-scraper/0.1.0` | HTTP User-Agent header |

## Security

- Do not expose this server unauthenticated on the public internet.
- Set `MCP_API_KEY` for Open WebUI or other clients that support Bearer auth. Do not enable it for Odysseus.
- Scraping is unrestricted by default; only scrape sites you are permitted to access.

## Creating a release

CI publishes to GHCR when a GitHub Release is created:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Create a release from tag `v0.1.0` on GitHub. The [release workflow](.github/workflows/release.yml) pushes:

- `ghcr.io/<owner>/mcp-web-scraper:0.1.0`
- `ghcr.io/<owner>/mcp-web-scraper:0.1`
- `ghcr.io/<owner>/mcp-web-scraper:0`
- `ghcr.io/<owner>/mcp-web-scraper:latest`

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
pytest
mcp-web-scraper
```

## License

MIT
