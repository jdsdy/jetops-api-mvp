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
    build_topic_batches,
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
    pending_notam_ids: list[str],
) -> list[tuple[int, None]]:
    pending = set(pending_notam_ids)
    return [(row.id, None) for row in notam_rows if row.notam_id in pending]


def _map_raw_notam_ids(
    notam_rows: list[AnalysisNotamRow],
    notam_ids: list[str],
) -> list[int]:
    pending = set(notam_ids)
    return [row.id for row in notam_rows if row.notam_id in pending]


def _pending_notam_ids(
    missing_notam_ids: list[str],
    rejected_notam_ids: list[str],
) -> list[str]:
    return sorted(set(missing_notam_ids) | set(rejected_notam_ids))


def _build_initial_persist_rows(
    notam_rows: list[AnalysisNotamRow],
    results: list[NotamResult],
    pending_notam_ids: list[str],
) -> list[tuple[int, NotamResult | None]]:
    completed = map_results_to_raw_notam_ids(notam_rows, results)
    pending = _map_pending_notam_rows(notam_rows, pending_notam_ids)
    return completed + pending


def _apply_retry_updates(
    job_id: UUID,
    notam_rows: list[AnalysisNotamRow],
    analysed_notam_repository: AnalysedNotamRepository,
    retry_result,
) -> None:
    retry_mapped = map_results_to_raw_notam_ids(notam_rows, retry_result.results)
    if retry_mapped:
        analysed_notam_repository.update_analysed_notams(job_id, retry_mapped)


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
                build_topic_batches(
                    flight,
                    notam_rows,
                    batch_size=settings.NOTAM_ANALYSIS_BATCH_SIZE,
                )
            )

            retried_notam_ids: list[str] | None = None
            pending_ids = _pending_notam_ids(
                batch_result.missing_notam_ids,
                batch_result.rejected_notam_ids,
            )
            if pending_ids:
                retried_notam_ids = pending_ids
                analysed_notam_repository.insert_analysed_notams(
                    job_id,
                    flight_plan_id,
                    _build_initial_persist_rows(
                        notam_rows,
                        batch_result.results,
                        pending_ids,
                    ),
                )

                job_repository.update_status(job_id, RETRYING)
                retry_results = []

                if batch_result.rejected_notam_ids:
                    rejected_rows = _filter_notam_rows(
                        notam_rows,
                        set(batch_result.rejected_notam_ids),
                    )
                    rejected_result = analyze_notam_batches(
                        chunk_notam_batches(
                            flight,
                            rejected_rows,
                            batch_size=settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE,
                            topic="MISC",
                        )
                    )
                    _apply_retry_updates(
                        job_id,
                        notam_rows,
                        analysed_notam_repository,
                        rejected_result,
                    )
                    retry_results.append(rejected_result)

                if batch_result.missing_notam_ids:
                    missing_rows = _filter_notam_rows(
                        notam_rows,
                        set(batch_result.missing_notam_ids),
                    )
                    missing_result = analyze_notam_batches(
                        build_topic_batches(
                            flight,
                            missing_rows,
                            batch_size=settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE,
                        )
                    )
                    _apply_retry_updates(
                        job_id,
                        notam_rows,
                        analysed_notam_repository,
                        missing_result,
                    )
                    retry_results.append(missing_result)

                still_pending: set[str] = set()
                for retry_result in retry_results:
                    still_pending.update(retry_result.missing_notam_ids)
                    still_pending.update(retry_result.rejected_notam_ids)

                if still_pending:
                    analysed_notam_repository.mark_analysed_notams_errored(
                        job_id,
                        _map_raw_notam_ids(notam_rows, sorted(still_pending)),
                    )

                if retry_results:
                    batch_result = merge_batch_results(batch_result, *retry_results)
                    batch_result = batch_result.model_copy(
                        update={
                            "missing_notam_ids": sorted(still_pending),
                            "rejected_notam_ids": [],
                        }
                    )
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
