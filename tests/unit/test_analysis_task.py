from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.repositories.job_repository import FINISHED, PARTIAL_FINISH, RETRYING
from app.schemas.analysis_context import AircraftContext, AirfieldContext, FlightContext
from app.schemas.notam_analysis import (
    AnalysisNotamRow,
    BatchAnalysisResult,
    BatchCallStats,
    NotamResult,
)
from app.services.analysis_task import run_analysis_task
from tests.conftest import PLAN_ID


def _flight_context() -> FlightContext:
    return FlightContext(
        departure_airfield=AirfieldContext(
            icao="YSSY",
            rwy="34L",
            iso_country="AU",
            length_ft=1299.0,
        ),
        arrival_airfield=AirfieldContext(icao="YPPH", rwy="03"),
        alternate_airfield_icao="YBLN",
        planned_dept_time=None,
        planned_arr_time=None,
        route="DCT",
        cruise_level="FL430",
        aircraft=AircraftContext(icao_wtc="M"),
    )


def test_run_analysis_task_success_sets_finished_and_persists() -> None:
    job_id = uuid4()
    notam_rows = [
        AnalysisNotamRow(id=1, notam_id="C0481/26 NOTAMN"),
    ]
    batch_result = BatchAnalysisResult(
        results=[NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="Runway")],
        batch_stats=[
            BatchCallStats(
                duration_ms=50,
                input_tokens=100,
                output_tokens=50,
                batch_size=1,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
    )

    mock_job_repo = MagicMock()
    mock_context_repo = MagicMock()
    mock_analysed_repo = MagicMock()
    mock_stage_repo = MagicMock()
    mock_settings = MagicMock()
    mock_settings.NOTAM_ANALYSIS_BATCH_SIZE = 10
    mock_settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE = 5
    mock_settings.NOTAM_ANALYSIS_INPUT_COST_PER_M = 3.0
    mock_settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M = 15.0

    with (
        patch("app.services.analysis_task.get_supabase_client"),
        patch("app.services.analysis_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.analysis_task.AnalysisContextRepository",
            return_value=mock_context_repo,
        ),
        patch(
            "app.services.analysis_task.AnalysedNotamRepository",
            return_value=mock_analysed_repo,
        ),
        patch(
            "app.services.pipeline_stage.PipelineStageLogRepository",
            return_value=mock_stage_repo,
        ),
        patch(
            "app.services.analysis_task.build_flight_context",
            return_value=_flight_context(),
        ),
        patch(
            "app.services.analysis_task.build_notam_rows",
            return_value=notam_rows,
        ),
        patch(
            "app.services.analysis_task.build_topic_batches",
            return_value=[MagicMock()],
        ) as mock_build_batches,
        patch(
            "app.services.analysis_task.analyze_notam_batches",
            return_value=batch_result,
        ),
        patch("app.services.analysis_task.get_settings", return_value=mock_settings),
    ):
        run_analysis_task(job_id, PLAN_ID)

    mock_build_batches.assert_called_once()
    mock_analysed_repo.insert_analysed_notams.assert_called_once()
    mock_job_repo.update_status.assert_called_once_with(job_id, FINISHED)
    mock_job_repo.mark_failed.assert_not_called()
    assert mock_stage_repo.insert_log.call_count == 2


def test_run_analysis_task_retries_missing_notams_and_finishes() -> None:
    job_id = uuid4()
    notam_rows = [
        AnalysisNotamRow(id=1, notam_id="C0481/26 NOTAMN"),
        AnalysisNotamRow(id=2, notam_id="C0478/26 NOTAMN"),
    ]
    initial_result = BatchAnalysisResult(
        results=[NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
        batch_stats=[
            BatchCallStats(
                duration_ms=50,
                input_tokens=100,
                output_tokens=50,
                batch_size=2,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
        missing_notam_ids=["C0478/26 NOTAMN"],
    )
    retry_result = BatchAnalysisResult(
        results=[NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="B")],
        batch_stats=[
            BatchCallStats(
                duration_ms=40,
                input_tokens=80,
                output_tokens=40,
                batch_size=1,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
        missing_notam_ids=[],
    )

    mock_job_repo = MagicMock()
    mock_context_repo = MagicMock()
    mock_analysed_repo = MagicMock()
    mock_stage_repo = MagicMock()
    mock_settings = MagicMock()
    mock_settings.NOTAM_ANALYSIS_BATCH_SIZE = 10
    mock_settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE = 5
    mock_settings.NOTAM_ANALYSIS_INPUT_COST_PER_M = 3.0
    mock_settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M = 15.0

    with (
        patch("app.services.analysis_task.get_supabase_client"),
        patch("app.services.analysis_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.analysis_task.AnalysisContextRepository",
            return_value=mock_context_repo,
        ),
        patch(
            "app.services.analysis_task.AnalysedNotamRepository",
            return_value=mock_analysed_repo,
        ),
        patch(
            "app.services.pipeline_stage.PipelineStageLogRepository",
            return_value=mock_stage_repo,
        ),
        patch(
            "app.services.analysis_task.build_flight_context",
            return_value=_flight_context(),
        ),
        patch(
            "app.services.analysis_task.build_notam_rows",
            return_value=notam_rows,
        ),
        patch(
            "app.services.analysis_task.build_topic_batches",
            side_effect=lambda flight, rows, batch_size: [MagicMock()],
        ) as mock_build_batches,
        patch(
            "app.services.analysis_task.analyze_notam_batches",
            side_effect=[initial_result, retry_result],
        ) as mock_analyze,
        patch("app.services.analysis_task.get_settings", return_value=mock_settings),
    ):
        run_analysis_task(job_id, PLAN_ID)

    assert mock_analyze.call_count == 2
    assert mock_build_batches.call_args_list[0].kwargs["batch_size"] == 10
    assert mock_build_batches.call_args_list[1].kwargs["batch_size"] == 5
    mock_job_repo.update_status.assert_any_call(job_id, RETRYING)
    mock_job_repo.update_status.assert_called_with(job_id, FINISHED)
    mock_analysed_repo.insert_analysed_notams.assert_called_once()
    insert_rows = mock_analysed_repo.insert_analysed_notams.call_args.args[2]
    assert insert_rows == [
        (1, NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")),
        (2, None),
    ]
    mock_analysed_repo.update_analysed_notams.assert_called_once()
    update_rows = mock_analysed_repo.update_analysed_notams.call_args.args[1]
    assert update_rows == [
        (2, NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="B")),
    ]


def test_run_analysis_task_sets_partial_finish_when_retry_still_missing() -> None:
    job_id = uuid4()
    notam_rows = [
        AnalysisNotamRow(id=1, notam_id="C0481/26 NOTAMN"),
        AnalysisNotamRow(id=2, notam_id="C0478/26 NOTAMN"),
    ]
    initial_result = BatchAnalysisResult(
        results=[NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
        batch_stats=[
            BatchCallStats(
                duration_ms=50,
                input_tokens=100,
                output_tokens=50,
                batch_size=2,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
        missing_notam_ids=["C0478/26 NOTAMN"],
    )
    retry_result = BatchAnalysisResult(
        results=[],
        batch_stats=[
            BatchCallStats(
                duration_ms=40,
                input_tokens=80,
                output_tokens=40,
                batch_size=1,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
        missing_notam_ids=["C0478/26 NOTAMN"],
    )

    mock_job_repo = MagicMock()
    mock_analysed_repo = MagicMock()

    with (
        patch("app.services.analysis_task.get_supabase_client"),
        patch("app.services.analysis_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.analysis_task.AnalysisContextRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.analysis_task.AnalysedNotamRepository",
            return_value=mock_analysed_repo,
        ),
        patch(
            "app.services.pipeline_stage.PipelineStageLogRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.analysis_task.build_flight_context",
            return_value=_flight_context(),
        ),
        patch(
            "app.services.analysis_task.build_notam_rows",
            return_value=notam_rows,
        ),
        patch(
            "app.services.analysis_task.build_topic_batches",
            return_value=[MagicMock()],
        ),
        patch(
            "app.services.analysis_task.analyze_notam_batches",
            side_effect=[initial_result, retry_result],
        ),
        patch(
            "app.services.analysis_task.get_settings",
            return_value=MagicMock(
                NOTAM_ANALYSIS_BATCH_SIZE=10,
                NOTAM_ANALYSIS_RETRY_BATCH_SIZE=5,
                NOTAM_ANALYSIS_INPUT_COST_PER_M=3.0,
                NOTAM_ANALYSIS_OUTPUT_COST_PER_M=15.0,
            ),
        ),
    ):
        run_analysis_task(job_id, PLAN_ID)

    mock_job_repo.update_status.assert_any_call(job_id, RETRYING)
    mock_job_repo.update_status.assert_called_with(job_id, PARTIAL_FINISH)
    insert_rows = mock_analysed_repo.insert_analysed_notams.call_args.args[2]
    assert insert_rows == [
        (1, NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")),
        (2, None),
    ]
    mock_analysed_repo.update_analysed_notams.assert_not_called()
    mock_analysed_repo.mark_analysed_notams_errored.assert_called_once_with(
        job_id,
        [2],
    )


def test_run_analysis_task_marks_failed_on_error() -> None:
    job_id = uuid4()
    mock_job_repo = MagicMock()

    with (
        patch("app.services.analysis_task.get_supabase_client"),
        patch("app.services.analysis_task.JobRepository", return_value=mock_job_repo),
        patch(
            "app.services.analysis_task.AnalysisContextRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.analysis_task.AnalysedNotamRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.pipeline_stage.PipelineStageLogRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.analysis_task.build_flight_context",
            side_effect=RuntimeError("context failed"),
        ),
        patch("app.services.analysis_task.get_settings"),
    ):
        run_analysis_task(job_id, PLAN_ID)

    mock_job_repo.mark_failed.assert_called_once()
    mock_job_repo.update_status.assert_not_called()
