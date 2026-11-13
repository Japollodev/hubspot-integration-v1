"""Minimal HubSpot Files API (v3) client.

Uploads are PRIVATE: HubSpot only serves them via signed URLs, so contact photos are never
publicly reachable. The httpx client is injected so tests can use httpx.MockTransport.
"""

import json
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Request

from app.core.config import Settings

UPLOAD_PATH = "/files/v3/files"


class HubSpotError(Exception):
    """HubSpot rejected the request or could not be reached. Message is safe to persist."""


@dataclass(frozen=True)
class HubSpotFile:
    id: str
    url: str | None


class HubSpotFilesClient:
    def __init__(self, http: httpx.AsyncClient, *, token: str, folder_path: str) -> None:
        self._http = http
        self._token = token
        self._folder_path = folder_path

    async def upload(self, *, filename: str, content_type: str, data: bytes) -> HubSpotFile:
        options = {"access": "PRIVATE", "overwrite": False, "duplicateValidationStrategy": "NONE"}
        try:
            res = await self._http.post(
                UPLOAD_PATH,
                headers={"Authorization": f"Bearer {self._token}"},
                files={"file": (filename, data, content_type)},
                data={"folderPath": self._folder_path, "options": json.dumps(options)},
            )
        except httpx.HTTPError as exc:
            raise HubSpotError(f"HubSpot unreachable: {type(exc).__name__}") from exc

        if res.status_code >= 400:
            raise HubSpotError(f"HubSpot returned {res.status_code}: {_error_message(res)}")

        body: dict[str, Any] = res.json()
        file_id = body.get("id")
        if not file_id:
            raise HubSpotError("HubSpot response did not include a file id")
        url = body.get("url")
        return HubSpotFile(id=str(file_id), url=str(url) if url else None)


def _error_message(res: httpx.Response) -> str:
    try:
        message = res.json().get("message")
    except ValueError:
        message = None
    return str(message or res.reason_phrase or "error")[:500]


def create_hubspot_http(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.hubspot_api_base, timeout=settings.hubspot_timeout_s)


def get_hubspot_files(request: Request) -> HubSpotFilesClient | None:
    """FastAPI dependency. Returns None when no HubSpot token is configured."""
    settings: Settings = request.app.state.settings
    if settings.hubspot_access_token is None:
        return None
    return HubSpotFilesClient(
        request.app.state.hubspot_http,
        token=settings.hubspot_access_token.get_secret_value(),
        folder_path=settings.hubspot_files_folder,
    )
