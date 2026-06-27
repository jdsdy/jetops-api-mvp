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
from app.schemas.notam_analysis import (
    AnalysisJobResult,
    AnalysisNotamRow,
    CategoryResult,
    NotamResult,
)
from app.schemas.pipeline_stage import (
    build_context_object_metadata,
    build_notam_analysis_metadata,
)
from app.services.analysis_context import build_flight_context, build_notam_rows
from app.services.notam_analyzer import (
    analyze_notam_job,
    build_topic_batches,
    categorize_notam_batches,
    chunk_notam_batches,
    chunk_summary_batches,
    map_results_to_raw_notam_ids,
    merge_category_batch_results,
    merge_notam_results,
    merge_summary_batch_results,
    partition_notam_rows,
    summarize_notam_batches,
)
from app.services.notam_heuristic_category import heuristic_category
from app.services.pipeline_stage import PipelineStageLogger


def _filter_notam_rows(
    notam_rows: list[AnalysisNotamRow],
    notam_ids: set[str],
) -> list[AnalysisNotamRow]:
    return [row for row in notam_rows if row.notam_id in notam_ids]


def _map_raw_notam_ids(
    notam_rows: list[AnalysisNotamRow],
    notam_ids: list[str],
) -> list[int]:
    pending = set(notam_ids)
    return [row.id for row in notam_rows if row.notam_id in pending]


def _pending_notam_ids(
    missing_category_notam_ids: list[str],
    missing_summary_notam_ids: list[str],
    rejected_notam_ids: list[str],
) -> list[str]:
    return sorted(
        set(missing_category_notam_ids)
        | set(missing_summary_notam_ids)
        | set(rejected_notam_ids)
    )


def _build_initial_persist_rows(
    notam_rows: list[AnalysisNotamRow],
    results: list[NotamResult],
    pending_notam_ids: list[str],
) -> list[tuple[int, NotamResult | None]]:
    by_notam_id = {result.notam_id: result for result in results}
    pending = set(pending_notam_ids)
    rows_out: list[tuple[int, NotamResult | None]] = []
    for row in notam_rows:
        result = by_notam_id.get(row.notam_id)
        if row.notam_id in pending:
            if result is not None and (
                result.category is not None or result.summary is not None
            ):
                rows_out.append((row.id, result))
            else:
                rows_out.append((row.id, None))
        else:
            if result is None or not result.is_complete:
                raise ValueError(
                    f"Complete analysis result missing for NOTAM: {row.notam_id}"
                )
            rows_out.append((row.id, result))
    return rows_out


def _heuristic_categories(
    notam_rows: list[AnalysisNotamRow],
) -> list[CategoryResult]:
    heuristic_rows, _ = partition_notam_rows(notam_rows)
    return [
        CategoryResult(notam_id=row.notam_id, category=heuristic_category(row))
        for row in heuristic_rows
    ]


def _rebuild_job_result(
    notam_rows: list[AnalysisNotamRow],
    *,
    heuristic_categories: list[CategoryResult],
    category_result,
    summary_result,
) -> AnalysisJobResult:
    all_categories = heuristic_categories + category_result.results
    return AnalysisJobResult(
        results=merge_notam_results(notam_rows, all_categories, summary_result.results),
        category_result=category_result,
        summary_result=summary_result,
        heuristic_category_count=len(heuristic_categories),
    )


def _apply_category_retry_updates(
    job_id: UUID,
    notam_rows: list[AnalysisNotamRow],
    analysed_notam_repository: AnalysedNotamRepository,
    category_results,
) -> None:
    retry_mapped = map_results_to_raw_notam_ids(
        notam_rows,
        [
            NotamResult(notam_id=result.notam_id, category=result.category)
            for result in category_results.results
        ],
    )
    if retry_mapped:
        analysed_notam_repository.update_analysed_notams(job_id, retry_mapped)


