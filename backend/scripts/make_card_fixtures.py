"""Render the synthetic business-card fixtures used by the Step 3 tests.

    uv run python scripts/make_card_fixtures.py

Writes (committed to the repo):
- tests/fixtures/card_clear.png        every field crisp  -> all fields extracted
- tests/fixtures/card_blurry_email.png email row blurred  -> email must come back blank

All data is fictional (example.com is reserved for documentation). Uses Pillow's bundled
scalable font so output is identical on every machine.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# Expected values, mirrored in tests/test_extraction_live.py.
CARD = {
    "name": "Ada Lovelace",
    "job_title": "Head of Engineering",
    "company": "Analytical Engines Ltd",
    "email": "ada.lovelace@example.com",
    "phone": "+1 555 0100",
    "website": "www.example.com",
}

SIZE = (1050, 600)  # 3.5in x 2in at 300 dpi
INK = (20, 32, 56)
MUTED = (90, 100, 120)
ACCENT = (37, 99, 235)
BLUR_RADIUS = 14


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def render_card() -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Return the card image and the bounding box of the email line."""
    img = Image.new("RGB", SIZE, (250, 250, 247))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 18, SIZE[1]), fill=ACCENT)

    x = 80
    draw.text((x, 70), CARD["name"], font=_font(72), fill=INK)
    draw.text((x, 165), CARD["job_title"], font=_font(40), fill=MUTED)
    draw.text((x, 220), CARD["company"], font=_font(36), fill=ACCENT)

    draw.line((x, 300, SIZE[0] - 80, 300), fill=(210, 214, 222), width=3)

    contact_font = _font(38)
    email_xy = (x, 340)
    draw.text(email_xy, CARD["email"], font=contact_font, fill=INK)
    draw.text((x, 410), CARD["phone"], font=contact_font, fill=INK)
    draw.text((x, 480), CARD["website"], font=contact_font, fill=INK)

    left, top, right, bottom = draw.textbbox(email_xy, CARD["email"], font=contact_font)
    pad = 12
    return img, (left - pad, top - pad, right + pad, bottom + pad)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    clear, email_box = render_card()
    clear.save(FIXTURES / "card_clear.png", optimize=True)

    blurry = clear.copy()
    region = blurry.crop(email_box).filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    blurry.paste(region, email_box)
    blurry.save(FIXTURES / "card_blurry_email.png", optimize=True)
    print(f"Wrote fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()
