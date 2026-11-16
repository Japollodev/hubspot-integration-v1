"""FastAPI application factory.

- JSON API under /api
- Built React app (frontend/dist) served at / with SPA fallback
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import error_response, register_error_handlers
from app.core.limits import UploadSizeLimitMiddleware
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.services.hubspot_files import create_hubspot_http

API_PREFIX = "/api"


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        # Dev mode: the Vite dev server serves the frontend and proxies /api here.
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    dist_root = dist.resolve()
    api_root = API_PREFIX.strip("/")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa(full_path: str) -> Response:
        # Unknown /api/* paths must 404 as JSON, never fall through to index.html.
        if full_path == api_root or full_path.startswith(api_root + "/"):
            return error_response(404, "http_error", "Not Found")
        candidate = (dist_root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
            return FileResponse(candidate)
        return FileResponse(index)


def _lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Engines connect lazily, so startup doesn't fail if the DB is briefly unavailable.
        engine = create_engine(
            settings.database_url.get_secret_value(),
            pooled=settings.db_pooled,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
        app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        app.state.hubspot_http = create_hubspot_http(settings)
        # One shared connection pool for OpenAI; each request brings its own key (BYOK).
        app.state.openai_http = openai.DefaultAsyncHttpxClient(timeout=settings.openai_timeout_s)
        try:
            yield
        finally:
            await app.state.openai_http.aclose()
            await app.state.hubspot_http.aclose()
            await engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)

    app = FastAPI(
        lifespan=_lifespan(settings),
        title=settings.app_name,
        version=__version__,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(
        UploadSizeLimitMiddleware,
        path=f"{API_PREFIX}/uploads",
        max_bytes=settings.max_upload_bytes,
    )
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)
    _mount_frontend(app, settings.frontend_dist)
    return app


app = create_app()
