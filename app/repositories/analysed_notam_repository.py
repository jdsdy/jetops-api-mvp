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
        rows: list[tuple[int, NotamResult | None]],
    ) -> None:
        if not rows:
            return

        payload = [
            {
                "anaysis_job_id": str(analysis_job_id),
                "flight_plan_id": str(flight_plan_id),
                "notam_id": raw_notam_id,
                "category": result.category if result is not None else None,
                "summary": result.summary if result is not None else None,
                "did_error": False,
            }
            for raw_notam_id, result in rows
        ]
        self._client.table("analysed_notams").insert(payload).execute()

    def update_analysed_notams(
        self,
        analysis_job_id: UUID,
        rows: list[tuple[int, NotamResult]],
    ) -> None:
        for raw_notam_id, result in rows:
            (
                self._client.table("analysed_notams")
                .update(
                    {
                        "category": result.category,
                        "summary": result.summary,
                        "did_error": False,
                    }
                )
                .eq("anaysis_job_id", str(analysis_job_id))
                .eq("notam_id", raw_notam_id)
                .execute()
            )

    def mark_analysed_notams_errored(
        self,
        analysis_job_id: UUID,
        raw_notam_ids: list[int],
    ) -> None:
        for raw_notam_id in raw_notam_ids:
            (
                self._client.table("analysed_notams")
                .update({"did_error": True})
                .eq("anaysis_job_id", str(analysis_job_id))
                .eq("notam_id", raw_notam_id)
                .execute()
            )
