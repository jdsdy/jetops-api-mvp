from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

FLIGHT_PLAN_PDFS_BUCKET = "flight_plan_pdfs"


class JobRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def create_job(
        self,
        *,
        flight_plan_id: UUID,
        organisation_id: UUID,
        triggered_by: str,
        status: str,
    ) -> UUID:
        payload = {
            "flight_plan_id": str(flight_plan_id),
            "organisation_id": str(organisation_id),
            "triggered_by": triggered_by,
            "status": status,
            "started_at": datetime.now(UTC).isoformat(),
        }
        result = self._client.table("analysis_jobs").insert(payload).execute()
        return UUID(result.data[0]["id"])

    def mark_failed(self, job_id: UUID, error_message: str) -> None:
        self._client.table("analysis_jobs").update(
            {
                "status": "failed",
                "error_message": error_message,
            }
        ).eq("id", str(job_id)).execute()

    def verify_flight_plan_pdf(self, storage_path: str) -> None:
        data = self._client.storage.from_(FLIGHT_PLAN_PDFS_BUCKET).download(
            storage_path
        )
        if not data:
            raise FileNotFoundError("Flight plan PDF not found")
