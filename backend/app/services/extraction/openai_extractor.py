"""Build-plan Step 3: structured contact extraction from a business-card photo with OpenAI vision.

Two layers keep "absent or unreadable fields stay blank":
1. The prompt tells the model to transcribe only, never infer, and to rate each field's legibility.
2. `apply_blank_rules` enforces it in code: a value survives only if the model rated it "clear"
   (and, for email, it has an email shape). Models can still guess; this guard cannot.

The model's raw reading (`source_text`, legibility, note) is kept as evidence for review.
"""

import base64
import re
from typing import Literal

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.services.extraction.base import (
    CONTACT_FIELDS,
    ExtractedContact,
    ExtractionError,
    FieldEvidence,
    OpenAIKeyError,
)
from app.services.extraction.image_prep import prepare_for_vision
from app.services.uploads import ValidatedImage

# Deliberately loose: a shape check that catches misreads ("ada@exarnple"), not real validation
# (that is Step 4). local@domain.tld, no spaces, TLD of 2+ letters.
EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

SYSTEM_PROMPT = """\
You read business cards. Transcribe contact details exactly as printed on the card in the image.

Rules:
- Transcribe only. Never infer, guess, complete, or correct a value. Do not build an email from \
a name and a website, do not add a country code, do not fix spelling.
- For each field, rate legibility:
  - "clear": every character is printed on the card and you can read it with certainty.
  - "partial": the field is on the card but some characters are blurred, cut off, or uncertain.
  - "unreadable": the field is on the card but cannot be read.
  - "absent": the field is not on the card.
- value: the exact text when legibility is "clear"; otherwise null.
- source_text: the characters you can actually see for this field, even when partial \
(use "?" for unreadable characters); null when absent.
- note: a few words on why the field is not clear (e.g. "blurred", "cut off"); otherwise null.
- first_name / last_name: split the printed person's name into given name(s) and family name.
- job_title: the person's role or title, not the company name.
- phone: the primary phone number exactly as printed, including any + and spacing.
"""

USER_PROMPT = "Extract the contact details from this business card."


class CardField(BaseModel):
    """One field as the model read it. Every key is required (nullable) for strict outputs."""

    value: str | None = Field(description="Exact text if legibility is 'clear', else null.")
    source_text: str | None = Field(description="Visible characters, '?' for unreadable ones.")
    legibility: Literal["clear", "partial", "unreadable", "absent"]
    note: str | None = Field(description="Why the field is not clear, else null.")


class CardExtraction(BaseModel):
    """Structured-output schema sent to OpenAI."""

    first_name: CardField
    last_name: CardField
    email: CardField
    phone: CardField
    job_title: CardField


def _clean(text: str | None) -> str | None:
    text = " ".join(text.split()) if text else None
    return text or None


def apply_blank_rules(raw: CardExtraction, *, model: str | None = None) -> ExtractedContact:
    """Keep a value only when the model rated it clear and it passes shape checks.

    Anything blanked keeps its evidence (what was seen + why it was blanked).
    """
    values: dict[str, str | None] = {}
    evidence: dict[str, FieldEvidence] = {}

    for name in CONTACT_FIELDS:
        read: CardField = getattr(raw, name)
        value = _clean(read.value)
        source_text = _clean(read.source_text) or value
        legibility = read.legibility
        note = _clean(read.note)

        if legibility != "clear":
            value = None
        elif value is None:
            # "clear" but nothing to show is contradictory; treat as not readable.
            legibility, note = "unreadable", note or "no text returned"
        elif name == "email" and not EMAIL_SHAPE.match(value):
            value = None
            legibility, note = "partial", "not a valid email shape"

        values[name] = value
        evidence[name] = FieldEvidence(legibility=legibility, source_text=source_text, note=note)

    return ExtractedContact(**values, evidence=evidence, model=model)


class OpenAIContactExtractor:
    """Uses the caller's (user's) OpenAI key via the injected client. Never logs the key."""

    name = "openai"

    def __init__(self, client: AsyncOpenAI, *, model: str, max_px: int) -> None:
        self._client = client
        self._model = model
        self._max_px = max_px

    async def extract(self, image: ValidatedImage) -> ExtractedContact:
        data, mime = prepare_for_vision(image, max_px=self._max_px)
        data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=SYSTEM_PROMPT,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": USER_PROMPT},
                            {"type": "input_image", "image_url": data_url, "detail": "high"},
                        ],
                    }
                ],
                text_format=CardExtraction,
                temperature=0,
                store=False,  # don't retain users' card photos on OpenAI's side
            )
        except openai.AuthenticationError as exc:
            raise OpenAIKeyError("invalid") from exc
        except openai.APIError as exc:
            raise _to_extraction_error(exc, self._model) from exc
        except (openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError) as exc:
            raise ExtractionError("OpenAI did not return a complete reading.") from exc

        parsed = response.output_parsed
        if not isinstance(parsed, CardExtraction):
            raise ExtractionError("OpenAI declined to read this image.", code="openai_refused")
        return apply_blank_rules(parsed, model=self._model)


def _to_extraction_error(exc: openai.APIError, model: str) -> ExtractionError:
    """Map SDK errors to short, user-safe messages (no key material, no raw payloads)."""
    if isinstance(exc, openai.APITimeoutError):
        return ExtractionError("OpenAI timed out reading the photo.", code="openai_timeout")
    if isinstance(exc, openai.APIConnectionError):
        return ExtractionError("OpenAI could not be reached.", code="openai_unreachable")
    if isinstance(exc, openai.RateLimitError):
        return ExtractionError(
            "Your OpenAI account hit a rate limit or is out of quota.", code="openai_rate_limited"
        )
    if isinstance(exc, openai.PermissionDeniedError | openai.NotFoundError):
        return ExtractionError(
            f"Your OpenAI key can't use the model '{model}'.", code="openai_model_unavailable"
        )
    status = getattr(exc, "status_code", None)
    return ExtractionError(
        f"OpenAI returned an error{f' ({status})' if status else ''}.", code="openai_error"
    )
