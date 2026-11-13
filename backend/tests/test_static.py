from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ClientFactory


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><div id=root></div>")
    (d / "assets" / "app.js").write_text("console.log('hi')")
    (d / "favicon.svg").write_text("<svg/>")
    return d


@pytest.fixture
def spa_client(make_client: ClientFactory, dist: Path) -> TestClient:
    return make_client(frontend_dist=dist)


def test_root_serves_index(spa_client: TestClient) -> None:
    res = spa_client.get("/")
    assert res.status_code == 200
    assert "id=root" in res.text


def test_client_side_route_falls_back_to_index(spa_client: TestClient) -> None:
    res = spa_client.get("/imports/123")
    assert res.status_code == 200
    assert "id=root" in res.text


def test_assets_and_root_files_served(spa_client: TestClient) -> None:
    assert spa_client.get("/assets/app.js").text == "console.log('hi')"
    assert spa_client.get("/favicon.svg").text == "<svg/>"


def test_api_paths_never_fall_back_to_index(spa_client: TestClient) -> None:
    res = spa_client.get("/api/nope")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "http_error"
    assert spa_client.get("/api/health").json()["status"] == "ok"


def test_path_traversal_does_not_escape_dist(spa_client: TestClient) -> None:
    res = spa_client.get("/..%2F..%2Fetc%2Fpasswd")
    assert res.status_code == 200
    assert "id=root" in res.text


def test_no_dist_means_no_frontend_route(client: TestClient) -> None:
    assert client.get("/").status_code == 404
