"""BYOK helpers for the UI: check a user's key before they upload, and report server key mode."""

from typing import Annotated

import openai
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import AppError
from app.services.extraction.keys import header_openai_key, make_openai_client, missing_key_error

router = APIRouter(prefix="/openai", tags=["openai"])


class OpenAIStatus(BaseModel):
    # True when a dev-only .env key will be used if the browser sends none.
    server_key_available: bool
    model: str


class VerifyResult(BaseModel):
    valid: bool
    message: str | None = None


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/status")
async def openai_status(settings: Annotated[Settings, Depends(_settings)]) -> OpenAIStatus:
    return OpenAIStatus(
        server_key_available=settings.server_openai_key is not None, model=settings.openai_model
    )


@router.post("/verify")
async def verify_openai_key(
    request: Request, settings: Annotated[Settings, Depends(_settings)]
) -> VerifyResult:
    """Check the X-OpenAI-Key header can authenticate AND use the configured model.

    Retrieving the model is one cheap call (no tokens billed) that proves both.
    """
    key = header_openai_key(request)
    if key is None:
        raise missing_key_error()
    client = make_openai_client(request, key, max_retries=0)
    try:
        await client.models.retrieve(settings.openai_model)
    except openai.AuthenticationError:
        return VerifyResult(valid=False, message="OpenAI rejected this API key.")
    except (openai.PermissionDeniedError, openai.NotFoundError):
        return VerifyResult(
            valid=False,
            message=f"This key works but can't use the model '{settings.openai_model}'.",
        )
    except openai.APIError as exc:
        raise AppError(
            "Could not reach OpenAI to check the key. Try again.",
            code="openai_unreachable",
            status_code=502,
        ) from exc
    return VerifyResult(valid=True)
