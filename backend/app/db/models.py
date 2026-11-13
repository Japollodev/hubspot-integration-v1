"""ORM models. Schema changes go through Alembic migrations (backend/alembic/versions)."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, LargeBinary, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class HubSpotStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)

    hubspot_status: Mapped[HubSpotStatus] = mapped_column(
        Enum(
            HubSpotStatus,
            name="hubspot_status",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=HubSpotStatus.PENDING,
    )
    hubspot_file_id: Mapped[str | None] = mapped_column(String(64))
    hubspot_url: Mapped[str | None] = mapped_column(Text)
    hubspot_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
