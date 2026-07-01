from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

FLIGHT_PLAN_PDFS_BUCKET = "flight_plan_pdfs"
ACCEPTED = "accepted"
AWAITING_CONFIRMATION = "awaiting_confirmation"
PROCESSING_ANALYSIS = "processing_analysis"
RETRYING = "retrying"
FINISHED = "finished"
PARTIAL_FINISH = "partial_finish"
PROCESSING = "processing"
COMPLETE = "complete"
FAILED = "failed"

_INTEGRATION_JOB_COLUMNS = (
    "id, status, stage, api_client_id, started_at, completed_at, "
    "error_code, error_message, departure_icao, arrival_icao, "
    "total_notams, cat1_notams, cat2_notams, cat3_notams"
)
_INTEGRATION_LIST_COLUMNS = (
    "id, status, started_at, completed_at, departure_icao, arrival_icao, "
    "total_notams, cat1_notams, cat2_notams, cat3_notams"
)


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

    def create_integration_job(
        self,
        *,
        api_client_id: UUID,
        status: str,
        departure_icao: str,
        arrival_icao: str,
    ) -> tuple[UUID, datetime]:
        started_at = datetime.now(UTC)
        payload = {
            "api_client_id": str(api_client_id),
            "status": status,
            "started_at": started_at.isoformat(),
            "departure_icao": departure_icao,
            "arrival_icao": arrival_icao,
        }
        result = self._client.table("analysis_jobs").insert(payload).execute()
        if result is None or not result.data:
            raise RuntimeError("Failed to create integration analysis job")
        return UUID(result.data[0]["id"]), started_at

    def list_integration_jobs(
        self,
        *,
        api_client_id: UUID,
        limit: int,
        offset: int,
        status: str | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
    ) -> tuple[list[dict], int]:
        query = (
            self._client.table("analysis_jobs")
            .select(_INTEGRATION_LIST_COLUMNS, count="exact")
            .eq("api_client_id", str(api_client_id))
            .order("started_at", desc=True)
        )
        if status is not None:
            query = query.eq("status", status)
        if started_from is not None:
            query = query.gte("started_at", started_from.isoformat())
        if started_to is not None:
            query = query.lte("started_at", started_to.isoformat())

        result = query.range(offset, offset + limit - 1).execute()
        rows = result.data or []
        total = result.count if result.count is not None else len(rows)
        return rows, total

    def get_integration_job(self, job_id: UUID) -> dict | None:
        result = (
            self._client.table("analysis_jobs")
            .select(_INTEGRATION_JOB_COLUMNS)
            .eq("id", str(job_id))
            .maybe_single()
            .execute()
        )
        if result is None:
            return None
        return result.data

    def update_integration_job(
        self,
        job_id: UUID,
        *,
        status: str | None = None,
        stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
        clear_stage: bool = False,
        total_notams: int | None = None,
        cat1_notams: int | None = None,
        cat2_notams: int | None = None,
        cat3_notams: int | None = None,
    ) -> None:
        payload: dict[str, object] = {}
        if status is not None:
            payload["status"] = status
        if clear_stage:
            payload["stage"] = None
        elif stage is not None:
            payload["stage"] = stage
        if error_code is not None:
            payload["error_code"] = error_code
        if error_message is not None:
            payload["error_message"] = error_message
        if completed_at is not None:
            payload["completed_at"] = completed_at.isoformat()
        if total_notams is not None:
            payload["total_notams"] = total_notams
        if cat1_notams is not None:
            payload["cat1_notams"] = cat1_notams
        if cat2_notams is not None:
            payload["cat2_notams"] = cat2_notams
        if cat3_notams is not None:
            payload["cat3_notams"] = cat3_notams
        if not payload:
            return
        self._client.table("analysis_jobs").update(payload).eq(
            "id",
            str(job_id),
        ).execute()

    def mark_failed(self, job_id: UUID, error_message: str) -> None:
        self._client.table("analysis_jobs").update(
            {
                "status": "failed",
                "error_message": error_message,
            }
        ).eq("id", str(job_id)).execute()

    def update_status(self, job_id: UUID, status: str) -> None:
        self._client.table("analysis_jobs").update({"status": status}).eq(
            "id",
            str(job_id),
        ).execute()

    def get_job(self, job_id: UUID) -> dict | None:
        result = (
            self._client.table("analysis_jobs")
            .select(
                "id, status, flight_plan_id, organisation_id, "
                "flight_plans!inner(flight_id)"
            )
            .eq("id", str(job_id))
            .maybe_single()
            .execute()
        )
        return result.data

    def download_flight_plan_pdf(self, storage_path: str) -> bytes:
        data = self._client.storage.from_(FLIGHT_PLAN_PDFS_BUCKET).download(
            storage_path
        )
        if not data:
            raise FileNotFoundError("Flight plan PDF not found")
        return data

    def verify_flight_plan_pdf(self, storage_path: str) -> None:
        self.download_flight_plan_pdf(storage_path)
