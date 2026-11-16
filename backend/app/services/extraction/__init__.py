"""Contact extraction from images (PDFs in Step 9).

Step 3: OpenAI structured extraction using the user's own key (see keys.py). The Step 2
`SampleContactExtractor` stays as an offline fake for tests.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.services.extraction.base import (
    ContactExtractor,
    ExtractedContact,
    ExtractionError,
    FieldEvidence,
    OpenAIKeyError,
)
from app.services.extraction.keys import make_openai_client, resolve_openai_key
from app.services.extraction.openai_extractor import OpenAIContactExtractor

__all__ = [
    "ContactExtractor",
    "ExtractedContact",
    "ExtractionError",
    "FieldEvidence",
    "OpenAIKeyError",
    "get_contact_extractor",
]


def get_contact_extractor(
    request: Request, key: Annotated[str, Depends(resolve_openai_key)]
) -> ContactExtractor:
    """FastAPI dependency. Tests override this to inject a fake extractor."""
    settings: Settings = request.app.state.settings
    return OpenAIContactExtractor(
        make_openai_client(request, key),
        model=settings.openai_model,
        max_px=settings.openai_max_image_px,
    )
