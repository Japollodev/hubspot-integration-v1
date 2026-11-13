from fastapi.testclient import TestClient

from app import __version__


def test_health_ok(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": __version__}


def test_unknown_api_route_returns_json_error(client: TestClient) -> None:
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "http_error"
