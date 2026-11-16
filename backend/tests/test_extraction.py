"""Step 3: OpenAI extraction, blank rules, image prep, and bring-your-own-key wiring.

OpenAI is never called for real here: the SDK's HTTP client is swapped for an
httpx2.MockTransport. The opt-in live test is tests/test_extraction_live.py.
"""

import asyncio
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx2
import openai
import pillow_heif
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services.extraction import ExtractionError, OpenAIKeyError, get_contact_extractor
from app.services.extraction.base import ExtractedContact
from app.services.extraction.image_prep import prepare_for_vision
from app.services.extraction.openai_extractor import (
    CardExtraction,
    OpenAIContactExtractor,
    apply_blank_rules,
)
from app.services.uploads import ValidatedImage
from tests.conftest import ClientFactory, asyncpg_dsn

FIXTURES = Path(__file__).parent / "fixtures"
CLEAR_CARD = (FIXTURES / "card_clear.png").read_bytes()
USER_KEY = "sk-user-test-key-1234"
OpenAIHandler = Callable[[httpx2.Request], httpx2.Response]


# ---------------------------------------------------------------- helpers


def card_field(value: str | None, legibility: str = "clear", **kw: Any) -> dict[str, Any]:
    return {
        "value": value,
        "source_text": kw.get("source_text", value),
        "legibility": legibility,
        "note": kw.get("note"),
    }


def card(**overrides: dict[str, Any]) -> dict[str, Any]:
    base = {
        "first_name": card_field("Ada"),
        "last_name": card_field("Lovelace"),
        "email": card_field("ada.lovelace@example.com"),
        "phone": card_field("+1 555 0100"),
        "job_title": card_field("Head of Engineering"),
    }
    return {**base, **overrides}


def responses_api_body(payload: dict[str, Any]) -> dict[str, Any]:
    """Minimal OpenAI Responses API body whose output text is `payload` as JSON."""
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": "completed",
        "model": "gpt-4o-mini",
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": json.dumps(payload), "annotations": []}
                ],
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
    }


def image_of(data: bytes, content_type: str = "image/png") -> ValidatedImage:
    return ValidatedImage(filename="card", content_type=content_type, data=data, sha256="x")


def extractor_with(handler: OpenAIHandler) -> OpenAIContactExtractor:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = openai.AsyncOpenAI(api_key=USER_KEY, http_client=http, max_retries=0)
    return OpenAIContactExtractor(client, model="gpt-4o-mini", max_px=2048)


@pytest.fixture
def openai_mock(monkeypatch: pytest.MonkeyPatch) -> Callable[[OpenAIHandler], list[httpx2.Request]]:
    """Route the app's shared OpenAI pool to a handler. Call BEFORE make_client()."""

    def install(handler: OpenAIHandler) -> list[httpx2.Request]:
        seen: list[httpx2.Request] = []

        def recording(request: httpx2.Request) -> httpx2.Response:
            seen.append(request)
            return handler(request)

        def factory(**kwargs: Any) -> httpx2.AsyncClient:
            return httpx2.AsyncClient(transport=httpx2.MockTransport(recording), **kwargs)

        monkeypatch.setattr(openai, "DefaultAsyncHttpxClient", factory)
        return seen

    return install


def count_uploads(database_url: str) -> int:
    async def _q() -> int:
        conn = await asyncpg.connect(asyncpg_dsn(database_url))
        try:
            return int(await conn.fetchval("SELECT count(*) FROM uploads"))
        finally:
            await conn.close()

    return asyncio.run(_q())


def post_card(client: TestClient, *, key: str | None = USER_KEY) -> httpx2.Response:
    headers = {"X-OpenAI-Key": key} if key else {}
    res: httpx2.Response = client.post(
        "/api/uploads", files={"file": ("card.png", CLEAR_CARD, "image/png")}, headers=headers
    )
    return res


# ---------------------------------------------------------------- 3.6 blank rules


