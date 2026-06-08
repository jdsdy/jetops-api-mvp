from datetime import datetime
from uuid import UUID

from supabase import Client

from app.schemas.flight import FlightData


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class FlightRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def get_flight_id(self, flight_plan_id: UUID) -> UUID:
        result = (
            self._client.table("flight_plans")
            .select("flight_id")
            .eq("id", str(flight_plan_id))
            .single()
            .execute()
        )
        return UUID(result.data["flight_id"])

    def update_from_extraction(
        self,
        flight_id: UUID,
        flight_plan_id: UUID,
        flight_data: FlightData,
    ) -> None:
        self._client.table("flights").update(
            {
                "departure_icao": flight_data.departure_icao,
                "arrival_icao": flight_data.arrival_icao,
            }
        ).eq("id", str(flight_id)).execute()

        self._client.table("flight_plans").update(
            {
                "route": flight_data.route,
                "cruise_level": flight_data.cruise_level,
                "planned_dept_time": _to_iso(flight_data.planned_dept_time),
                "planned_arr_time": _to_iso(flight_data.planned_arr_time),
                "alt_icao": flight_data.alt_icao,
                "source_app": flight_data.source_app,
            }
        ).eq("id", str(flight_plan_id)).execute()
