from uuid import UUID

import pytest

from app.api.api_logging import (
    API_SERVICE_NAME,
    extract_error_message_from_response_body,
    extract_organisation_id_from_body,
    normalise_v1_path,
)


def test_normalise_v1_path_returns_path_when_it_starts_with_v1() -> None:
    assert normalise_v1_path("/v1/jobs") == "/v1/jobs"
    assert normalise_v1_path("/v1/jobs/analysis") == "/v1/jobs/analysis"


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
