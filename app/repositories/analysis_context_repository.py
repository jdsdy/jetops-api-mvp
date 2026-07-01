from uuid import UUID

from supabase import Client

_FLIGHT_PLAN_FIELDS = (
    "route",
    "cruise_level",
    "dept_rwy",
    "arr_rwy",
    "alt_icao",
    "planned_dept_time",
    "planned_arr_time",
)

_CURRENT_FLIGHT_PLAN_SELECT = ", ".join(_FLIGHT_PLAN_FIELDS)


def _merge_current_flight_plan(bundle: dict, current_plan: dict | None) -> dict:
    if not current_plan:
        return bundle

    flight_plans = dict(bundle["flight_plans"])
    for field in _FLIGHT_PLAN_FIELDS:
        if field in current_plan:
            flight_plans[field] = current_plan[field]
    return {**bundle, "flight_plans": flight_plans}


class AnalysisContextRepository:
    _JOB_BUNDLE_SELECT = """
        id,
        flight_plan_id,
        flight_plans!inner (
            flight_id,
            route,
            cruise_level,
            dept_rwy,
            arr_rwy,
            alt_icao,
            planned_dept_time,
            planned_arr_time,
            flights!inner (
                departure_icao,
                arrival_icao,
                fleet_aircraft (
                    tail_number,
                    seats,
                    rnav_equipped,
                    manufacturer,
                    model,
                    custom_data,
                    aircraft_reference (
                        manufacturer,
                        model,
                        wingspan_m,
                        wingspan_ft,
                        length_m,
                        length_ft,
                        icao_wtc,
                        weight_class,
                        adc,
                        aac
                    )
                )
            )
        )
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def fetch_current_flight_plan(self, flight_id: UUID) -> dict | None:
        result = (
            self._client.table("flight_plans")
            .select(_CURRENT_FLIGHT_PLAN_SELECT)
            .eq("flight_id", str(flight_id))
            .eq("is_current", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return result.data[0]

    def fetch_job_bundle(self, job_id: UUID) -> dict | None:
        result = (
            self._client.table("analysis_jobs")
            .select(self._JOB_BUNDLE_SELECT)
            .eq("id", str(job_id))
            .maybe_single()
            .execute()
        )
        if not result.data:
            return None

        flight_id = UUID(result.data["flight_plans"]["flight_id"])
        current_plan = self.fetch_current_flight_plan(flight_id)
        return _merge_current_flight_plan(result.data, current_plan)

    def fetch_airport_context(self, icao: str | None) -> dict | None:
        if not icao:
            return None

        result = (
            self._client.table("airports_reference")
            .select("icao_code, iso_country, airport_runways_reference(*)")
            .eq("icao_code", icao)
            .maybe_single()
            .execute()
        )
        return result.data

    def fetch_notams(self, job_id: UUID) -> list[dict]:
        result = (
            self._client.table("raw_notams")
            .select("id, title, notam_id, topic, topic_confidence, q, a, b, c, d, e, f, g")
            .eq("analysis_job_id", str(job_id))
            .execute()
        )
        return result.data or []
