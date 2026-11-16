"""Build-plan Step 3 "Done when", against the REAL OpenAI API. Opt-in; costs a few cents.

    OPENAI_API_KEY=sk-... make test-live

- A clear card yields the expected fields.
- An unreadable (blurred) email is left blank, with evidence saying why.
"""

import asyncio
import os
from pathlib import Path

import openai
import pytest

from app.core.config import Settings
from app.services.extraction.base import ExtractedContact
from app.services.extraction.openai_extractor import OpenAIContactExtractor
from app.services.uploads import ValidatedImage

pytestmark = pytest.mark.live

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada.lovelace@example.com",
    "phone": "+1 555 0100",
    "job_title": "Head of Engineering",
}


def _key() -> str:
    key = os.environ.get("OPENAI_API_KEY") or (
        k.get_secret_value() if (k := Settings().openai_api_key) else None
    )
    if not key:
        pytest.skip("Set OPENAI_API_KEY to run live extraction tests")
    return key


def _extract(fixture: str) -> ExtractedContact:
    settings = Settings()
    data = (FIXTURES / fixture).read_bytes()
    image = ValidatedImage(filename=fixture, content_type="image/png", data=data, sha256="live")

    async def run() -> ExtractedContact:
        async with openai.AsyncOpenAI(api_key=_key(), timeout=settings.openai_timeout_s) as client:
            extractor = OpenAIContactExtractor(
                client, model=settings.openai_model, max_px=settings.openai_max_image_px
            )
            return await extractor.extract(image)

    return asyncio.run(run())


def test_clear_card_yields_expected_fields() -> None:
    result = _extract("card_clear.png")
    assert result.values() == EXPECTED


def test_blurry_email_is_left_blank() -> None:
    result = _extract("card_blurry_email.png")
    assert result.email is None
    assert result.evidence["email"].legibility != "clear"
    # The crisp fields on the same card still come through.
    assert result.first_name == "Ada"
    assert result.phone == "+1 555 0100"
