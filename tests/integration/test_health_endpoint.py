from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200_with_ok_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