def test_clear_fields_are_kept_with_evidence() -> None:
    result = apply_blank_rules(CardExtraction.model_validate(card()), model="m")
    assert result.values() == {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada.lovelace@example.com",
        "phone": "+1 555 0100",
        "job_title": "Head of Engineering",
    }
    assert result.model == "m"
    assert result.evidence["email"].legibility == "clear"


def test_partial_field_is_blanked_but_evidence_kept() -> None:
    raw = card(
        email=card_field(
            "ada.lovelace@example.com",  # model "guessed" a value despite rating it partial
            "partial",
            source_text="ada.lov???@exa???.com",
            note="blurred",
        )
    )
    result = apply_blank_rules(CardExtraction.model_validate(raw))
    assert result.email is None
    ev = result.evidence["email"]
    assert (ev.legibility, ev.source_text, ev.note) == (
        "partial",
        "ada.lov???@exa???.com",
        "blurred",
    )


@pytest.mark.parametrize("legibility", ["unreadable", "absent"])
def test_unreadable_or_absent_is_blank(legibility: str) -> None:
    raw = card(phone=card_field(None, legibility, source_text=None))
    assert apply_blank_rules(CardExtraction.model_validate(raw)).phone is None


@pytest.mark.parametrize(
    "bad", ["ada.lovelace@exarnple", "ada lovelace@example.com", "ada.example.com"]
)
def test_malformed_email_is_blanked(bad: str) -> None:
    result = apply_blank_rules(CardExtraction.model_validate(card(email=card_field(bad))))
    assert result.email is None
    assert result.evidence["email"].note == "not a valid email shape"
    assert result.evidence["email"].source_text == bad


def test_whitespace_trimmed_and_empty_clear_value_treated_as_unreadable() -> None:
    raw = card(job_title=card_field("  Head   of\nEngineering "), phone=card_field("   "))
    result = apply_blank_rules(CardExtraction.model_validate(raw))
    assert result.job_title == "Head of Engineering"
    assert result.phone is None
    assert result.evidence["phone"].legibility == "unreadable"


# ---------------------------------------------------------------- 3.4 image prep


def test_small_png_passes_through_untouched() -> None:
    assert prepare_for_vision(image_of(CLEAR_CARD), max_px=2048) == (CLEAR_CARD, "image/png")


def test_heic_is_converted_to_jpeg() -> None:
    out = io.BytesIO()
    Image.new("RGB", (64, 32), "white").save(out, format="HEIF")
    data, mime = prepare_for_vision(image_of(out.getvalue(), "image/heic"), max_px=2048)
    assert mime == "image/jpeg"
    assert data[:3] == b"\xff\xd8\xff"
    assert pillow_heif.is_supported(out.getvalue())


def test_large_image_is_downscaled() -> None:
    data, mime = prepare_for_vision(image_of(CLEAR_CARD), max_px=500)
    assert mime == "image/png"
    with Image.open(io.BytesIO(data)) as img:
        assert max(img.size) == 500


def test_exif_rotation_is_applied() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90° CW to display"
    out = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(out, format="JPEG", exif=exif)
    data, mime = prepare_for_vision(image_of(out.getvalue(), "image/jpeg"), max_px=2048)
    assert mime == "image/jpeg"
    with Image.open(io.BytesIO(data)) as img:
        assert img.size == (100, 200)


def test_undecodable_image_raises_extraction_error() -> None:
    with pytest.raises(ExtractionError) as exc:
        prepare_for_vision(image_of(b"\x89PNG\r\n\x1a\n" + b"junk"), max_px=2048)
    assert exc.value.code == "image_unreadable"


# ---------------------------------------------------------------- 3.5 extractor


