"""Extraction contract shared by every extractor (sample now, OpenAI in Step 3)."""

from dataclasses import dataclass
from typing import Protocol

from app.services.uploads import ValidatedImage


@dataclass(frozen=True)
class ExtractedContact:
    """None means the field was absent or unreadable; it must stay blank, never guessed."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None


class ContactExtractor(Protocol):
    name: str

    async def extract(self, image: ValidatedImage) -> ExtractedContact: ...
