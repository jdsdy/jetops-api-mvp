from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.repositories.flight_repository import FlightRepository
from app.repositories.job_repository import AWAITING_CONFIRMATION, JobRepository
from app.schemas.flight import FlightData
from app.services.extraction_task import run_extraction
from tests.conftest import PLAN_ID, STORAGE_PATH


def test_run_extraction_success_updates_flight_data_and_job_status() -> None:
    job_id = uuid4()
    flight_id = uuid4()
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_flight_repo = MagicMock(spec=FlightRepository)
    mock_job_repo.download_flight_plan_pdf.return_value = b"%PDF-1.4"
    mock_flight_repo.get_flight_id.return_value = flight_id

    flight_data = FlightData(
        departure_icao="YSSY",
        arrival_icao="YPPH",
        planned_dept_time=datetime(2026, 4, 15, 11, 35, tzinfo=UTC),
        planned_arr_time=datetime(2026, 4, 15, 15, 42, tzinfo=UTC),
        route="DCT",
        cruise_level="FL430",
        alt_icao="YBLN",
        source_app="foreflight",
    )

    with (
        patch("app.services.extraction_task.get_supabase_client"),
        patch("app.services.extraction_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.extraction_task.FlightRepository",
            return_value=mock_flight_repo,
        ),
        patch("app.services.extraction_task.extract_pdf_text", return_value="text"),
        patch(
            "app.services.extraction_task.parse_flight_data",
            return_value=flight_data,
        ),
    ):
        run_extraction(job_id, PLAN_ID, STORAGE_PATH)

    mock_flight_repo.update_from_extraction.assert_called_once_with(
        flight_id,
        PLAN_ID,
        flight_data,
    )
    mock_job_repo.update_status.assert_called_once_with(
        job_id,
        AWAITING_CONFIRMATION,
    )
    mock_job_repo.mark_failed.assert_not_called()


def test_run_extraction_failure_marks_job_failed() -> None:
    job_id = uuid4()
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_flight_repo = MagicMock(spec=FlightRepository)
    mock_job_repo.download_flight_plan_pdf.side_effect = RuntimeError("parse failed")

    with (
        patch("app.services.extraction_task.get_supabase_client"),
        patch("app.services.extraction_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.extraction_task.FlightRepository",
            return_value=mock_flight_repo,
        ),
    ):
        run_extraction(job_id, PLAN_ID, STORAGE_PATH)

    mock_job_repo.mark_failed.assert_called_once_with(job_id, "parse failed")
    mock_job_repo.update_status.assert_not_called()