def test_extractor_sends_image_and_strict_schema_with_user_key() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=responses_api_body(card()))

    result = asyncio.run(extractor_with(handler).extract(image_of(CLEAR_CARD)))

    assert result.email == "ada.lovelace@example.com"
    (req,) = seen
    assert req.url.path.endswith("/responses")
    assert req.headers["authorization"] == f"Bearer {USER_KEY}"
    body = json.loads(req.content)
    assert body["model"] == "gpt-4o-mini"
    assert body["temperature"] == 0
    assert body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    image_part = body["input"][0]["content"][1]
    assert image_part["type"] == "input_image"
    assert image_part["image_url"].startswith("data:image/png;base64,")
    assert "never infer" in body["instructions"].lower()


def test_extractor_401_means_invalid_key() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"error": {"message": "Incorrect API key"}})

    with pytest.raises(OpenAIKeyError) as exc:
        asyncio.run(extractor_with(handler).extract(image_of(CLEAR_CARD)))
    assert exc.value.code == "openai_key_invalid"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (429, "openai_rate_limited"),
        (403, "openai_model_unavailable"),
        (404, "openai_model_unavailable"),
        (500, "openai_error"),
    ],
)
def test_extractor_maps_api_errors(status: int, code: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json={"error": {"message": "nope"}})

    with pytest.raises(ExtractionError) as exc:
        asyncio.run(extractor_with(handler).extract(image_of(CLEAR_CARD)))
    assert exc.value.code == code
    assert USER_KEY not in str(exc.value)


def test_extractor_timeout_is_extraction_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    with pytest.raises(ExtractionError) as exc:
        asyncio.run(extractor_with(handler).extract(image_of(CLEAR_CARD)))
    assert exc.value.code == "openai_timeout"


# ---------------------------------------------------------------- 3.7/3.8 BYOK through the API


@pytest.fixture
def real_client(make_client: ClientFactory, clean_db: str) -> TestClient:
    return make_client(database_url=clean_db, fake_extractor=False)


def test_upload_without_key_is_rejected_before_storing(
    real_client: TestClient, clean_db: str
) -> None:
    res = post_card(real_client, key=None)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "openai_key_missing"
    assert count_uploads(clean_db) == 0


def test_upload_with_user_key_extracts_and_stores_evidence(
    openai_mock: Callable[[OpenAIHandler], list[httpx2.Request]],
    make_client: ClientFactory,
    clean_db: str,
) -> None:
    blurry_email = card_field(None, "unreadable", source_text="???@???", note="blurred")
    seen = openai_mock(
        lambda _: httpx2.Response(200, json=responses_api_body(card(email=blurry_email)))
    )
    client = make_client(database_url=clean_db, fake_extractor=False)

    res = post_card(client)

    assert res.status_code == 200
    contact = res.json()["contact"]
    assert contact["extractor"] == "openai"
    assert contact["status"] == "succeeded"
    assert contact["model"] == "gpt-4o-mini"
    assert contact["first_name"] == "Ada"
    assert contact["email"] is None
    assert contact["evidence"]["email"] == {
        "legibility": "unreadable",
        "source_text": "???@???",
        "note": "blurred",
    }
    assert seen[0].headers["authorization"] == f"Bearer {USER_KEY}"

    # Evidence round-trips through Postgres.
    again = client.get(f"/api/uploads/{res.json()['id']}").json()
    assert again["contact"] == contact


def test_invalid_key_returns_401_but_keeps_upload(
    openai_mock: Callable[[OpenAIHandler], list[httpx2.Request]],
    make_client: ClientFactory,
    clean_db: str,
) -> None:
    openai_mock(lambda _: httpx2.Response(401, json={"error": {"message": "bad key"}}))
    client = make_client(database_url=clean_db, fake_extractor=False)

    res = post_card(client, key="sk-wrong")

    assert res.status_code == 401
    err = res.json()["error"]
    assert err["code"] == "openai_key_invalid"
    stored = client.get(f"/api/uploads/{err['details']['upload_id']}").json()
    assert stored["contact"]["status"] == "failed"
    assert stored["contact"]["error_code"] == "openai_key_invalid"
    assert count_uploads(clean_db) == 1


