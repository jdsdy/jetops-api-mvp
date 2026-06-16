import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from app.core.config import Settings, get_settings
from app.schemas.notam_topic import MISC_TOPIC
from app.schemas.analysis_context import FlightContext
from app.schemas.notam_analysis import (
    AnalysisNotamRow,
    AnalysisOutput,
    BatchAnalysisResult,
    BatchCallStats,
    NotamBatchPayload,
    NotamResult,
)
from app.services.notam_topic_prompts import PLACEHOLDER_SYSTEM_PROMPT, get_system_prompt

# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------


def chunk_notam_batches(
    flight: FlightContext,
    notam_rows: list[AnalysisNotamRow],
    *,
    batch_size: int,
    topic: str = MISC_TOPIC,
) -> list[NotamBatchPayload]:
    if not notam_rows:
        return []

    batches: list[NotamBatchPayload] = []
    for start in range(0, len(notam_rows), batch_size):
        batches.append(
            NotamBatchPayload(
                flight=flight,
                notams=notam_rows[start : start + batch_size],
                topic=topic,
            )
        )
    return batches


def group_notam_rows_by_topic(
    notam_rows: list[AnalysisNotamRow],
) -> dict[str, list[AnalysisNotamRow]]:
    grouped: dict[str, list[AnalysisNotamRow]] = {}
    for row in notam_rows:
        topic = row.topic or MISC_TOPIC
        grouped.setdefault(topic, []).append(row)
    return grouped


def build_topic_batches(
    flight: FlightContext,
    notam_rows: list[AnalysisNotamRow],
    *,
    batch_size: int,
) -> list[NotamBatchPayload]:
    batches: list[NotamBatchPayload] = []
    for topic, rows in group_notam_rows_by_topic(notam_rows).items():
        batches.extend(
            chunk_notam_batches(flight, rows, batch_size=batch_size, topic=topic)
        )
    return batches


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def _build_user_message(batch: NotamBatchPayload) -> str:
    payload = {
        "flight": batch.flight.model_dump(mode="json"),
        "notams": [notam.model_dump(mode="json", exclude={"id"}) for notam in batch.notams],
    }
    return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

ANALYSIS_OUTPUT_JSON_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "notam_id": {"type": "string"},
            "category": {"type": "integer"},
            "summary": {"type": "string"},
        },
        "required": ["notam_id", "category", "summary"],
        "additionalProperties": False,
    },
}


def _parse_analysis_response(text: str) -> list[NotamResult]:
    return AnalysisOutput.model_validate_json(text).root


def _batch_result_outcome(
    batch: NotamBatchPayload,
    results: list[NotamResult],
) -> tuple[list[NotamResult], set[str]]:
    expected_ids = {notam.notam_id for notam in batch.notams}
    returned_ids = {result.notam_id for result in results}
    missing = expected_ids - returned_ids
    valid_results = [result for result in results if result.notam_id in expected_ids]
    return valid_results, missing


def _analyze_batch(
    batch: NotamBatchPayload,
    *,
    client: anthropic.Anthropic,
    settings: Settings,
    system_prompt: str | None = None,
) -> tuple[list[NotamResult], BatchCallStats, set[str]]:
    if system_prompt is None:
        system_prompt = get_system_prompt(batch.topic)

    start = time.perf_counter()
    response = client.messages.create(
        model=settings.NOTAM_ANALYSIS_MODEL,
        max_tokens=settings.NOTAM_ANALYSIS_MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _build_user_message(batch)}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": ANALYSIS_OUTPUT_JSON_SCHEMA,
            },
            "effort": "low"
        },
    )
    duration_ms = int((time.perf_counter() - start) * 1000)

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError("NOTAM analysis returned no text output")

    results = _parse_analysis_response(text_blocks[0])
    valid_results, missing = _batch_result_outcome(batch, results)

    stats = BatchCallStats(
        duration_ms=duration_ms,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        batch_size=len(batch.notams),
    )
    return valid_results, stats, missing


def merge_batch_results(*parts: BatchAnalysisResult) -> BatchAnalysisResult:
    if not parts:
        raise ValueError("At least one batch result is required")

    return BatchAnalysisResult(
        results=[result for part in parts for result in part.results],
        batch_stats=[stat for part in parts for stat in part.batch_stats],
        model=parts[0].model,
        token_limit_hit=any(part.token_limit_hit for part in parts),
        missing_notam_ids=parts[-1].missing_notam_ids,
    )


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def analyze_notam_batches(
    batches: list[NotamBatchPayload],
    *,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> BatchAnalysisResult:
    if settings is None:
        settings = get_settings()
    if client is None:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    if not batches:
        return BatchAnalysisResult(
            results=[],
            batch_stats=[],
            model=settings.NOTAM_ANALYSIS_MODEL,
            token_limit_hit=False,
        )

    all_results: list[NotamResult] = []
    batch_stats: list[BatchCallStats] = []
    all_missing: set[str] = set()

    with ThreadPoolExecutor(max_workers=settings.NOTAM_ANALYSIS_MAX_CONCURRENCY) as pool:
        futures = {
            pool.submit(
                _analyze_batch,
                batch,
                client=client,
                settings=settings,
                system_prompt=get_system_prompt(batch.topic),
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            results, stats, missing = future.result()
            all_results.extend(results)
            batch_stats.append(stats)
            all_missing.update(missing)

    token_limit_hit = any(
        stat.output_tokens >= settings.NOTAM_ANALYSIS_MAX_TOKENS for stat in batch_stats
    )

    return BatchAnalysisResult(
        results=all_results,
        batch_stats=batch_stats,
        model=settings.NOTAM_ANALYSIS_MODEL,
        token_limit_hit=token_limit_hit,
        missing_notam_ids=sorted(all_missing),
    )


def map_results_to_raw_notam_ids(
    notam_rows: list[AnalysisNotamRow],
    results: list[NotamResult],
) -> list[tuple[int, NotamResult]]:
    by_notam_id = {row.notam_id: row.id for row in notam_rows}
    mapped: list[tuple[int, NotamResult]] = []
    for result in results:
        raw_id = by_notam_id.get(result.notam_id)
        if raw_id is None:
            raise ValueError(f"Unknown NOTAM id in analysis result: {result.notam_id}")
        mapped.append((raw_id, result))
    return mapped
