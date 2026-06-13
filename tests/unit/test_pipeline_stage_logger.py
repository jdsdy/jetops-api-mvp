from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.pipeline_stage import FlightDataParseMetadata, PdfExtractionMetadata
from app.services.pipeline_stage import PipelineStageLogger


def test_log_inserts_serialised_metadata() -> None:
    job_id = uuid4()
    mock_repo = MagicMock()

    with patch(
        "app.services.pipeline_stage.PipelineStageLogRepository",
        return_value=mock_repo,
    ):
        logger = PipelineStageLogger(MagicMock(), job_id)
        logger.log(
            "pdf_extraction",
            42,
            PdfExtractionMetadata(
                page_count=10,
                file_size_bytes=1024,
                download_url="org/flight/plan/file.pdf",
            ),
        )

    mock_repo.insert_log.assert_called_once_with(
        analysis_job_id=job_id,
        stage_name="pdf_extraction",
        duration_ms=42,
        metadata={
            "page_count": 10,
            "file_size_bytes": 1024,
            "download_url": "org/flight/plan/file.pdf",
        },
    )


def test_track_writes_log_on_exit_when_metadata_set() -> None:
    job_id = uuid4()
    mock_repo = MagicMock()

    with patch(
        "app.services.pipeline_stage.PipelineStageLogRepository",
        return_value=mock_repo,
    ):
        logger = PipelineStageLogger(MagicMock(), job_id)
        with logger.track("flight_data_parse") as stage:
            stage.metadata = FlightDataParseMetadata(
                fields_extracted=["route"],
                fields_missing=[],
                source_type="foreflight",
            )

    mock_repo.insert_log.assert_called_once()
    call = mock_repo.insert_log.call_args.kwargs
    assert call["analysis_job_id"] == job_id
    assert call["stage_name"] == "flight_data_parse"
    assert call["duration_ms"] >= 0
    assert call["metadata"]["source_type"] == "foreflight"


def test_track_skips_log_when_metadata_not_set() -> None:
    mock_repo = MagicMock()

    with patch(
        "app.services.pipeline_stage.PipelineStageLogRepository",
        return_value=mock_repo,
    ):
        logger = PipelineStageLogger(MagicMock(), uuid4())
        with logger.track("notam_parse"):
            pass

    mock_repo.insert_log.assert_not_called()


def test_log_swallows_repository_errors() -> None:
    mock_repo = MagicMock()
    mock_repo.insert_log.side_effect = RuntimeError("db down")

    with patch(
        "app.services.pipeline_stage.PipelineStageLogRepository",
        return_value=mock_repo,
    ):
        logger = PipelineStageLogger(MagicMock(), uuid4())
        logger.log(
            "pdf_extraction",
            1,
            PdfExtractionMetadata(
                page_count=1,
                file_size_bytes=1,
                download_url="path.pdf",
            ),
        )
