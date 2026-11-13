"""Upload validation: size limits, magic-byte type detection, filename sanitising, hashing.

Client-supplied filename and MIME type are untrusted; the stored content type is the one
detected from the file's bytes.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import UploadFile

from app.core.errors import AppError

READ_CHUNK = 1024 * 1024
MAX_FILENAME_LEN = 255
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}
_UNSAFE_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class ValidatedImage:
    filename: str
    content_type: str
    data: bytes
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def detect_image_type(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in _HEIF_BRANDS:
        return "image/heic"
    return None


def sanitize_filename(name: str | None) -> str:
    base = PurePosixPath((name or "").replace("\\", "/")).name
    base = _UNSAFE_CHARS.sub("", base).strip()
    if not base or base in {".", ".."}:
        return "upload"
    if len(base) > MAX_FILENAME_LEN:
        suffix = PurePosixPath(base).suffix[:16]
        base = base[: MAX_FILENAME_LEN - len(suffix)] + suffix
    return base


def too_large(max_bytes: int) -> AppError:
    return AppError(
        f"File is larger than the {max_bytes // (1024 * 1024)} MB limit.",
        code="file_too_large",
        status_code=413,
    )


async def read_and_validate(file: UploadFile, *, max_bytes: int) -> ValidatedImage:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(READ_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise too_large(max_bytes)
        chunks.append(chunk)
    data = b"".join(chunks)

    if not data:
        raise AppError("The uploaded file is empty.", code="empty_file", status_code=400)

    content_type = detect_image_type(data[:32])
    if content_type is None:
        raise AppError(
            "Unsupported file type. Upload a JPEG, PNG, WebP or HEIC photo.",
            code="unsupported_type",
            status_code=415,
        )

    return ValidatedImage(
        filename=sanitize_filename(file.filename),
        content_type=content_type,
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
    )
