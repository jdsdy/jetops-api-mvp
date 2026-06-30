from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.integration_dependencies import get_api_key_repository
from app.core.config import Settings, get_settings
from app.main import app

from tests.conftest import integration_auth_headers

TEST_SIGNUP_CODE = "invite-only-2026"
API_CLIENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def test_api_logging_middleware_records_signup_request() -> None:
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
    mock_repository = MagicMock()

    with (
        patch("app.api.api_logging.ApiLogRepository", return_value=mock_repository),
        TestClient(app) as client,
    ):
        response = client.post("/v1/app/signup", json={"code": TEST_SIGNUP_CODE})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_repository.insert_api_log.assert_called_once()
    call_kwargs = mock_repository.insert_api_log.call_args.kwargs
    assert call_kwargs["service"] == "fastapi"
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["path"] == "/v1/app/signup"
    assert call_kwargs["status_code"] == 200
    assert call_kwargs["user_id"] is None
    assert call_kwargs["organisation_id"] is None
    assert call_kwargs["api_client_id"] is None
    assert call_kwargs["error_message"] is None
    assert isinstance(call_kwargs["duration_ms"], int)


def test_api_logging_middleware_records_error_message_for_failed_signup() -> None:
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
    mock_repository = MagicMock()

    with (
        patch("app.api.api_logging.ApiLogRepository", return_value=mock_repository),
        TestClient(app) as client,
    ):
        response = client.post("/v1/app/signup", json={"code": "wrong-code"})

    app.dependency_overrides.clear()

    assert response.status_code == 400
    call_kwargs = mock_repository.insert_api_log.call_args.kwargs
    assert call_kwargs["status_code"] == 400
    assert call_kwargs["error_message"] == "Invalid signup code"


def test_api_logging_middleware_records_api_client_id_for_integration_request() -> None:
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
    mock_repository = MagicMock()
    mock_api_key_repository = MagicMock()
    mock_api_key_repository.lookup_by_hash.return_value = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "api_client_id": str(API_CLIENT_ID),
        "is_active": True,
        "revoked_at": None,
        "expires_at": None,
        "api_clients": {
            "is_active": True,
            "organisation_id": None,
        },
    }
    app.dependency_overrides[get_api_key_repository] = lambda: mock_api_key_repository

    with (
        patch("app.api.api_logging.ApiLogRepository", return_value=mock_repository),
        TestClient(app) as client,
    ):
        response = client.get("/v1/test", headers=integration_auth_headers())

    app.dependency_overrides.clear()

    assert response.status_code == 200
    call_kwargs = mock_repository.insert_api_log.call_args.kwargs
    assert call_kwargs["path"] == "/v1/test"
    assert call_kwargs["api_client_id"] == API_CLIENT_ID
