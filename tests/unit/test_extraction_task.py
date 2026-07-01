from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.repositories.flight_repository import FlightRepository
from app.repositories.job_repository import AWAITING_CONFIRMATION, JobRepository
from app.repositories.notam_repository import NotamRepository
from app.schemas.flight import FlightData
from app.schemas.notam import RawNotam
from app.schemas.notam_topic import ClassificationResult
from app.services.extraction.extraction_task import (
    _identify_notam_topics,
    _merge_classified_notams,
    run_extraction,
)
from app.services.extraction.pdf_extractor import PdfExtractionResult
from tests.conftest import PLAN_ID


def test_identify_notam_topics_classifies_each_notam() -> None:
    notams = [
        RawNotam(notam_id="C0481/26 NOTAMN"),
        RawNotam(notam_id="C0478/26 NOTAMN"),
    ]

    with patch(
        "app.services.extraction.extraction_task.classify_notam",
        side_effect=[
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic="OBSTACLE", confidence=30),
        ],
    ):
        classifications, errors = _identify_notam_topics(notams)

    assert classifications == [
        ClassificationResult(topic="RUNWAY", confidence=100),
        ClassificationResult(topic="OBSTACLE", confidence=30),
    ]
    assert errors == 0


def test_merge_classified_notams_pairs_notam_with_classification() -> None:
    notam = RawNotam(notam_id="C0481/26 NOTAMN")
    classification = ClassificationResult(topic="RUNWAY", confidence=100)

    merged = _merge_classified_notams([notam], [classification])

    assert merged == [(notam, classification)]


def test_run_extraction_success_persists_flight_notams_and_status() -> None:
    job_id = uuid4()
    flight_id = uuid4()
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_flight_repo = MagicMock(spec=FlightRepository)
    mock_notam_repo = MagicMock(spec=NotamRepository)
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
    notams = [RawNotam(notam_id="C0481/26 NOTAMN", q="YMMM/QMDCH/IV/NBO/A/000/999/")]
    classification = ClassificationResult(topic="RUNWAY", confidence=100)
    inserted = [{"id": 42, "topic": "RUNWAY", "topic_confidence": 100}]

    mock_notam_repo.insert_classified_notams.return_value = inserted
    mock_stage_repo = MagicMock()

    with (
        patch("app.services.extraction.extraction_task.get_supabase_client"),
        patch("app.services.extraction.extraction_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.extraction.extraction_task.FlightRepository",
            return_value=mock_flight_repo,
        ),
        patch(
            "app.services.extraction.extraction_task.NotamRepository",
            return_value=mock_notam_repo,
        ),
        patch(
            "app.services.pipeline.pipeline_stage.PipelineStageLogRepository",
            return_value=mock_stage_repo,
        ),
        patch(
            "app.services.extraction.extraction_task.extract_pdf_text",
            return_value=PdfExtractionResult(text="text", page_count=5),
        ),
        patch(
            "app.services.extraction.extraction_task.parse_flight_data",
            return_value=flight_data,
        ),
        patch(
            "app.services.extraction.extraction_task.extract_notams",
            return_value=notams,
        ),
        patch(
            "app.services.extraction.extraction_task.classify_notam",
            return_value=classification,
        ),
    ):
        run_extraction(job_id, PLAN_ID, "org/flight/plan/file.pdf")

    assert mock_stage_repo.insert_log.call_count == 4
    mock_flight_repo.update_from_extraction.assert_called_once_with(
        flight_id,
        PLAN_ID,
        flight_data,
    )
    mock_notam_repo.insert_classified_notams.assert_called_once_with(
        job_id,
        PLAN_ID,
        [(notams[0], classification)],
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
    mock_notam_repo = MagicMock(spec=NotamRepository)
    mock_job_repo.download_flight_plan_pdf.side_effect = RuntimeError("parse failed")

    mock_stage_repo = MagicMock()

    with (
        patch("app.services.extraction.extraction_task.get_supabase_client"),
        patch("app.services.extraction.extraction_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.extraction.extraction_task.FlightRepository",
            return_value=mock_flight_repo,
        ),
        patch(
            "app.services.extraction.extraction_task.NotamRepository",
            return_value=mock_notam_repo,
        ),
        patch(
            "app.services.pipeline.pipeline_stage.PipelineStageLogRepository",
            return_value=mock_stage_repo,
        ),
    ):
        run_extraction(job_id, PLAN_ID, "org/flight/plan/file.pdf")

    mock_job_repo.mark_failed.assert_called_once_with(job_id, "parse failed")
    mock_job_repo.update_status.assert_not_called()
    mock_notam_repo.insert_classified_notams.assert_not_called()
    mock_stage_repo.insert_log.assert_not_called()
