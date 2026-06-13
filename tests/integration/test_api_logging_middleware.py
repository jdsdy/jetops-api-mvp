from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

TEST_SIGNUP_CODE = "invite-only-2026"


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
        response = client.post("/v1/signup", json={"code": TEST_SIGNUP_CODE})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_repository.insert_api_log.assert_called_once()
    call_kwargs = mock_repository.insert_api_log.call_args.kwargs
    assert call_kwargs["service"] == "fastapi"
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["path"] == "/v1/signup"
    assert call_kwargs["status_code"] == 200
    assert call_kwargs["user_id"] is None
    assert call_kwargs["organisation_id"] is None
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
        response = client.post("/v1/signup", json={"code": "wrong-code"})

    app.dependency_overrides.clear()

    assert response.status_code == 400
    call_kwargs = mock_repository.insert_api_log.call_args.kwargs
    assert call_kwargs["status_code"] == 400
    assert call_kwargs["error_message"] == "Invalid signup code"
