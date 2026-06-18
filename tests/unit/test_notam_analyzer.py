from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.schemas.analysis_context import AircraftContext, AirfieldContext, FlightContext
from app.schemas.notam_analysis import (
    AnalysisNotamRow,
    BatchAnalysisResult,
    BatchCallStats,
    NotamBatchPayload,
    NotamResult,
)
from app.services.notam_analyzer import (
    GENERAL_ANALYSIS_OUTPUT_JSON_SCHEMA,
    PLACEHOLDER_SYSTEM_PROMPT,
    SPECIALIST_ANALYSIS_OUTPUT_JSON_SCHEMA,
    _analyze_batch,
    _batch_result_outcome,
    _parse_analysis_response,
    _parse_specialist_analysis_response,
    analyze_notam_batches,
    build_topic_batches,
    chunk_notam_batches,
    group_notam_rows_by_topic,
    map_results_to_raw_notam_ids,
    merge_batch_results,
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


def _notam_row(row_id: int, notam_id: str, *, topic: str | None = None) -> AnalysisNotamRow:
    return AnalysisNotamRow(id=row_id, notam_id=notam_id, e="Test NOTAM", topic=topic)


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
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
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
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        NOTAM_ANALYSIS_MAX_TOKENS=12000,
        NOTAM_ANALYSIS_MAX_CONCURRENCY=2,
        BETA_SIGNUP_CODE="test-signup-code",
    )

    def fake_analyze(batch, *, client, settings, system_prompt=None):
        if batch.notams[0].id == 1:
            return (
                [NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
                BatchCallStats(
                    duration_ms=100,
                    input_tokens=1000,
                    output_tokens=500,
                    batch_size=1,
                ),
            set(),
            set(),
        )
        return (
            [NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="B")],
            BatchCallStats(
                duration_ms=200,
                input_tokens=2000,
                output_tokens=12000,
                batch_size=1,
            ),
            set(),
            set(),
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


def test_parse_specialist_analysis_response_extracts_rejected_ids() -> None:
    payload = (
        '{"results": [{"notam_id": "C0481/26 NOTAMN", "category": 1, "summary": "Runway"}],'
        '"rejected_notam_ids": ["C0478/26 NOTAMN"]}'
    )

    results, rejected = _parse_specialist_analysis_response(payload)

    assert results == [
        NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="Runway")
    ]
    assert rejected == ["C0478/26 NOTAMN"]


def test_batch_result_outcome_treats_rejected_ids_as_not_missing() -> None:
    flight = _flight_context()
    batch = NotamBatchPayload(
        flight=flight,
        notams=[
            _notam_row(1, "C0481/26 NOTAMN"),
            _notam_row(2, "C0478/26 NOTAMN"),
        ],
        topic="OBSTACLE",
    )
    results = [NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")]

    valid_results, missing, rejected = _batch_result_outcome(
        batch,
        results,
        rejected_notam_ids=["C0478/26 NOTAMN"],
    )

    assert valid_results == results
    assert missing == set()
    assert rejected == {"C0478/26 NOTAMN"}


def test_analyze_notam_batches_collects_rejected_notam_ids() -> None:
    flight = _flight_context()
    batch = NotamBatchPayload(
        flight=flight,
        notams=[
            _notam_row(1, "C0481/26 NOTAMN"),
            _notam_row(2, "C0478/26 NOTAMN"),
        ],
        topic="OBSTACLE",
    )
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
    )

    def fake_analyze(current_batch, *, client, settings, system_prompt=None):
        return (
            [NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
            BatchCallStats(
                duration_ms=100,
                input_tokens=100,
                output_tokens=50,
                batch_size=len(current_batch.notams),
            ),
            set(),
            {"C0478/26 NOTAMN"},
        )

    with (
        patch("app.services.notam_analyzer._analyze_batch", side_effect=fake_analyze),
        patch(
            "app.services.notam_analyzer.get_system_prompt",
            return_value="specialist prompt",
        ),
    ):
        result = analyze_notam_batches([batch], settings=settings)

    assert result.rejected_notam_ids == ["C0478/26 NOTAMN"]
    assert result.missing_notam_ids == []
    assert len(result.results) == 1


def test_parse_analysis_response_validates_json_array() -> None:
    payload = '[{"notam_id": "C0481/26 NOTAMN", "category": 1, "summary": "Runway"}]'

    results = _parse_analysis_response(payload)

    assert results == [
        NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="Runway")
    ]


def test_group_notam_rows_by_topic_defaults_missing_to_misc() -> None:
    rows = [
        _notam_row(1, "N001/26", topic="RUNWAY"),
        _notam_row(2, "N002/26"),
    ]

    grouped = group_notam_rows_by_topic(rows)

    assert grouped["RUNWAY"] == [rows[0]]
    assert grouped["MISC"] == [rows[1]]


