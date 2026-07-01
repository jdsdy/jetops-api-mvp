from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.api.integration_dependencies import verify_integration_api_key
from app.schemas.integration_auth import IntegrationAuthContext

API_KEY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
API_CLIENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
RAW_KEY = "jops_dev_sk_test_key"


def _request() -> Request:
    return Request({"type": "http", "headers": [], "method": "GET", "path": "/v1/test"})


def _credentials(token: str = RAW_KEY) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _valid_row() -> dict:
    return {
        "id": str(API_KEY_ID),
        "api_client_id": str(API_CLIENT_ID),
        "is_active": True,
        "revoked_at": None,
        "expires_at": None,
        "api_clients": {
            "is_active": True,
            "organisation_id": str(ORG_ID),
        },
    }


def test_verify_integration_api_key_raises_401_when_credentials_missing() -> None:
    mock_repository = MagicMock()
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        verify_integration_api_key(
            _request(),
            None,
            background_tasks,
            mock_repository,
        )

    assert exc_info.value.status_code == 401
    mock_repository.lookup_by_hash.assert_not_called()


def test_verify_integration_api_key_raises_401_when_key_not_found() -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.return_value = None
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        verify_integration_api_key(
            _request(),
            _credentials(),
            background_tasks,
            mock_repository,
        )

    assert exc_info.value.status_code == 401


def test_verify_integration_api_key_raises_401_when_key_inactive() -> None:
    mock_repository = MagicMock()
    row = _valid_row()
    row["is_active"] = False
    mock_repository.lookup_by_hash.return_value = row
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        verify_integration_api_key(
            _request(),
            _credentials(),
            background_tasks,
            mock_repository,
        )

    assert exc_info.value.status_code == 401


def test_verify_integration_api_key_raises_401_when_lookup_raises() -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.side_effect = AttributeError(
        "'NoneType' object has no attribute 'data'"
    )
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        verify_integration_api_key(
            _request(),
            _credentials(),
            background_tasks,
            mock_repository,
        )

    assert exc_info.value.status_code == 401


def test_verify_integration_api_key_returns_context_and_sets_request_state() -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.return_value = _valid_row()
    background_tasks = BackgroundTasks()
    request = _request()

    result = verify_integration_api_key(
        request,
        _credentials(),
        background_tasks,
        mock_repository,
    )

    assert result == IntegrationAuthContext(
        api_key_id=API_KEY_ID,
        api_client_id=API_CLIENT_ID,
        organisation_id=ORG_ID,
    )
    assert request.state.api_client_id == API_CLIENT_ID
    assert request.state.organisation_id == ORG_ID
    assert request.state.api_key_hash is not None


def test_verify_integration_api_key_schedules_last_used_update() -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.return_value = _valid_row()
    background_tasks = MagicMock(spec=BackgroundTasks)

    verify_integration_api_key(
        _request(),
        _credentials(),
        background_tasks,
        mock_repository,
    )

    background_tasks.add_task.assert_called_once_with(
        mock_repository.touch_last_used,
        API_KEY_ID,
    )
