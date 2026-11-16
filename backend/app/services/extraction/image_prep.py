"""Turn an accepted upload into an image OpenAI vision will accept and read well.

- HEIC (iPhone default) is not accepted by OpenAI -> re-encode as JPEG.
- Phones store many photos sideways with an EXIF "rotate" flag -> apply it, so the card is upright.
- Very large photos cost more tokens without reading better -> cap the long edge.

Only the copy sent to OpenAI is transformed; the original bytes stored in Postgres are untouched.
"""

import io

import pillow_heif
from PIL import Image, ImageOps

from app.services.extraction.base import ExtractionError
from app.services.uploads import ValidatedImage

pillow_heif.register_heif_opener()

# Formats OpenAI vision accepts as-is (when no rotation/resize is needed).
_PASSTHROUGH = {"image/jpeg", "image/png", "image/webp"}
_JPEG_QUALITY = 90
# EXIF tag 0x0112 = Orientation; 1 means "already upright".
_EXIF_ORIENTATION = 0x0112


def prepare_for_vision(image: ValidatedImage, *, max_px: int) -> tuple[bytes, str]:
    """Return (bytes, mime type) ready to send to OpenAI vision."""
    try:
        with Image.open(io.BytesIO(image.data)) as opened:
            needs_rotation = opened.getexif().get(_EXIF_ORIENTATION, 1) != 1
            too_big = max(opened.size) > max_px
            if image.content_type in _PASSTHROUGH and not needs_rotation and not too_big:
                return image.data, image.content_type

            img = ImageOps.exif_transpose(opened)
            if too_big:
                img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

            # Keep PNG/WebP (lossless text edges); everything else (HEIC, JPEG) -> JPEG.
            if image.content_type in {"image/png", "image/webp"}:
                fmt, mime = ("PNG", "image/png")
            else:
                fmt, mime = ("JPEG", "image/jpeg")
                if img.mode not in {"RGB", "L"}:
                    img = img.convert("RGB")

            out = io.BytesIO()
            img.save(out, format=fmt, **({"quality": _JPEG_QUALITY} if fmt == "JPEG" else {}))
            return out.getvalue(), mime
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ExtractionError(
            "The photo could not be decoded for extraction.", code="image_unreadable"
        ) from exc
