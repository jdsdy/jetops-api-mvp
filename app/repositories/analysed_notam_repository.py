from uuid import UUID

from supabase import Client

from app.schemas.notam_analysis import NotamResult


class AnalysedNotamRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def insert_analysed_notams(
        self,
        analysis_job_id: UUID,
        flight_plan_id: UUID,
        rows: list[tuple[int, NotamResult]],
    ) -> None:
        if not rows:
            return

        payload = [
            {
                "anaysis_job_id": str(analysis_job_id),
                "flight_plan_id": str(flight_plan_id),
                "notam_id": raw_notam_id,
                "category": result.category,
                "summary": result.summary,
                "was_cached": None,
            }
            for raw_notam_id, result in rows
        ]
        self._client.table("analysed_notams").insert(payload).execute()
