# syntax=docker/dockerfile:1

# ---- Stage 1: build the React frontend ----
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime serving API + built frontend ----
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini backend/docker-entrypoint.sh ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN useradd --create-home --uid 10001 app \
 && chmod +x /app/backend/docker-entrypoint.sh
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status == 200 else 1)"

# Entrypoint runs `alembic upgrade head` unless RUN_MIGRATIONS=false, then execs CMD.
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