def test_build_topic_batches_chunks_each_topic_separately() -> None:
    flight = _flight_context()
    rows = [
        _notam_row(i, f"N{i:03d}/26", topic="RUNWAY" if i <= 11 else "MISC")
        for i in range(1, 14)
    ]

    batches = build_topic_batches(flight, rows, batch_size=10)

    assert len(batches) == 3
    assert batches[0].topic == "RUNWAY"
    assert len(batches[0].notams) == 10
    assert batches[1].topic == "RUNWAY"
    assert len(batches[1].notams) == 1
    assert batches[2].topic == "MISC"
    assert len(batches[2].notams) == 2


def test_analyze_batch_uses_misc_prompt_by_default() -> None:
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
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
    )
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = (
        '[{"notam_id": "C0481/26 NOTAMN", "category": 1, "summary": "Runway"}]'
    )
    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    results, stats, missing, rejected = _analyze_batch(batch, client=mock_client, settings=settings)

    assert results == [
        NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="Runway")
    ]
    assert missing == set()
    assert rejected == set()
    assert stats.batch_size == 1
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": GENERAL_ANALYSIS_OUTPUT_JSON_SCHEMA,
        },
        "effort": "low",
    }
    assert call_kwargs["system"][0]["text"] == PLACEHOLDER_SYSTEM_PROMPT
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_analyze_batch_passes_custom_system_prompt() -> None:
    flight = _flight_context()
    batch = NotamBatchPayload(
        flight=flight,
        notams=[_notam_row(1, "C0481/26 NOTAMN")],
        topic="RUNWAY",
    )
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
    )
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = (
        '{"results": [{"notam_id": "C0481/26 NOTAMN", "category": 1, "summary": "Runway"}],'
        '"rejected_notam_ids": []}'
    )
    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    custom_prompt = "Specialist runway prompt"
    _analyze_batch(
        batch,
        client=mock_client,
        settings=settings,
        system_prompt=custom_prompt,
    )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["output_config"]["format"]["schema"] == SPECIALIST_ANALYSIS_OUTPUT_JSON_SCHEMA
    assert call_kwargs["system"][0]["text"] == custom_prompt


def test_batch_result_outcome_tracks_missing_notam_ids() -> None:
    flight = _flight_context()
    batch = NotamBatchPayload(
        flight=flight,
        notams=[
            _notam_row(1, "C0481/26 NOTAMN"),
            _notam_row(2, "C0478/26 NOTAMN"),
        ],
    )
    results = [NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")]

    valid_results, missing, rejected = _batch_result_outcome(batch, results, rejected_notam_ids=[])

    assert valid_results == results
    assert missing == {"C0478/26 NOTAMN"}
    assert rejected == set()


def test_analyze_batch_returns_missing_instead_of_raising() -> None:
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
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
    )
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = '[{"notam_id": "WRONG/26", "category": 1, "summary": "X"}]'
    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    results, stats, missing, rejected = _analyze_batch(batch, client=mock_client, settings=settings)

    assert results == []
    assert missing == {"C0481/26 NOTAMN"}
    assert rejected == set()


def test_analyze_notam_batches_collects_missing_from_failed_batches() -> None:
    flight = _flight_context()
    batch = NotamBatchPayload(
        flight=flight,
        notams=[
            _notam_row(1, "C0481/26 NOTAMN"),
            _notam_row(2, "C0478/26 NOTAMN"),
        ],
    )
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
    )

    def fake_analyze(current_batch, *, client, settings, system_prompt=None):
        return (
            [NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
            BatchCallStats(
                duration_ms=100,
                input_tokens=100,
                output_tokens=50,
                batch_size=len(current_batch.notams),
            ),
            {"C0478/26 NOTAMN"},
            set(),
        )

    with patch("app.services.notam_analyzer._analyze_batch", side_effect=fake_analyze):
        result = analyze_notam_batches([batch], settings=settings)

    assert result.missing_notam_ids == ["C0478/26 NOTAMN"]
    assert len(result.results) == 1


def test_merge_batch_results_combines_stats_and_keeps_final_missing() -> None:
    first = BatchAnalysisResult(
        results=[NotamResult(notam_id="C0481/26 NOTAMN", category=1, summary="A")],
        batch_stats=[
            BatchCallStats(
                duration_ms=100,
                input_tokens=100,
                output_tokens=50,
                batch_size=1,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
        missing_notam_ids=["C0478/26 NOTAMN"],
    )
    second = BatchAnalysisResult(
        results=[NotamResult(notam_id="C0478/26 NOTAMN", category=2, summary="B")],
        batch_stats=[
            BatchCallStats(
                duration_ms=200,
                input_tokens=200,
                output_tokens=60,
                batch_size=1,
            )
        ],
        model="claude-sonnet-4-6",
        token_limit_hit=False,
        missing_notam_ids=[],
    )

    merged = merge_batch_results(first, second)

    assert merged.notams_analysed == 2
    assert merged.missing_notam_ids == []
    assert merged.batches == 2
    assert merged.input_tokens == 300
