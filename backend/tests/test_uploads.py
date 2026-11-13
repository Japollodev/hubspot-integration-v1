import asyncio
import json
from collections.abc import Callable
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx
import pytest
from fastapi.testclient import TestClient

from app.services.hubspot_files import HubSpotFilesClient, get_hubspot_files
from app.services.uploads import detect_image_type, sanitize_filename
from tests.conftest import ClientFactory, asyncpg_dsn

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 1020  # 1 KiB, valid JPEG signature
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

Handler = Callable[[httpx.Request], httpx.Response]


def fetch_upload(database_url: str, upload_id: str) -> dict[str, Any]:
    async def _q() -> dict[str, Any]:
        conn = await asyncpg.connect(asyncpg_dsn(database_url))
        try:
            row = await conn.fetchrow("SELECT * FROM uploads WHERE id = $1::uuid", upload_id)
            assert row is not None
            return dict(row)
        finally:
            await conn.close()

    return asyncio.run(_q())


@pytest.fixture
def db_client(make_client: ClientFactory, clean_db: str) -> TestClient:
    return make_client(database_url=clean_db)


def use_hubspot(client: TestClient, handler: Handler, seen: list[httpx.Request]) -> None:
    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(
        base_url="https://api.hubapi.test", transport=httpx.MockTransport(recording)
    )
    fake = HubSpotFilesClient(http, token="test-token", folder_path="/test-folder")  # noqa: S106
    client.app.dependency_overrides[get_hubspot_files] = lambda: fake  # type: ignore[attr-defined]


def post_file(client: TestClient, data: bytes, name: str = "card.jpg") -> httpx.Response:
    res: httpx.Response = client.post("/api/uploads", files={"file": (name, data, "image/jpeg")})
    return res


def test_upload_stores_in_postgres_and_hubspot(db_client: TestClient, clean_db: str) -> None:
    seen: list[httpx.Request] = []
    use_hubspot(
        db_client,
        lambda _: httpx.Response(200, json={"id": "987", "url": "https://files.example/987"}),
        seen,
    )

    res = post_file(db_client, JPEG)

    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == "card.jpg"
    assert body["size_bytes"] == len(JPEG)
    assert body["content_type"] == "image/jpeg"
    assert body["hubspot"] == {
        "status": "uploaded",
        "file_id": "987",
        "url": "https://files.example/987",
        "error": None,
    }

    row = fetch_upload(clean_db, body["id"])
    assert row["data"] == JPEG
    assert row["hubspot_status"] == "uploaded"
    assert row["hubspot_file_id"] == "987"

    (req,) = seen
    assert req.url.path == "/files/v3/files"
    assert req.headers["authorization"] == "Bearer test-token"
    assert b'name="folderPath"\r\n\r\n/test-folder' in req.content
    assert json.dumps({"access": "PRIVATE"})[1:-1].encode() in req.content


def test_hubspot_failure_still_returns_200_and_keeps_row(
    db_client: TestClient, clean_db: str
) -> None:
    use_hubspot(db_client, lambda _: httpx.Response(500, json={"message": "boom"}), [])

    res = post_file(db_client, JPEG)

    assert res.status_code == 200
    hubspot = res.json()["hubspot"]
    assert hubspot["status"] == "failed"
    assert "500" in hubspot["error"]
    assert fetch_upload(clean_db, res.json()["id"])["data"] == JPEG


def test_hubspot_unreachable_is_recorded(db_client: TestClient) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    use_hubspot(db_client, down, [])
    res = post_file(db_client, JPEG)
    assert res.status_code == 200
    assert res.json()["hubspot"]["status"] == "failed"


def test_no_token_skips_hubspot(db_client: TestClient, clean_db: str) -> None:
    res = post_file(db_client, PNG, name="card.png")
    assert res.status_code == 200
    assert res.json()["hubspot"]["status"] == "skipped"
    assert res.json()["content_type"] == "image/png"
    assert fetch_upload(clean_db, res.json()["id"])["hubspot_status"] == "skipped"


def test_content_type_comes_from_bytes_not_client(db_client: TestClient) -> None:
    res = db_client.post("/api/uploads", files={"file": ("x.jpg", PNG, "image/jpeg")})
    assert res.json()["content_type"] == "image/png"


def test_filename_is_sanitized(db_client: TestClient) -> None:
    res = post_file(db_client, JPEG, name="../../etc/passwd.jpg")
    assert res.json()["filename"] == "passwd.jpg"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("card.jpg", "card.jpg"),
        ("C:\\Users\\me\\card.jpg", "card.jpg"),
        ("../../x\x00y.jpg", "xy.jpg"),
        ("..", "upload"),
        ("", "upload"),
        (None, "upload"),
        ("a" * 300 + ".jpeg", "a" * 250 + ".jpeg"),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (JPEG[:16], "image/jpeg"),
        (PNG[:16], "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"\x00\x00\x00\x18ftypheic\x00\x00", "image/heic"),
        (b"%PDF-1.7", None),
        (b"GIF89a", None),
    ],
)
def test_detect_image_type(head: bytes, expected: str | None) -> None:
    assert detect_image_type(head) == expected


def test_unsupported_type_rejected(client: TestClient) -> None:
    res = post_file(client, b"just some text pretending to be a jpeg", name="fake.jpg")
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "unsupported_type"


def test_empty_file_rejected(client: TestClient) -> None:
    res = post_file(client, b"")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "empty_file"


def test_missing_file_field_rejected(client: TestClient) -> None:
    res = client.post("/api/uploads", data={"nope": "x"})
    assert res.status_code == 422


def test_file_just_over_limit_rejected_by_validator(make_client: ClientFactory) -> None:
    client = make_client(max_upload_mb=1)
    res = post_file(client, JPEG[:4] + b"\x00" * (1024 * 1024 - 3))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"


def test_huge_request_rejected_by_content_length(make_client: ClientFactory) -> None:
    client = make_client(max_upload_mb=1)
    res = post_file(client, JPEG[:4] + b"\x00" * (2 * 1024 * 1024))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"
