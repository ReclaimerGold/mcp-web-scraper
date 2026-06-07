# MCP Web Scraper

A minimal [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that scrapes static HTML with BeautifulSoup and analyzes content via an external [Ollama](https://ollama.com) DeepSeek model.

Designed for container deployment and integration with [Odysseus](https://github.com/pewdiepie-archdaemon/odysseus) and [Open WebUI](https://docs.openwebui.com/features/extensibility/mcp/) over **Streamable HTTP**.

## What it does

Exposes three MCP tools:

| Tool | Description |
|------|-------------|
| `scrape_url` | Fetch a URL and return title, text, optional CSS matches, and links |
| `extract_from_html` | Parse existing HTML with a CSS selector |
| `analyze_content` | Send text to Ollama/DeepSeek with a custom analysis prompt |

**Limitations:** static HTML only (no JavaScript rendering), no anti-bot bypass. Respect site terms and rate limits.

## Prerequisites

- Docker
- Ollama running on the host with a DeepSeek model pulled, e.g. `ollama pull deepseek-r1:7b`
- Host Ollama listening on the network (required when MCP runs in Docker):

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

## Quick start (GHCR image)

After your first GitHub Release, pull the published image:

```bash
docker pull ghcr.io/<owner>/mcp-web-scraper:latest

docker run -d \
  --name mcp-web-scraper \
  -p 127.0.0.1:8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:7b \
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

Odysseus uses native Streamable HTTP MCP (transport `http`). No MCPO bridge required.

1. Run this MCP server (publish port `8000` or attach to the same Docker network as Odysseus).
2. In Odysseus **Settings → MCP** (admin), add a server:

| Field | Value |
|-------|-------|
| Name | `web-scraper` |
| Transport | `http` |
| URL | `http://mcp-web-scraper:8000/mcp` (shared compose network) or `http://host.docker.internal:8000/mcp` (MCP on host) |

3. Configure Ollama in Odysseus separately: `http://host.docker.internal:11434/v1`

### Compose overlay with Odysseus

Add to your Odysseus `docker-compose.yml` or a override file:

```yaml
services:
  mcp-web-scraper:
    image: ghcr.io/<owner>/mcp-web-scraper:latest
    ports:
      - "127.0.0.1:8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OLLAMA_HOST=http://host.docker.internal:11434
      - OLLAMA_MODEL=deepseek-r1:7b
    restart: unless-stopped

  odysseus:
    depends_on:
      - mcp-web-scraper
```

Use `http://mcp-web-scraper:8000/mcp` as the MCP URL inside Odysseus.

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
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `deepseek-r1:7b` | Default analysis model |
| `SCRAPE_TIMEOUT_S` | `30` | HTTP fetch timeout (seconds) |
| `SCRAPE_MAX_BYTES` | `2097152` | Max download size (2 MB) |
| `MCP_API_KEY` | _(empty)_ | Optional Bearer token for `/mcp` |
| `ALLOWED_ORIGINS` | `*` | Origin allowlist for Streamable HTTP |
| `USER_AGENT` | `mcp-web-scraper/0.1.0` | HTTP User-Agent header |

## Security

- Do not expose this server unauthenticated on the public internet.
- Set `MCP_API_KEY` and pass `Authorization: Bearer <key>` from your MCP client.
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
