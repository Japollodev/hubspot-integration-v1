"""Response contract for /api/uploads (mirrored in frontend/src/lib/api.ts)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import ExtractionStatus, HubSpotStatus


class HubSpotFileResult(BaseModel):
    status: HubSpotStatus
    file_id: str | None = None
    url: str | None = None
    error: str | None = None


class FieldEvidenceOut(BaseModel):
    """What the extractor saw for one field, kept for review."""

    legibility: Literal["clear", "partial", "unreadable", "absent"]
    source_text: str | None = None
    note: str | None = None


class ContactFields(BaseModel):
    """Extracted contact. None = absent or unreadable on the card (see `evidence` for why)."""

    extractor: str
    status: ExtractionStatus = ExtractionStatus.SUCCEEDED
    model: str | None = None
    error_code: str | None = None
    error: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None
    evidence: dict[str, FieldEvidenceOut] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    hubspot: HubSpotFileResult
    contact: ContactFields | None = None