def test_extraction_failure_is_recorded_and_returns_200(
    make_client: ClientFactory, clean_db: str
) -> None:
    class Broken:
        name = "openai"

        async def extract(self, image: ValidatedImage) -> ExtractedContact:
            raise ExtractionError("OpenAI timed out reading the photo.", code="openai_timeout")

    client = make_client(database_url=clean_db)
    client.app.dependency_overrides[get_contact_extractor] = Broken  # type: ignore[attr-defined]

    res = post_card(client)

    assert res.status_code == 200
    contact = res.json()["contact"]
    assert contact["status"] == "failed"
    assert contact["error_code"] == "openai_timeout"
    assert contact["email"] is None


def test_dev_env_key_is_used_when_no_header(
    openai_mock: Callable[[OpenAIHandler], list[httpx2.Request]],
    make_client: ClientFactory,
    clean_db: str,
) -> None:
    seen = openai_mock(lambda _: httpx2.Response(200, json=responses_api_body(card())))
    client = make_client(database_url=clean_db, fake_extractor=False, openai_api_key="sk-dev-env")
    assert post_card(client, key=None).status_code == 200
    assert seen[0].headers["authorization"] == "Bearer sk-dev-env"


def test_header_key_wins_over_env_key(
    openai_mock: Callable[[OpenAIHandler], list[httpx2.Request]],
    make_client: ClientFactory,
    clean_db: str,
) -> None:
    seen = openai_mock(lambda _: httpx2.Response(200, json=responses_api_body(card())))
    client = make_client(database_url=clean_db, fake_extractor=False, openai_api_key="sk-dev")
    post_card(client)
    assert seen[0].headers["authorization"] == f"Bearer {USER_KEY}"


def test_production_ignores_env_key(make_client: ClientFactory, clean_db: str) -> None:
    client = make_client(
        database_url=clean_db,
        fake_extractor=False,
        environment="production",
        openai_api_key="sk-developer",
    )
    res = post_card(client, key=None)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "openai_key_missing"


# ---------------------------------------------------------------- verify / status endpoints


def test_status_reports_server_key_mode(make_client: ClientFactory) -> None:
    assert make_client().get("/api/openai/status").json() == {
        "server_key_available": False,
        "model": "gpt-4o-mini",
    }
    assert (
        make_client(openai_api_key="sk-dev")
        .get("/api/openai/status")
        .json()["server_key_available"]
    )
    prod = make_client(openai_api_key="sk-dev", environment="production")
    assert not prod.get("/api/openai/status").json()["server_key_available"]


@pytest.mark.parametrize(
    ("status", "valid", "message_part"),
    [(200, True, None), (401, False, "rejected"), (404, False, "can't use the model")],
)
def test_verify_key(
    openai_mock: Callable[[OpenAIHandler], list[httpx2.Request]],
    make_client: ClientFactory,
    status: int,
    valid: bool,
    message_part: str | None,
) -> None:
    seen = openai_mock(
        lambda _: httpx2.Response(status, json={"id": "gpt-4o-mini", "object": "model"})
    )
    res = make_client().post("/api/openai/verify", headers={"X-OpenAI-Key": USER_KEY})
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is valid
    if message_part:
        assert message_part in body["message"]
    assert seen[0].url.path.endswith("/models/gpt-4o-mini")
    assert seen[0].headers["authorization"] == f"Bearer {USER_KEY}"


def test_verify_without_key_is_400(make_client: ClientFactory) -> None:
    res = make_client(openai_api_key="sk-dev").post("/api/openai/verify")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "openai_key_missing"


def test_verify_when_openai_unreachable_is_502(
    openai_mock: Callable[[OpenAIHandler], list[httpx2.Request]], make_client: ClientFactory
) -> None:
    def down(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route", request=request)

    openai_mock(down)
    res = make_client().post("/api/openai/verify", headers={"X-OpenAI-Key": USER_KEY})
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "openai_unreachable"
