from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from supabase_auth.types import User

from app.api.dependencies import get_authenticated_user, verify_api_key
from app.api.rate_limit import rate_limit_begin_analysis, rate_limit_create_job
from app.api.v1.endpoints.jobs import get_job_service
from app.core.config import Settings, get_settings
from app.main import app
from app.services.job_service import JobService

TEST_API_KEY = "test-api-key"
TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
ORG_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
FLIGHT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PLAN_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
STORAGE_PATH = f"{ORG_ID}/{FLIGHT_ID}/{PLAN_ID}/briefing.pdf"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        API_KEY=TEST_API_KEY,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="test-secret-key",
        ANTHROPIC_API_KEY="test-anthropic-key",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="test-upstash-token",
    )


@pytest.fixture
def mock_user() -> User:
    return User(
        id=TEST_USER_ID,
        app_metadata={},
        user_metadata={},
        aud="authenticated",
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def mock_job_service() -> MagicMock:
    return MagicMock(spec=JobService)


@pytest.fixture
def client(
    test_settings: Settings,
    mock_user: User,
    mock_job_service: MagicMock,
) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user
    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    app.dependency_overrides[rate_limit_create_job] = lambda: None
    app.dependency_overrides[rate_limit_begin_analysis] = lambda: None

    with (
        patch("app.api.v1.endpoints.jobs.run_extraction"),
        TestClient(app) as test_client,
    ):
        yield test_client

    app.dependency_overrides.clear()


def valid_job_payload() -> dict[str, str]:
    return {
        "organisation_id": str(ORG_ID),
        "flight_id": str(FLIGHT_ID),
        "flight_plan_id": str(PLAN_ID),
        "storage_path": STORAGE_PATH,
    }


def auth_headers(api_key: str | None = TEST_API_KEY) -> dict[str, str]:
    headers = {"Authorization": "Bearer test-jwt"}
    if api_key is not None:
        headers["x-api-key"] = api_key
    return headers
