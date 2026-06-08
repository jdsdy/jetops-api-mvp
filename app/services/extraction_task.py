from uuid import UUID

from app.core.errors import extract_error_message
from app.core.supabase import get_supabase_client
from app.repositories.flight_repository import FlightRepository
from app.repositories.job_repository import AWAITING_CONFIRMATION, JobRepository
from app.services.flight_parser import parse_flight_data
from app.services.pdf_extractor import extract_pdf_text


def run_extraction(job_id: UUID, flight_plan_id: UUID, storage_path: str) -> None:
    client = get_supabase_client()
    job_repository = JobRepository(client)
    flight_repository = FlightRepository(client)

    try:
        pdf_bytes = job_repository.download_flight_plan_pdf(storage_path)
        flight_data = parse_flight_data(extract_pdf_text(pdf_bytes))
        flight_id = flight_repository.get_flight_id(flight_plan_id)
        flight_repository.update_from_extraction(flight_id, flight_plan_id, flight_data)
        job_repository.update_status(job_id, AWAITING_CONFIRMATION)
    except Exception as error:
        job_repository.mark_failed(job_id, extract_error_message(error))
