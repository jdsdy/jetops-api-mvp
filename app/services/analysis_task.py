from uuid import UUID

from app.core.config import get_settings
from app.core.errors import extract_error_message
from app.core.supabase import get_supabase_client
from app.repositories.analysed_notam_repository import AnalysedNotamRepository
from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.repositories.job_repository import FINISHED, JobRepository
from app.schemas.pipeline_stage import (
    build_context_object_metadata,
    build_notam_analysis_metadata,
)
from app.services.analysis_context import build_flight_context, build_notam_rows
from app.services.notam_analyzer import (
    analyze_notam_batches,
    chunk_notam_batches,
    map_results_to_raw_notam_ids,
)
from app.services.pipeline_stage import PipelineStageLogger


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

        with stage_logger.track("notam_analysis") as analysis_stage:
            notam_rows = build_notam_rows(context_repository.fetch_notams(job_id))
            batches = chunk_notam_batches(
                flight,
                notam_rows,
                batch_size=settings.NOTAM_ANALYSIS_BATCH_SIZE,
            )
            batch_result = analyze_notam_batches(batches)
            mapped = map_results_to_raw_notam_ids(notam_rows, batch_result.results)
            analysed_notam_repository.insert_analysed_notams(
                job_id,
                flight_plan_id,
                mapped,
            )
            analysis_stage.metadata = build_notam_analysis_metadata(
                batch_result,
                input_cost_per_m=settings.NOTAM_ANALYSIS_INPUT_COST_PER_M,
                output_cost_per_m=settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M,
            )

        job_repository.update_status(job_id, FINISHED)
    except Exception as error:
        job_repository.mark_failed(job_id, extract_error_message(error))
