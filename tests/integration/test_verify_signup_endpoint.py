import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

TEST_SIGNUP_CODE = "invite-only-2026"


@pytest.fixture
def signup_client() -> TestClient:
    settings = Settings(
        API_KEY="test-api-key",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="test-secret-key",
        ANTHROPIC_API_KEY="test-anthropic-key",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="test-upstash-token",
        BETA_SIGNUP_CODE=TEST_SIGNUP_CODE,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_verify_signup_code_returns_200_when_code_matches(signup_client: TestClient) -> None:
    response = signup_client.post(
        "/v1/signup",
        json={"code": TEST_SIGNUP_CODE},
    )

    assert response.status_code == 200


def test_verify_signup_code_returns_400_when_code_does_not_match(
    signup_client: TestClient,
) -> None:
    response = signup_client.post(
        "/v1/signup",
        json={"code": "wrong-code"},
    )

    assert response.status_code == 400


def test_verify_signup_code_returns_422_when_code_missing(signup_client: TestClient) -> None:
    response = signup_client.post("/v1/signup", json={})

    assert response.status_code == 422
