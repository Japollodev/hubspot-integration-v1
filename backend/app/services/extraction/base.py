"""Extraction contract shared by every extractor (sample, OpenAI, PDF in Step 9)."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.services.uploads import ValidatedImage

Legibility = Literal["clear", "partial", "unreadable", "absent"]

CONTACT_FIELDS: tuple[str, ...] = ("first_name", "last_name", "email", "phone", "job_title")


@dataclass(frozen=True)
class FieldEvidence:
    """What was actually seen on the card for one field, kept for human review (Step 7).

    `source_text` is the raw visible text even when the value was blanked, so a reviewer can
    tell "not on the card" (absent) apart from "on the card but blurry" (unreadable/partial).
    """

    legibility: Legibility
    source_text: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ExtractedContact:
    """None means the field was absent or unreadable; it must stay blank, never guessed."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None
    # Keyed by field name (see CONTACT_FIELDS). Empty for extractors that keep no evidence.
    evidence: dict[str, FieldEvidence] = field(default_factory=dict)
    # Model that produced the values, if any (e.g. "gpt-4o-mini").
    model: str | None = None

    def values(self) -> dict[str, str | None]:
        return {name: getattr(self, name) for name in CONTACT_FIELDS}


class ExtractionError(Exception):
    """Extraction failed for a reason the user can't fix by changing their key.

    Recorded on the extraction row (status=failed); the upload itself still succeeds.
    `str(exc)` is safe to persist and show: it never contains key material.
    """

    def __init__(self, message: str, *, code: str = "extraction_failed") -> None:
        super().__init__(message)
        self.code = code


class OpenAIKeyError(Exception):
    """The OpenAI key is missing or was rejected. The user must supply a (new) key."""

    def __init__(self, reason: Literal["missing", "invalid"]) -> None:
        self.reason = reason
        self.code = f"openai_key_{reason}"
        super().__init__(
            "Add your OpenAI API key to extract contacts."
            if reason == "missing"
            else "OpenAI rejected the API key. Check it and enter it again."
        )


class ContactExtractor(Protocol):
    name: str

    async def extract(self, image: ValidatedImage) -> ExtractedContact: ...
