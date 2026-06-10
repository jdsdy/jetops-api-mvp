from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.schemas.analysis_context import AircraftContext, AirfieldContext, FlightContext
from app.schemas.notam_analysis import (
    AnalysisNotamRow,
    AnalysisOutput,
    BatchCallStats,
    NotamBatchPayload,
    NotamResult,
)
from app.services.notam_analyzer import (
    analyze_notam_batches,
    chunk_notam_batches,
    map_results_to_raw_notam_ids,
)


def _flight_context() -> FlightContext:
    return FlightContext(
        departure_airfield=AirfieldContext(icao="YSSY", rwy="34L"),
        arrival_airfield=AirfieldContext(icao="YPPH", rwy="03"),
        alternate_airfield_icao="YBLN",
        planned_dept_time=None,
        planned_arr_time=None,
        route="DCT",
        cruise_level="FL430",
        aircraft=AircraftContext(),
    )


def _notam_row(row_id: int, notam_id: str) -> AnalysisNotamRow:
    return AnalysisNotamRow(id=row_id, notam_id=notam_id, e="Test NOTAM")


def test_chunk_notam_batches_splits_into_groups_of_ten() -> None:
    flight = _flight_context()
    rows = [_notam_row(i, f"N{i:03d}/26") for i in range(1, 32)]

    batches = chunk_notam_batches(flight, rows, batch_size=10)

    assert len(batches) == 4
    assert [len(batch.notams) for batch in batches] == [10, 10, 10, 1]
    assert all(batch.flight is flight for batch in batches)


def test_chunk_notam_batches_returns_empty_for_no_notams() -> None:
    assert chunk_notam_batches(_flight_context(), [], batch_size=10) == []


def test_map_results_to_raw_notam_ids_links_icao_strings_to_db_ids() -> None:
    rows = [
        _notam_row(10, "C0481/26 NOTAMN"),
        _notam_row(11, "C0478/26 NOTAMN"),
    ]
    results = [
        NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A"),
        NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="B"),
    ]

    mapped = map_results_to_raw_notam_ids(rows, results)

    assert mapped == [
        (10, results[0]),
        (11, results[1]),
    ]


def test_map_results_raises_for_unknown_notam_id() -> None:
    rows = [_notam_row(1, "C0481/26 NOTAMN")]
    results = [NotamResult(notam_id="UNKNOWN/26", category=1, summary="X")]

    with pytest.raises(ValueError, match="Unknown NOTAM id"):
        map_results_to_raw_notam_ids(rows, results)


def test_analyze_notam_batches_empty_returns_zero_stats() -> None:
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
    )

    result = analyze_notam_batches([], settings=settings)

    assert result.results == []
    assert result.batches == 0
    assert result.token_limit_hit is False


def test_analyze_notam_batches_aggregates_tokens_and_detects_limit() -> None:
    flight = _flight_context()
    batch_one = NotamBatchPayload(
        flight=flight,
        notams=[_notam_row(1, "C0481/26 NOTAMN")],
    )
    batch_two = NotamBatchPayload(
        flight=flight,
        notams=[_notam_row(2, "C0478/26 NOTAMN")],
    )
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
        NOTAM_ANALYSIS_MAX_TOKENS=12000,
        NOTAM_ANALYSIS_MAX_CONCURRENCY=2,
    )

    def fake_analyze(batch, *, client, settings):
        if batch.notams[0].id == 1:
            return (
                [NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
                BatchCallStats(
                    duration_ms=100,
                    input_tokens=1000,
                    output_tokens=500,
                    batch_size=1,
                ),
            )
        return (
            [NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="B")],
            BatchCallStats(
                duration_ms=200,
                input_tokens=2000,
                output_tokens=12000,
                batch_size=1,
            ),
        )

    with patch(
        "app.services.notam_analyzer._analyze_batch",
        side_effect=fake_analyze,
    ):
        result = analyze_notam_batches(
            [batch_one, batch_two],
            client=MagicMock(),
            settings=settings,
        )

    assert result.notams_analysed == 2
    assert result.input_tokens == 3000
    assert result.output_tokens == 12500
    assert result.slowest_batch_ms == 200
    assert result.batch_sizes == [1, 1]
    assert result.token_limit_hit is True


def test_analyze_batch_validates_returned_notam_ids() -> None:
    from app.services.notam_analyzer import _analyze_batch

    flight = _flight_context()
    batch = NotamBatchPayload(
        flight=flight,
        notams=[_notam_row(1, "C0481/26 NOTAMN")],
    )
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
    )
    mock_response = MagicMock()
    mock_response.parsed_output = AnalysisOutput(
        root=[NotamResult(notam_id="WRONG/26", category=1, summary="X")]
    )
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_response

    with pytest.raises(ValueError, match="result mismatch"):
        _analyze_batch(batch, client=mock_client, settings=settings)
