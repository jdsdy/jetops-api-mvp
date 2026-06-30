from unittest.mock import patch
from uuid import UUID

import pytest
from starlette.background import BackgroundTask, BackgroundTasks
from starlette.responses import Response

from app.api.api_logging import (
    API_SERVICE_NAME,
    _schedule_api_log,
    extract_error_message_from_response_body,
    extract_organisation_id_from_body,
    normalise_v1_path,
)


def test_normalise_v1_path_returns_path_when_it_starts_with_v1() -> None:
    assert normalise_v1_path("/v1/app/jobs") == "/v1/app/jobs"
    assert normalise_v1_path("/v1/app/jobs/analysis") == "/v1/app/jobs/analysis"


def test_normalise_v1_path_returns_none_for_non_v1_paths() -> None:
    assert normalise_v1_path("/docs") is None
    assert normalise_v1_path("/openapi.json") is None


def test_extract_organisation_id_from_body() -> None:
    body = b'{"organisation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "flight_id": "x"}'

    organisation_id = extract_organisation_id_from_body(body)

    assert organisation_id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_extract_organisation_id_from_body_returns_none_when_missing() -> None:
    assert extract_organisation_id_from_body(b'{"code": "abc"}') is None
    assert extract_organisation_id_from_body(b"not-json") is None


def test_extract_error_message_from_response_body() -> None:
    body = b'{"detail": "Invalid signup code"}'

    assert extract_error_message_from_response_body(body) == "Invalid signup code"


def test_extract_error_message_from_response_body_formats_validation_errors() -> None:
    body = b'{"detail":[{"msg":"Field required","loc":["body","code"]}]}'

    assert "Field required" in extract_error_message_from_response_body(body)


def test_api_service_name_is_fastapi() -> None:
    assert API_SERVICE_NAME == "fastapi"


def _log_kwargs() -> dict:
    return {
        "method": "GET",
        "path": "/v1/test",
        "status_code": 200,
        "duration_ms": 12,
        "user_id": None,
        "organisation_id": None,
        "api_client_id": None,
        "error_message": None,
    }


@pytest.mark.anyio
async def test_schedule_api_log_defers_write_until_background_runs() -> None:
    response = Response()

    with patch("app.api.api_logging._write_api_log") as mock_write:
        _schedule_api_log(response, **_log_kwargs())
        mock_write.assert_not_called()
        assert response.background is not None
        await response.background()
        mock_write.assert_called_once_with(**_log_kwargs())


@pytest.mark.anyio
async def test_schedule_api_log_preserves_existing_background_task() -> None:
    response = Response()
    existing_ran = False

    def existing_task() -> None:
        nonlocal existing_ran
        existing_ran = True

    response.background = BackgroundTask(existing_task)

    with patch("app.api.api_logging._write_api_log") as mock_write:
        _schedule_api_log(response, **_log_kwargs())
        assert isinstance(response.background, BackgroundTasks)
        await response.background()

    assert existing_ran is True
    mock_write.assert_called_once_with(**_log_kwargs())
