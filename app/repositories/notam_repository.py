from uuid import UUID

from supabase import Client

from app.schemas.notam import RawNotam


class NotamRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def insert_notams(
        self,
        analysis_job_id: UUID,
        flight_plan_id: UUID,
        notams: list[RawNotam],
    ) -> list[dict]:
        if not notams:
            return []

        rows = [
            {
                "analysis_job_id": str(analysis_job_id),
                "flight_plan_id": str(flight_plan_id),
                "notam_id": notam.notam_id,
                "title": notam.title,
                "q": notam.q,
                "a": notam.a,
                "b": notam.b,
                "c": notam.c,
                "d": notam.d,
                "e": notam.e,
                "f": notam.f,
                "g": notam.g,
            }
            for notam in notams
        ]
        result = self._client.table("raw_notams").insert(rows).execute()
        return result.data or []

    def update_notam_classification(
        self,
        updates: list[tuple[int, str, int]],
    ) -> None:
        for row_id, topic, confidence in updates:
            (
                self._client.table("raw_notams")
                .update({"topic": topic, "topic_confidence": confidence})
                .eq("id", row_id)
                .execute()
            )
