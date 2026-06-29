from unittest.mock import MagicMock
from uuid import uuid4

from app.repositories.analysis_context_repository import (
    AnalysisContextRepository,
    _merge_current_flight_plan,
)


def test_merge_current_flight_plan_overlays_plan_fields() -> None:
    bundle = {
        "id": str(uuid4()),
        "flight_plan_id": str(uuid4()),
        "flight_plans": {
            "flight_id": str(uuid4()),
            "route": "OLD ROUTE",
            "cruise_level": "FL100",
            "dept_rwy": "01",
            "arr_rwy": "19",
            "alt_icao": "YOLD",
            "planned_dept_time": "2026-01-01T00:00:00+00:00",
            "planned_arr_time": "2026-01-01T01:00:00+00:00",
            "flights": {"departure_icao": "YSSY", "arrival_icao": "YPPH"},
        },
    }
    current_plan = {
        "route": "NEW ROUTE",
        "cruise_level": "FL430",
        "dept_rwy": "34L",
        "arr_rwy": "03",
        "alt_icao": "YBLN",
        "planned_dept_time": "2026-04-15T11:35:00+00:00",
        "planned_arr_time": "2026-04-15T15:42:00+00:00",
    }

    merged = _merge_current_flight_plan(bundle, current_plan)

    assert merged["flight_plans"]["route"] == "NEW ROUTE"
    assert merged["flight_plans"]["cruise_level"] == "FL430"
    assert merged["flight_plans"]["dept_rwy"] == "34L"
    assert merged["flight_plans"]["flights"]["departure_icao"] == "YSSY"


def test_merge_current_flight_plan_returns_bundle_when_no_current_plan() -> None:
    bundle = {
        "flight_plans": {
            "route": "OLD ROUTE",
            "flights": {"departure_icao": "YSSY"},
        }
    }

    merged = _merge_current_flight_plan(bundle, None)

    assert merged is bundle
    assert merged["flight_plans"]["route"] == "OLD ROUTE"


def test_fetch_current_flight_plan_filters_is_current_and_orders_by_created_at() -> (
    None
):
    flight_id = uuid4()
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[{"route": "CURRENT", "cruise_level": "FL430"}]
    )

    repository = AnalysisContextRepository(mock_client)
    result = repository.fetch_current_flight_plan(flight_id)

    mock_client.table.assert_called_once_with("flight_plans")
    mock_table.eq.assert_any_call("flight_id", str(flight_id))
    mock_table.eq.assert_any_call("is_current", True)
    mock_table.order.assert_called_once_with("created_at", desc=True)
    mock_table.limit.assert_called_once_with(1)
    assert result == {"route": "CURRENT", "cruise_level": "FL430"}


def test_fetch_current_flight_plan_returns_none_when_no_rows() -> None:
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    repository = AnalysisContextRepository(mock_client)
    assert repository.fetch_current_flight_plan(uuid4()) is None


def test_fetch_job_bundle_uses_current_flight_plan() -> None:
    job_id = uuid4()
    flight_id = uuid4()
    mock_client = MagicMock()
    mock_jobs_table = MagicMock()
    mock_plans_table = MagicMock()

    def table(name: str) -> MagicMock:
        if name == "analysis_jobs":
            return mock_jobs_table
        if name == "flight_plans":
            return mock_plans_table
        raise AssertionError(f"unexpected table {name}")

    mock_client.table.side_effect = table
    mock_jobs_table.select.return_value = mock_jobs_table
    mock_jobs_table.eq.return_value = mock_jobs_table
    mock_jobs_table.maybe_single.return_value = mock_jobs_table
    mock_jobs_table.execute.return_value = MagicMock(
        data={
            "id": str(job_id),
            "flight_plan_id": str(uuid4()),
            "flight_plans": {
                "flight_id": str(flight_id),
                "route": "JOB PLAN ROUTE",
                "cruise_level": "FL100",
                "dept_rwy": "01",
                "arr_rwy": "19",
                "alt_icao": None,
                "planned_dept_time": None,
                "planned_arr_time": None,
                "flights": {
                    "departure_icao": "YSSY",
                    "arrival_icao": "YPPH",
                    "fleet_aircraft": None,
                },
            },
        }
    )
    mock_plans_table.select.return_value = mock_plans_table
    mock_plans_table.eq.return_value = mock_plans_table
    mock_plans_table.order.return_value = mock_plans_table
    mock_plans_table.limit.return_value = mock_plans_table
    mock_plans_table.execute.return_value = MagicMock(
        data=[
            {
                "route": "CURRENT ROUTE",
                "cruise_level": "FL430",
                "dept_rwy": "34L",
                "arr_rwy": "03",
                "alt_icao": "YBLN",
                "planned_dept_time": "2026-04-15T11:35:00+00:00",
                "planned_arr_time": "2026-04-15T15:42:00+00:00",
            }
        ]
    )

    repository = AnalysisContextRepository(mock_client)
    bundle = repository.fetch_job_bundle(job_id)

    assert bundle is not None
    assert bundle["flight_plans"]["route"] == "CURRENT ROUTE"
    assert bundle["flight_plans"]["cruise_level"] == "FL430"
    assert bundle["flight_plans"]["dept_rwy"] == "34L"
