import logging
import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import ContactExtraction, ExtractionStatus, HubSpotStatus, Upload
from app.db.session import get_session
from app.schemas.uploads import (
    ContactFields,
    FieldEvidenceOut,
    HubSpotFileResult,
    UploadResponse,
)
from app.services.extraction import (
    ContactExtractor,
    ExtractionError,
    OpenAIKeyError,
    get_contact_extractor,
)
from app.services.hubspot_files import HubSpotError, HubSpotFilesClient, get_hubspot_files
from app.services.uploads import read_and_validate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])


@router.post("/uploads", status_code=200)
async def create_upload(
    request: Request,
    file: Annotated[UploadFile, File(description="Business-card photo (JPEG/PNG/WebP/HEIC)")],
    session: Annotated[AsyncSession, Depends(get_session)],
    hubspot: Annotated[HubSpotFilesClient | None, Depends(get_hubspot_files)],
    extractor: Annotated[ContactExtractor, Depends(get_contact_extractor)],
) -> UploadResponse:
    settings: Settings = request.app.state.settings
    image = await read_and_validate(file, max_bytes=settings.max_upload_bytes)

    # 1. Postgres first: the photo is durable before any external call.
    upload = Upload(
        original_filename=image.filename,
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        sha256=image.sha256,
        data=image.data,
        hubspot_status=HubSpotStatus.PENDING,
    )
    session.add(upload)
    await session.commit()

    # 2. Contact extraction (OpenAI with the user's key), stored against the upload.
    #    Failures are recorded on the row, not raised -- except an invalid key (raised below,
    #    after the row is saved) because only the user can fix it.
    key_error: OpenAIKeyError | None = None
    try:
        fields = await extractor.extract(image)
    except (ExtractionError, OpenAIKeyError) as exc:
        if isinstance(exc, OpenAIKeyError):
            key_error = exc
        logger.warning(
            "Contact extraction failed",
            extra={"upload_id": str(upload.id), "error_code": exc.code},
        )
        extraction = ContactExtraction(
            upload_id=upload.id,
            extractor=extractor.name,
            status=ExtractionStatus.FAILED,
            error_code=exc.code,
            error=str(exc),
        )
    else:
        extraction = ContactExtraction(
            upload_id=upload.id,
            extractor=extractor.name,
            status=ExtractionStatus.SUCCEEDED,
            model=fields.model,
            evidence={name: asdict(ev) for name, ev in fields.evidence.items()} or None,
            **fields.values(),
        )
    session.add(extraction)

    # 3. HubSpot Files. A failure here is recorded, not raised: the upload itself succeeded.
    if hubspot is None:
        upload.hubspot_status = HubSpotStatus.SKIPPED
    else:
        try:
            hs_file = await hubspot.upload(
                filename=image.filename, content_type=image.content_type, data=image.data
            )
        except HubSpotError as exc:
            logger.warning("HubSpot file upload failed", extra={"upload_id": str(upload.id)})
            upload.hubspot_status = HubSpotStatus.FAILED
            upload.hubspot_error = str(exc)
        else:
            upload.hubspot_status = HubSpotStatus.UPLOADED
            upload.hubspot_file_id = hs_file.id
            upload.hubspot_url = hs_file.url
    await session.commit()

    logger.info(
        "Upload stored",
        extra={
            "upload_id": str(upload.id),
            "size_bytes": upload.size_bytes,
            "hubspot_status": upload.hubspot_status.value,
            "extractor": extraction.extractor,
            "extraction_status": extraction.status.value,
        },
    )
    if key_error is not None:
        raise AppError(
            str(key_error),
            code=key_error.code,
            status_code=401,
            details={"upload_id": str(upload.id)},
        )
    return _to_response(upload, extraction)


@router.get("/uploads/{upload_id}")
async def get_upload(
    upload_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UploadResponse:
    """Read an upload and its extracted contact back from Postgres (never loads the photo bytes)."""
    stmt = (
        select(Upload, ContactExtraction)
        .outerjoin(ContactExtraction, ContactExtraction.upload_id == Upload.id)
        .where(Upload.id == upload_id)
        .options(defer(Upload.data))
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise AppError("Upload not found.", code="upload_not_found", status_code=404)
    upload, extraction = row
    return _to_response(upload, extraction)


def _to_response(upload: Upload, extraction: ContactExtraction | None) -> UploadResponse:
    return UploadResponse(
        id=upload.id,
        filename=upload.original_filename,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        sha256=upload.sha256,
        hubspot=HubSpotFileResult(
            status=upload.hubspot_status,
            file_id=upload.hubspot_file_id,
            url=upload.hubspot_url,
            error=upload.hubspot_error,
        ),
        contact=(
            ContactFields(
                extractor=extraction.extractor,
                status=extraction.status,
                model=extraction.model,
                error_code=extraction.error_code,
                error=extraction.error,
                evidence={
                    name: FieldEvidenceOut(**ev) for name, ev in (extraction.evidence or {}).items()
                },
                first_name=extraction.first_name,
                last_name=extraction.last_name,
                email=extraction.email,
                phone=extraction.phone,
                job_title=extraction.job_title,
            )
            if extraction
            else None
        ),
    )
