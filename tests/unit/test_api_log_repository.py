from unittest.mock import MagicMock
from uuid import uuid4

from app.repositories.api_log_repository import ApiLogRepository


def test_insert_api_log_writes_expected_payload() -> None:
    user_id = uuid4()
    organisation_id = uuid4()
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    repository = ApiLogRepository(mock_client)
    repository.insert_api_log(
        service="fastapi",
        method="POST",
        path="/v1/jobs",
        status_code=201,
        user_id=user_id,
        organisation_id=organisation_id,
        duration_ms=42,
        error_message=None,
    )

    mock_table.insert.assert_called_once_with(
        {
            "service": "fastapi",
            "method": "POST",
            "path": "/v1/jobs",
            "status_code": 201,
            "user_id": str(user_id),
            "organisation_id": str(organisation_id),
            "duration_ms": 42,
            "error_message": None,
        }
    )


def test_insert_api_log_omits_null_user_and_organisation_ids() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock()

    repository = ApiLogRepository(mock_client)
    repository.insert_api_log(
        service="fastapi",
        method="POST",
        path="/v1/signup",
        status_code=200,
        user_id=None,
        organisation_id=None,
        duration_ms=10,
        error_message=None,
    )

    mock_table.insert.assert_called_once_with(
        {
            "service": "fastapi",
            "method": "POST",
            "path": "/v1/signup",
            "status_code": 200,
            "user_id": None,
            "organisation_id": None,
            "duration_ms": 10,
            "error_message": None,
        }
    )
