from uuid import UUID

from app.core.errors import extract_error_message
from app.core.supabase import get_supabase_client
from app.repositories.flight_repository import FlightRepository
from app.repositories.job_repository import AWAITING_CONFIRMATION, JobRepository
from app.repositories.notam_repository import NotamRepository
from app.schemas.pipeline_stage import (
    PdfExtractionMetadata,
    build_flight_parse_metadata,
    build_notam_parse_metadata,
)
from app.services.flight_parser import parse_flight_data
from app.services.notam_parser import extract_notams
from app.services.pdf_extractor import extract_pdf_text
from app.services.pipeline_stage import PipelineStageLogger


def run_extraction(job_id: UUID, flight_plan_id: UUID, storage_path: str) -> None:
    client = get_supabase_client()
    job_repository = JobRepository(client)
    flight_repository = FlightRepository(client)
    notam_repository = NotamRepository(client)
    stage_logger = PipelineStageLogger(client, job_id)

    try:
        with stage_logger.track("pdf_extraction") as pdf_stage:
            pdf_bytes = job_repository.download_flight_plan_pdf(storage_path)
            pdf_result = extract_pdf_text(pdf_bytes)
            pdf_stage.metadata = PdfExtractionMetadata(
                page_count=pdf_result.page_count,
                file_size_bytes=len(pdf_bytes),
                download_url=storage_path,
            )

        with stage_logger.track("flight_data_parse") as flight_stage:
            flight_data = parse_flight_data(pdf_result.text)
            flight_id = flight_repository.get_flight_id(flight_plan_id)
            flight_repository.update_from_extraction(
                flight_id,
                flight_plan_id,
                flight_data,
            )
            flight_stage.metadata = build_flight_parse_metadata(flight_data)

        with stage_logger.track("notam_parse") as notam_stage:
            notams = extract_notams(pdf_result.text)
            notam_repository.insert_notams(job_id, flight_plan_id, notams)
            notam_stage.metadata = build_notam_parse_metadata(
                notams,
                flight_data.source_app,
            )

        job_repository.update_status(job_id, AWAITING_CONFIRMATION)
    except Exception as error:
        job_repository.mark_failed(job_id, extract_error_message(error))
