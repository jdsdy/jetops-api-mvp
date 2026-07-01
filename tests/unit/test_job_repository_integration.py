from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID

from app.repositories.job_repository import (
    ACCEPTED,
    COMPLETE,
    FAILED,
    PROCESSING,
    JobRepository,
)

API_CLIENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
JOB_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_create_integration_job_inserts_expected_payload() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": str(JOB_ID)}])

    repository = JobRepository(mock_client)
    job_id, started_at = repository.create_integration_job(
        api_client_id=API_CLIENT_ID,
        status=ACCEPTED,
        departure_icao="YSSY",
        arrival_icao="YPPH",
    )

    mock_table.insert.assert_called_once()
    payload = mock_table.insert.call_args.args[0]
    assert payload["api_client_id"] == str(API_CLIENT_ID)
    assert payload["status"] == ACCEPTED
    assert payload["departure_icao"] == "YSSY"
    assert payload["arrival_icao"] == "YPPH"
    assert "started_at" in payload
    assert "flight_plan_id" not in payload
    assert job_id == JOB_ID
    assert started_at.tzinfo is not None


def test_get_integration_job_returns_row() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.maybe_single.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data={
            "id": str(JOB_ID),
            "status": ACCEPTED,
            "stage": None,
            "api_client_id": str(API_CLIENT_ID),
            "started_at": "2025-01-15T10:30:00+00:00",
            "completed_at": None,
            "error_code": None,
            "error_message": None,
        }
    )

    repository = JobRepository(mock_client)
    result = repository.get_integration_job(JOB_ID)

    assert result is not None
    assert result["id"] == str(JOB_ID)
    assert result["status"] == ACCEPTED


def test_update_integration_job_writes_fields() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table

    repository = JobRepository(mock_client)
    completed_at = datetime(2025, 1, 15, 10, 31, 45, tzinfo=UTC)
    repository.update_integration_job(
        JOB_ID,
        status=PROCESSING,
        stage="classification",
    )
    repository.update_integration_job(
        JOB_ID,
        status=COMPLETE,
        clear_stage=True,
        completed_at=completed_at,
    )

    assert mock_table.update.call_count == 2
    first_payload = mock_table.update.call_args_list[0].args[0]
    assert first_payload == {"status": PROCESSING, "stage": "classification"}
    second_payload = mock_table.update.call_args_list[1].args[0]
    assert second_payload["status"] == COMPLETE
    assert second_payload["stage"] is None
    assert second_payload["completed_at"] == completed_at.isoformat()


def test_update_integration_job_writes_failure_fields() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table

    repository = JobRepository(mock_client)
    repository.update_integration_job(
        JOB_ID,
        status=FAILED,
        error_code="internal_error",
        error_message="db down",
        clear_stage=True,
        completed_at=datetime(2025, 1, 15, 10, 31, 12, tzinfo=UTC),
    )

    payload = mock_table.update.call_args.args[0]
    assert payload["status"] == FAILED
    assert payload["error_code"] == "internal_error"
    assert payload["error_message"] == "db down"


def test_update_integration_job_writes_notam_counts() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table

    repository = JobRepository(mock_client)
    repository.update_integration_job(
        JOB_ID,
        status=COMPLETE,
        stage="complete",
        total_notams=47,
        cat1_notams=3,
        cat2_notams=12,
        cat3_notams=32,
    )

    payload = mock_table.update.call_args.args[0]
    assert payload == {
        "status": COMPLETE,
        "stage": "complete",
        "total_notams": 47,
        "cat1_notams": 3,
        "cat2_notams": 12,
        "cat3_notams": 32,
    }


def test_list_integration_jobs_applies_filters_and_pagination() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.range.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[
            {
                "id": str(JOB_ID),
                "status": COMPLETE,
                "started_at": "2025-01-15T10:30:00+00:00",
                "completed_at": "2025-01-15T10:31:45+00:00",
                "departure_icao": "YSSY",
                "arrival_icao": "YPPH",
                "total_notams": 1,
                "cat1_notams": 1,
            }
        ],
        count=1,
    )

    repository = JobRepository(mock_client)
    started_from = datetime(2025, 1, 1, tzinfo=UTC)
    started_to = datetime(2025, 2, 1, tzinfo=UTC)
    rows, total = repository.list_integration_jobs(
        api_client_id=API_CLIENT_ID,
        limit=20,
        offset=0,
        status=COMPLETE,
        started_from=started_from,
        started_to=started_to,
    )

    assert total == 1
    assert len(rows) == 1
    mock_table.select.assert_called_once()
    mock_table.eq.assert_any_call("api_client_id", str(API_CLIENT_ID))
    mock_table.eq.assert_any_call("status", COMPLETE)
    mock_table.gte.assert_called_once_with("started_at", started_from.isoformat())
    mock_table.lte.assert_called_once_with("started_at", started_to.isoformat())
    mock_table.range.assert_called_once_with(0, 19)
