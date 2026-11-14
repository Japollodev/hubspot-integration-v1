"""Contact extraction from images and PDFs.

Step 2 ships a fixed sample extractor. Step 3 adds OpenAI structured extraction behind the same
`ContactExtractor` protocol; Step 9 adds PDF input.
"""

from app.services.extraction.base import ContactExtractor, ExtractedContact
from app.services.extraction.sample import SampleContactExtractor

__all__ = ["ContactExtractor", "ExtractedContact", "get_contact_extractor"]


def get_contact_extractor() -> ContactExtractor:
    """FastAPI dependency. Tests override this to inject a fake extractor."""
    return SampleContactExtractor()
