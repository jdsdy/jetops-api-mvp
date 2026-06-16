from uuid import UUID

from supabase import Client


class AnalysisContextRepository:
    _JOB_BUNDLE_SELECT = """
        id,
        flight_plan_id,
        flight_plans!inner (
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

    def fetch_job_bundle(self, job_id: UUID) -> dict | None:
        result = (
            self._client.table("analysis_jobs")
            .select(self._JOB_BUNDLE_SELECT)
            .eq("id", str(job_id))
            .maybe_single()
            .execute()
        )
        return result.data

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
            .select("id, title, notam_id, topic, q, a, b, c, d, e, f, g")
            .eq("analysis_job_id", str(job_id))
            .execute()
        )
        return result.data or []
