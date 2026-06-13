# Analysis context

Assembles structured flight and NOTAM data from Supabase for LLM analysis. Used by [`AnalysisService`](../services/analysis-context.md) before the analysis step runs.

See also: [Begin analysis (debug)](../endpoints/v1-jobs-begin-analysis.md).

## Output shape

| Top-level key | Description |
|---|---|
| `flight` | Departure/arrival airfields, planned times, route, cruise level, aircraft specs, alternate ICAO |
| `notams` | All `raw_notams` rows for the job (`analysis_job_id`) |

## Data sources

| Context field | DB source |
|---|---|
| `departure_airfield` / `arrival_airfield` | `flights.departure_icao` / `arrival_icao`, `flight_plans.dept_rwy` / `arr_rwy`, `airports_reference`, matched `airport_runways_reference` row |
| `alternate_airfield_icao` | `flight_plans.alt_icao` |
| `planned_dept_time` / `planned_arr_time` | `flight_plans` |
| `route`, `cruise_level` | `flight_plans` |
| `aircraft` | `fleet_aircraft` + optional `aircraft_reference`, or `fleet_aircraft.custom_data` when reference is null |
| `notams` | `raw_notams` |

Runway dimensions are selected when `dept_rwy` / `arr_rwy` matches `le_ident` or `he_ident` on a runway row (case-insensitive). If no match, `icao` and `rwy` are still set; reference fields are null.

When `fleet_aircraft.aircraft_ref_id` is null, aircraft `make` / `model` come from `fleet_aircraft`; reference fields come from `fleet_aircraft.custom_data` when present (`aac` → instrument approach category, `adg` → aircraft design group). If `custom_data` is also absent, those fields are null.

## Module layout

| Module | Role |
|---|---|
| [`app/schemas/analysis_context.py`](../../app/schemas/analysis_context.py) | Pydantic models |
| [`app/repositories/analysis_context_repository.py`](../../app/repositories/analysis_context_repository.py) | Supabase queries (job bundle join, airports, NOTAMs) |
| [`app/services/analysis_context.py`](../../app/services/analysis_context.py) | Mapping + `build_analysis_context(job_id)` |
| [`app/services/analysis_service.py`](../../app/services/analysis_service.py) | Status transition + returns `flight` only to API |

## Tests

```bash
pytest tests/unit/test_analysis_context.py \
       tests/unit/test_analysis_service.py -v
```
