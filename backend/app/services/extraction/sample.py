"""Build-plan Step 2: a fixed contact so the UI and storage can be built before real extraction."""

from app.services.extraction.base import ExtractedContact
from app.services.uploads import ValidatedImage

SAMPLE_CONTACT = ExtractedContact(
    first_name="Ada",
    last_name="Lovelace",
    email="ada.lovelace@example.com",
    phone="+1 555 0100",
    job_title="Head of Engineering",
)


class SampleContactExtractor:
    name = "sample"

    async def extract(self, image: ValidatedImage) -> ExtractedContact:
        return SAMPLE_CONTACT
