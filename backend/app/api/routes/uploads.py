import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import HubSpotStatus, Upload
from app.db.session import get_session
from app.schemas.uploads import HubSpotFileResult, UploadResponse
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

    # 2. HubSpot Files. A failure here is recorded, not raised: the upload itself succeeded.
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
        },
    )
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
    )
