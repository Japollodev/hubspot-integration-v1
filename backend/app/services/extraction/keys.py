"""Bring-your-own-key: resolve which OpenAI key a request uses, and build a client for it.

The key arrives from the browser in the X-OpenAI-Key header. It is used for this one request,
held only in memory, and never persisted or logged. Outside production, an OPENAI_API_KEY in
.env is a convenience fallback for local dev and the live tests.
"""

from fastapi import Request
from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.errors import AppError
from app.services.extraction.base import OpenAIKeyError

OPENAI_KEY_HEADER = "X-OpenAI-Key"


def header_openai_key(request: Request) -> str | None:
    """The user's key from the request header, or None."""
    key = request.headers.get(OPENAI_KEY_HEADER, "").strip()
    return key or None


def missing_key_error() -> AppError:
    err = OpenAIKeyError("missing")
    return AppError(str(err), code=err.code, status_code=400)


def resolve_openai_key(request: Request) -> str:
    """FastAPI dependency: header key, else the dev-only .env key, else 400 openai_key_missing.

    Runs before the route body, so a missing key fails before anything is stored.
    """
    settings: Settings = request.app.state.settings
    key = header_openai_key(request) or settings.server_openai_key
    if key is None:
        raise missing_key_error()
    return key


def make_openai_client(request: Request, key: str, *, max_retries: int = 2) -> AsyncOpenAI:
    """A per-request client carrying `key`, sharing the app-wide connection pool."""
    settings: Settings = request.app.state.settings
    return AsyncOpenAI(
        api_key=key,
        base_url=settings.openai_api_base,
        http_client=request.app.state.openai_http,
        timeout=settings.openai_timeout_s,
        max_retries=max_retries,
    )
