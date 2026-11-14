"""Response contract for /api/uploads (mirrored in frontend/src/lib/api.ts)."""

import uuid

from pydantic import BaseModel

from app.db.models import HubSpotStatus


class HubSpotFileResult(BaseModel):
    status: HubSpotStatus
    file_id: str | None = None
    url: str | None = None
    error: str | None = None


class ContactFields(BaseModel):
    """Extracted contact. None = absent or unreadable on the card."""

    extractor: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None


class UploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    hubspot: HubSpotFileResult
    contact: ContactFields | None = None
