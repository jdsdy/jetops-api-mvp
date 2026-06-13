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
    ) -> None:
        if not notams:
            return

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
        self._client.table("raw_notams").insert(rows).execute()
