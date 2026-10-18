"""Health endpoint tests: no authentication, no LLM calls."""

from fastapi.testclient import TestClient

from repair_ai.main import create_app


def test_liveness():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness():
    client = TestClient(create_app())
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
