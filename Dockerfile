FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin mcp

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

USER mcp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["mcp-web-scraper"]
