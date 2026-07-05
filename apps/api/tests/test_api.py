from fastapi.testclient import TestClient

import api


def test_health_endpoint():
    response = TestClient(api.app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_optional_api_key(monkeypatch):
    monkeypatch.setenv("AUDIOMIND_API_KEY", "test-secret")
    client = TestClient(api.app)
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={"X-API-Key": "test-secret"}).status_code == 200
