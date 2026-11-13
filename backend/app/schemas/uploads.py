"""Response contract for POST /api/uploads (mirrored in frontend/src/lib/api.ts)."""

import uuid

from pydantic import BaseModel

from app.db.models import HubSpotStatus


class HubSpotFileResult(BaseModel):
    status: HubSpotStatus
    file_id: str | None = None
    url: str | None = None
    error: str | None = None


class UploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    hubspot: HubSpotFileResult
