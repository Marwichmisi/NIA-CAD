FROM python:3.12.3-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12.3-slim AS runtime

WORKDIR /app
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin nia
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml ./
COPY docker/api-entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    NIA_DATABASE=/data/nia.sqlite \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=8 \
    CMD /app/.venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/projects')"

ENTRYPOINT ["/entrypoint.sh"]
