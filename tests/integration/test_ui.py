"""Static UI mount tests: the UI is served at / without shadowing API routes."""

from fastapi.testclient import TestClient

from repair_ai.main import create_app


def test_root_serves_ui():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Repair AI" in response.text


def test_ui_static_assets_served():
    client = TestClient(create_app())
    for asset in ("/app.js", "/styles.css"):
        response = client.get(asset)
        assert response.status_code == 200


def test_ui_mount_does_not_shadow_api_routes():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
