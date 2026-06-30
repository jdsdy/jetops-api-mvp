from unittest.mock import MagicMock, patch
from uuid import UUID

from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.repositories.job_repository import COMPLETE, FAILED, PROCESSING, JobRepository
from app.repositories.notam_repository import NotamRepository
from app.schemas.integration_analysis import IntegrationAnalysisRequest
from app.schemas.notam_analysis import (
    AnalysisJobResult,
    BatchCallStats,
    CategoryBatchResult,
    NotamResult,
    SummaryBatchResult,
)
from app.services.integration.integration_analysis_task import run_integration_analysis
from tests.unit.test_integration_analysis_submission import minimal_valid_payload

JOB_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@patch("app.services.integration.integration_analysis_task.get_supabase_client")
def test_run_integration_analysis_persists_after_analysis(
    mock_get_client: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_notam_repo = MagicMock(spec=NotamRepository)
    mock_notam_repo.insert_classified_notams.return_value = [
        {"id": 10, "notam_id": "C1223/26 NOTAMN"}
    ]
    submission = IntegrationAnalysisRequest.model_validate(minimal_valid_payload())
    job_result = AnalysisJobResult(
        results=[
            NotamResult(
                notam_id="C1223/26 NOTAMN",
                category=1,
                summary="Runway closed",
            )
        ],
        category_result=CategoryBatchResult(
            results=[],
            batch_stats=[
                BatchCallStats(
                    duration_ms=50,
                    input_tokens=0,
                    output_tokens=0,
                    batch_size=1,
                )
            ],
            model="claude-sonnet-4-6",
            token_limit_hit=False,
            missing_notam_ids=[],
            rejected_notam_ids=[],
        ),
        summary_result=SummaryBatchResult(
            results=[],
            batch_stats=[
                BatchCallStats(
                    duration_ms=40,
                    input_tokens=0,
                    output_tokens=0,
                    batch_size=1,
                )
            ],
            model="claude-haiku-4-5",
            token_limit_hit=False,
            missing_notam_ids=[],
        ),
        heuristic_category_count=0,
    )

    with (
        patch(
            "app.services.integration.integration_analysis_task.JobRepository",
            return_value=mock_job_repo,
        ),
        patch(
            "app.services.integration.integration_analysis_task.NotamRepository",
            return_value=mock_notam_repo,
        ),
        patch(
            "app.services.integration.integration_analysis_task.PipelineStageLogger"
        ) as mock_stage_logger_cls,
        patch(
            "app.services.integration.integration_analysis_task.execute_notam_analysis_with_retries",
            return_value=(job_result, MagicMock(), []),
        ),
        patch(
            "app.services.integration.integration_analysis_task.AnalysedNotamRepository"
        ) as mock_analysed_repo_cls,
    ):
        mock_stage_logger_cls.return_value.track.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        mock_stage_logger_cls.return_value.track.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_analysed_repo = MagicMock(spec=AnalysedNotamRepository)
        mock_analysed_repo_cls.return_value = mock_analysed_repo

        run_integration_analysis(JOB_ID, submission)

    mock_job_repo.update_integration_job.assert_any_call(
        JOB_ID,
        status=PROCESSING,
        stage="topic_identification",
    )
    mock_notam_repo.insert_classified_notams.assert_called_once()
    mock_analysed_repo.insert_analysed_notams.assert_called_once()
    complete_calls = [
        call
        for call in mock_job_repo.update_integration_job.call_args_list
        if call.kwargs.get("status") == COMPLETE
    ]
    assert len(complete_calls) == 1
    assert complete_calls[0].kwargs["stage"] == "complete"
    assert complete_calls[0].kwargs["total_notams"] == 1
    assert complete_calls[0].kwargs["cat1_notams"] == 1
    assert complete_calls[0].kwargs["cat2_notams"] == 0
    assert complete_calls[0].kwargs["cat3_notams"] == 0


@patch("app.services.integration.integration_analysis_task.get_supabase_client")
def test_run_integration_analysis_marks_job_failed_on_error(
    mock_get_client: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_job_repo = MagicMock(spec=JobRepository)
    submission = IntegrationAnalysisRequest.model_validate(minimal_valid_payload())

    with (
        patch(
            "app.services.integration.integration_analysis_task.JobRepository",
            return_value=mock_job_repo,
        ),
        patch(
            "app.services.integration.integration_analysis_task.build_flight_context_from_integration",
            side_effect=RuntimeError("context failed"),
        ),
    ):
        run_integration_analysis(JOB_ID, submission)

    failed_calls = [
        call
        for call in mock_job_repo.update_integration_job.call_args_list
        if call.kwargs.get("status") == FAILED
    ]
    assert len(failed_calls) == 1
    assert failed_calls[0].kwargs["error_code"] == "internal_error"
    assert failed_calls[0].kwargs["error_message"] == "context failed"
