from uuid import UUID

from app.core.config import get_settings
from app.core.errors import extract_error_message
from app.core.supabase import get_supabase_client
from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.repositories.job_repository import (
    FINISHED,
    PARTIAL_FINISH,
    RETRYING,
    JobRepository,
)
from app.schemas.notam_analysis import AnalysisNotamRow, NotamResult
from app.schemas.pipeline_stage import (
    build_context_object_metadata,
    build_notam_analysis_metadata,
)
from app.services.analysis_context import build_flight_context, build_notam_rows
from app.services.notam_analyzer import (
    analyze_notam_batches,
    chunk_notam_batches,
    map_results_to_raw_notam_ids,
    merge_batch_results,
)
from app.services.pipeline_stage import PipelineStageLogger


def _filter_notam_rows(
    notam_rows: list[AnalysisNotamRow],
    notam_ids: set[str],
) -> list[AnalysisNotamRow]:
    return [row for row in notam_rows if row.notam_id in notam_ids]


def _map_pending_notam_rows(
    notam_rows: list[AnalysisNotamRow],
    missing_notam_ids: list[str],
) -> list[tuple[int, None]]:
    missing = set(missing_notam_ids)
    return [(row.id, None) for row in notam_rows if row.notam_id in missing]


def _map_raw_notam_ids(
    notam_rows: list[AnalysisNotamRow],
    notam_ids: list[str],
) -> list[int]:
    missing = set(notam_ids)
    return [row.id for row in notam_rows if row.notam_id in missing]


def _build_initial_persist_rows(
    notam_rows: list[AnalysisNotamRow],
    results: list[NotamResult],
    missing_notam_ids: list[str],
) -> list[tuple[int, NotamResult | None]]:
    completed = map_results_to_raw_notam_ids(notam_rows, results)
    pending = _map_pending_notam_rows(notam_rows, missing_notam_ids)
    return completed + pending


def run_analysis_task(job_id: UUID, flight_plan_id: UUID) -> None:
    client = get_supabase_client()
    job_repository = JobRepository(client)
    context_repository = AnalysisContextRepository(client)
    analysed_notam_repository = AnalysedNotamRepository(client)
    stage_logger = PipelineStageLogger(client, job_id)
    settings = get_settings()

    try:
        with stage_logger.track("build_context_object") as ctx_stage:
            flight = build_flight_context(job_id, context_repository)
            ctx_stage.metadata = build_context_object_metadata(flight)

        notam_rows = build_notam_rows(context_repository.fetch_notams(job_id))

        with stage_logger.track("notam_analysis") as analysis_stage:
            batch_result = analyze_notam_batches(
                chunk_notam_batches(
                    flight,
                    notam_rows,
                    batch_size=settings.NOTAM_ANALYSIS_BATCH_SIZE,
                )
            )

            retried_notam_ids: list[str] | None = None
            if batch_result.missing_notam_ids:
                retried_notam_ids = list(batch_result.missing_notam_ids)
                analysed_notam_repository.insert_analysed_notams(
                    job_id,
                    flight_plan_id,
                    _build_initial_persist_rows(
                        notam_rows,
                        batch_result.results,
                        batch_result.missing_notam_ids,
                    ),
                )

                job_repository.update_status(job_id, RETRYING)
                retry_rows = _filter_notam_rows(
                    notam_rows,
                    set(batch_result.missing_notam_ids),
                )
                retry_result = analyze_notam_batches(
                    chunk_notam_batches(
                        flight,
                        retry_rows,
                        batch_size=settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE,
                    )
                )

                retry_mapped = map_results_to_raw_notam_ids(
                    notam_rows,
                    retry_result.results,
                )
                if retry_mapped:
                    analysed_notam_repository.update_analysed_notams(
                        job_id,
                        retry_mapped,
                    )

                if retry_result.missing_notam_ids:
                    analysed_notam_repository.mark_analysed_notams_errored(
                        job_id,
                        _map_raw_notam_ids(notam_rows, retry_result.missing_notam_ids),
                    )

                batch_result = merge_batch_results(batch_result, retry_result)
            else:
                analysed_notam_repository.insert_analysed_notams(
                    job_id,
                    flight_plan_id,
                    map_results_to_raw_notam_ids(notam_rows, batch_result.results),
                )

            analysis_stage.metadata = build_notam_analysis_metadata(
                batch_result,
                input_cost_per_m=settings.NOTAM_ANALYSIS_INPUT_COST_PER_M,
                output_cost_per_m=settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M,
                retried_notam_ids=retried_notam_ids,
            )

        final_status = (
            PARTIAL_FINISH if batch_result.missing_notam_ids else FINISHED
        )
        job_repository.update_status(job_id, final_status)
    except Exception as error:
        job_repository.mark_failed(job_id, extract_error_message(error))