def _apply_summary_retry_updates(
    job_id: UUID,
    notam_rows: list[AnalysisNotamRow],
    analysed_notam_repository: AnalysedNotamRepository,
    summary_results,
) -> None:
    retry_mapped = map_results_to_raw_notam_ids(
        notam_rows,
        [
            NotamResult(notam_id=result.notam_id, summary=result.summary)
            for result in summary_results.results
        ],
    )
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
        heuristic_categories = _heuristic_categories(notam_rows)

        with stage_logger.track("notam_analysis") as analysis_stage:
            job_result = analyze_notam_job(flight, notam_rows)

            retried_category_notam_ids: list[str] | None = None
            retried_summary_notam_ids: list[str] | None = None
            pending_ids = _pending_notam_ids(
                job_result.missing_category_notam_ids,
                job_result.missing_summary_notam_ids,
                job_result.rejected_notam_ids,
            )
            category_result = job_result.category_result
            summary_result = job_result.summary_result

            if pending_ids:
                retried_category_ids = sorted(
                    set(job_result.missing_category_notam_ids)
                    | set(job_result.rejected_notam_ids)
                )
                retried_summary_ids = sorted(job_result.missing_summary_notam_ids)
                if retried_category_ids:
                    retried_category_notam_ids = retried_category_ids
                if retried_summary_ids:
                    retried_summary_notam_ids = retried_summary_ids

                analysed_notam_repository.insert_analysed_notams(
                    job_id,
                    flight_plan_id,
                    _build_initial_persist_rows(
                        notam_rows,
                        job_result.results,
                        pending_ids,
                    ),
                )

                job_repository.update_status(job_id, RETRYING)

                if job_result.rejected_notam_ids:
                    rejected_rows = _filter_notam_rows(
                        notam_rows,
                        set(job_result.rejected_notam_ids),
                    )
                    rejected_result = categorize_notam_batches(
                        chunk_notam_batches(
                            flight,
                            rejected_rows,
                            batch_size=settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE,
                            topic="MISC",
                        )
                    )
                    _apply_category_retry_updates(
                        job_id,
                        notam_rows,
                        analysed_notam_repository,
                        rejected_result,
                    )
                    category_result = merge_category_batch_results(
                        category_result,
                        rejected_result,
                    )

                if job_result.missing_category_notam_ids:
                    missing_rows = _filter_notam_rows(
                        notam_rows,
                        set(job_result.missing_category_notam_ids),
                    )
                    missing_category_result = categorize_notam_batches(
                        build_topic_batches(
                            flight,
                            missing_rows,
                            batch_size=settings.NOTAM_ANALYSIS_RETRY_BATCH_SIZE,
                        )
                    )
                    _apply_category_retry_updates(
                        job_id,
                        notam_rows,
                        analysed_notam_repository,
                        missing_category_result,
                    )
                    category_result = merge_category_batch_results(
                        category_result,
                        missing_category_result,
                    )

                if job_result.missing_summary_notam_ids:
                    missing_rows = _filter_notam_rows(
                        notam_rows,
                        set(job_result.missing_summary_notam_ids),
                    )
                    missing_summary_result = summarize_notam_batches(
                        chunk_summary_batches(
                            missing_rows,
                            batch_size=settings.NOTAM_SUMMARY_RETRY_BATCH_SIZE,
                        )
                    )
                    _apply_summary_retry_updates(
                        job_id,
                        notam_rows,
                        analysed_notam_repository,
                        missing_summary_result,
                    )
                    summary_result = merge_summary_batch_results(
                        summary_result,
                        missing_summary_result,
                    )

                job_result = _rebuild_job_result(
                    notam_rows,
                    heuristic_categories=heuristic_categories,
                    category_result=category_result,
                    summary_result=summary_result,
                )

                still_pending = _pending_notam_ids(
                    job_result.missing_category_notam_ids,
                    job_result.missing_summary_notam_ids,
                    job_result.rejected_notam_ids,
                )
                if still_pending:
                    analysed_notam_repository.mark_analysed_notams_errored(
                        job_id,
                        _map_raw_notam_ids(notam_rows, still_pending),
                    )
            else:
                analysed_notam_repository.insert_analysed_notams(
                    job_id,
                    flight_plan_id,
                    map_results_to_raw_notam_ids(notam_rows, job_result.results),
                )

            analysis_stage.metadata = build_notam_analysis_metadata(
                job_result,
                categorize_input_cost_per_m=settings.NOTAM_ANALYSIS_INPUT_COST_PER_M,
                categorize_output_cost_per_m=settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M,
                summarize_input_cost_per_m=settings.NOTAM_SUMMARY_INPUT_COST_PER_M,
                summarize_output_cost_per_m=settings.NOTAM_SUMMARY_OUTPUT_COST_PER_M,
                retried_category_notam_ids=retried_category_notam_ids,
                retried_summary_notam_ids=retried_summary_notam_ids,
            )

        final_status = (
            PARTIAL_FINISH
            if _pending_notam_ids(
                job_result.missing_category_notam_ids,
                job_result.missing_summary_notam_ids,
                job_result.rejected_notam_ids,
            )
            else FINISHED
        )
        job_repository.update_status(job_id, final_status)
    except Exception as error:
        job_repository.mark_failed(job_id, extract_error_message(error))
