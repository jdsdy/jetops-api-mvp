from uuid import UUID

from supabase import Client

from app.schemas.notam_analysis import NotamResult


class AnalysedNotamRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def insert_analysed_notams(
        self,
        analysis_job_id: UUID,
        flight_plan_id: UUID | None,
        rows: list[tuple[int, NotamResult | None]],
    ) -> None:
        if not rows:
            return

        payload = [
            {
                "anaysis_job_id": str(analysis_job_id),
                "flight_plan_id": str(flight_plan_id) if flight_plan_id else None,
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
            update_fields: dict = {}
            if result.category is not None:
                update_fields["category"] = result.category
            if result.summary is not None:
                update_fields["summary"] = result.summary
            if not update_fields:
                continue
            update_fields["did_error"] = False
            (
                self._client.table("analysed_notams")
                .update(update_fields)
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

    def fetch_integration_results(self, analysis_job_id: UUID) -> list[dict]:
        result = (
            self._client.table("analysed_notams")
            .select(
                "category, summary, raw_notams!inner(notam_id)",
            )
            .eq("anaysis_job_id", str(analysis_job_id))
            .eq("did_error", False)
            .execute()
        )
        rows = result.data or []
        output: list[dict] = []
        for row in rows:
            raw_notam = row.get("raw_notams") or {}
            notam_id = raw_notam.get("notam_id")
            category = row.get("category")
            summary = row.get("summary")
            if notam_id is None or category is None or summary is None:
                continue
            output.append(
                {
                    "notam_id": notam_id,
                    "category": category,
                    "summary": summary,
                }
            )
        return output
