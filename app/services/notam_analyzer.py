import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from app.core.config import Settings, get_settings
from app.schemas.analysis_context import FlightContext
from app.schemas.notam_topic import MISC_TOPIC
from app.schemas.notam_analysis import (
    AnalysisJobResult,
    AnalysisNotamRow,
    BatchAnalysisResult,
    BatchCallStats,
    CategoryBatchResult,
    CategoryOutput,
    CategoryResult,
    NotamBatchPayload,
    NotamResult,
    SpecialistCategoryOutput,
    SummaryBatchPayload,
    SummaryBatchResult,
    SummaryOutput,
    SummaryResult,
)
from app.services.notam_heuristic_category import (
    heuristic_category,
    is_heuristic_category_candidate,
)
from app.services.notam_categorize_agent import get_categorize_agent_config
from app.services.notam_prompts.summary import SUMMARY
from app.services.notam_topic_prompts import get_system_prompt

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


def chunk_summary_batches(
    notam_rows: list[AnalysisNotamRow],
    *,
    batch_size: int,
) -> list[SummaryBatchPayload]:
    if not notam_rows:
        return []

    batches: list[SummaryBatchPayload] = []
    for start in range(0, len(notam_rows), batch_size):
        batches.append(
            SummaryBatchPayload(notams=notam_rows[start : start + batch_size])
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


def partition_notam_rows(
    notam_rows: list[AnalysisNotamRow],
    *,
    settings: Settings | None = None,
) -> tuple[list[AnalysisNotamRow], list[AnalysisNotamRow]]:
    heuristic_rows: list[AnalysisNotamRow] = []
    agent_rows: list[AnalysisNotamRow] = []
    for row in notam_rows:
        if is_heuristic_category_candidate(row, settings=settings):
            heuristic_rows.append(row)
        else:
            agent_rows.append(row)
    return heuristic_rows, agent_rows


# ---------------------------------------------------------------------------
# Prompt payloads
# ---------------------------------------------------------------------------


def _build_user_message(batch: NotamBatchPayload) -> str:
    payload = {
        "flight": batch.flight.model_dump(mode="json"),
        "notams": [
            notam.model_dump(mode="json", exclude={"id", "topic_confidence"})
            for notam in batch.notams
        ],
    }
    return json.dumps(payload, default=str)


def _build_summary_user_message(batch: SummaryBatchPayload) -> str:
    payload = {
        "notams": [
            notam.model_dump(
                mode="json",
                include={
                    "title",
                    "notam_id",
                    "q",
                    "a",
                    "b",
                    "c",
                    "d",
                    "e",
                    "f",
                    "g",
                },
            )
            for notam in batch.notams
        ],
    }
    return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# JSON schemas
# ---------------------------------------------------------------------------

GENERAL_CATEGORY_OUTPUT_JSON_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "notam_id": {"type": "string"},
            "category": {"type": "integer"},
        },
        "required": ["notam_id", "category"],
        "additionalProperties": False,
    },
}

SPECIALIST_CATEGORY_OUTPUT_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "results": GENERAL_CATEGORY_OUTPUT_JSON_SCHEMA,
        "rejected_notam_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["results", "rejected_notam_ids"],
    "additionalProperties": False,
}

SUMMARY_OUTPUT_JSON_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "notam_id": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["notam_id", "summary"],
        "additionalProperties": False,
    },
}

# Backward-compatible aliases for tests referencing the general-agent schema.
GENERAL_ANALYSIS_OUTPUT_JSON_SCHEMA = GENERAL_CATEGORY_OUTPUT_JSON_SCHEMA
SPECIALIST_ANALYSIS_OUTPUT_JSON_SCHEMA = SPECIALIST_CATEGORY_OUTPUT_JSON_SCHEMA
ANALYSIS_OUTPUT_JSON_SCHEMA = GENERAL_CATEGORY_OUTPUT_JSON_SCHEMA


def _category_output_schema_for_topic(topic: str) -> dict:
    if topic == MISC_TOPIC:
        return GENERAL_CATEGORY_OUTPUT_JSON_SCHEMA
    return SPECIALIST_CATEGORY_OUTPUT_JSON_SCHEMA


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_category_response(text: str) -> list[CategoryResult]:
    return CategoryOutput.model_validate_json(text).root


def _parse_specialist_category_response(
    text: str,
) -> tuple[list[CategoryResult], list[str]]:
    parsed = SpecialistCategoryOutput.model_validate_json(text)
    return parsed.results, parsed.rejected_notam_ids


def _parse_summary_response(text: str) -> list[SummaryResult]:
    return SummaryOutput.model_validate_json(text).root


# Backward-compatible parser aliases.
def _parse_analysis_response(text: str) -> list[NotamResult]:
    categories = _parse_category_response(text)
    return [
        NotamResult(notam_id=result.notam_id, category=result.category)
        for result in categories
    ]


def _parse_specialist_analysis_response(
    text: str,
) -> tuple[list[NotamResult], list[str]]:
    categories, rejected = _parse_specialist_category_response(text)
    return [
        NotamResult(notam_id=result.notam_id, category=result.category)
        for result in categories
    ], rejected


def _category_batch_outcome(
    batch: NotamBatchPayload,
    results: list[CategoryResult],
    *,
    rejected_notam_ids: list[str],
) -> tuple[list[CategoryResult], set[str], set[str]]:
    expected_ids = {notam.notam_id for notam in batch.notams}
    returned_ids = {result.notam_id for result in results}
    rejected = {
        notam_id for notam_id in rejected_notam_ids if notam_id in expected_ids
    } - returned_ids
    missing = expected_ids - returned_ids - rejected
    valid_results = [
        result for result in results if result.notam_id in expected_ids
    ]
    return valid_results, missing, rejected


def _summary_batch_outcome(
    batch: SummaryBatchPayload,
    results: list[SummaryResult],
) -> tuple[list[SummaryResult], set[str]]:
    expected_ids = {notam.notam_id for notam in batch.notams}
    returned_ids = {result.notam_id for result in results}
    missing = expected_ids - returned_ids
    valid_results = [
        result for result in results if result.notam_id in expected_ids
    ]
    return valid_results, missing


# ---------------------------------------------------------------------------
# Anthropic batch calls
# ---------------------------------------------------------------------------


def _categorize_batch(
    batch: NotamBatchPayload,
    *,
    client: anthropic.Anthropic,
    settings: Settings,
    system_prompt: str | None = None,
) -> tuple[list[CategoryResult], BatchCallStats, set[str], set[str]]:
    if system_prompt is None:
        system_prompt = get_system_prompt(batch.topic)

    output_schema = _category_output_schema_for_topic(batch.topic)
    agent_config = get_categorize_agent_config(batch.topic, settings)
    start = time.perf_counter()
    response = client.messages.create(
        model=agent_config.model,
        max_tokens=agent_config.max_tokens,
        thinking=agent_config.thinking,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _build_user_message(batch)}],
        output_config=agent_config.category_output_config(output_schema),
    )
    duration_ms = int((time.perf_counter() - start) * 1000)

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError("NOTAM categorization returned no text output")

    if batch.topic == MISC_TOPIC:
        results = _parse_category_response(text_blocks[0])
        rejected_notam_ids: list[str] = []
    else:
        results, rejected_notam_ids = _parse_specialist_category_response(
            text_blocks[0]
        )

    valid_results, missing, rejected = _category_batch_outcome(
        batch,
        results,
        rejected_notam_ids=rejected_notam_ids,
    )

    stats = BatchCallStats(
        duration_ms=duration_ms,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        batch_size=len(batch.notams),
        model=agent_config.model,
        max_tokens=agent_config.max_tokens,
        input_cost_per_m=agent_config.input_cost_per_m,
        output_cost_per_m=agent_config.output_cost_per_m,
    )
    return valid_results, stats, missing, rejected


def _summarize_batch(
    batch: SummaryBatchPayload,
    *,
    client: anthropic.Anthropic,
    settings: Settings,
) -> tuple[list[SummaryResult], BatchCallStats, set[str]]:
    start = time.perf_counter()
    response = client.messages.create(
        model=settings.NOTAM_SUMMARY_MODEL,
        max_tokens=settings.NOTAM_SUMMARY_MAX_TOKENS,
        thinking={"type": "disabled"},
        system=[
            {
                "type": "text",
                "text": SUMMARY,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": _build_summary_user_message(batch)}
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": SUMMARY_OUTPUT_JSON_SCHEMA,
            },
        },
    )
    duration_ms = int((time.perf_counter() - start) * 1000)

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError("NOTAM summarization returned no text output")

    results = _parse_summary_response(text_blocks[0])
    valid_results, missing = _summary_batch_outcome(batch, results)

    stats = BatchCallStats(
        duration_ms=duration_ms,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        batch_size=len(batch.notams),
    )
    return valid_results, stats, missing


# Backward-compatible alias used by existing unit tests.
_analyze_batch = _categorize_batch


def _batch_result_outcome(
    batch: NotamBatchPayload,
    results: list[NotamResult],
    *,
    rejected_notam_ids: list[str],
) -> tuple[list[NotamResult], set[str], set[str]]:
    categories = [
        CategoryResult(notam_id=result.notam_id, category=result.category)
        for result in results
        if result.category is not None
    ]
    valid_categories, missing, rejected = _category_batch_outcome(
        batch,
        categories,
        rejected_notam_ids=rejected_notam_ids,
    )
    valid_results = [
        NotamResult(notam_id=result.notam_id, category=result.category)
        for result in valid_categories
    ]
    return valid_results, missing, rejected


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def merge_category_batch_results(*parts: CategoryBatchResult) -> CategoryBatchResult:
    if not parts:
        raise ValueError("At least one category batch result is required")

    by_notam_id: dict[str, CategoryResult] = {}
    for part in parts:
        for result in part.results:
            by_notam_id[result.notam_id] = result

    return CategoryBatchResult(
        results=list(by_notam_id.values()),
        batch_stats=[stat for part in parts for stat in part.batch_stats],
        model=parts[0].model,
        token_limit_hit=any(part.token_limit_hit for part in parts),
        missing_notam_ids=parts[-1].missing_notam_ids,
        rejected_notam_ids=parts[-1].rejected_notam_ids,
    )


def merge_summary_batch_results(*parts: SummaryBatchResult) -> SummaryBatchResult:
    if not parts:
        raise ValueError("At least one summary batch result is required")

    by_notam_id: dict[str, SummaryResult] = {}
    for part in parts:
        for result in part.results:
            by_notam_id[result.notam_id] = result

    return SummaryBatchResult(
        results=list(by_notam_id.values()),
        batch_stats=[stat for part in parts for stat in part.batch_stats],
        model=parts[0].model,
        token_limit_hit=any(part.token_limit_hit for part in parts),
        missing_notam_ids=parts[-1].missing_notam_ids,
    )


def merge_notam_results(
    notam_rows: list[AnalysisNotamRow],
    categories: list[CategoryResult],
    summaries: list[SummaryResult],
) -> list[NotamResult]:
    category_by_id = {result.notam_id: result.category for result in categories}
    summary_by_id = {result.notam_id: result.summary for result in summaries}
    return [
        NotamResult(
            notam_id=row.notam_id,
            category=category_by_id.get(row.notam_id),
            summary=summary_by_id.get(row.notam_id),
        )
        for row in notam_rows
    ]


def merge_analysis_job_results(*parts: AnalysisJobResult) -> AnalysisJobResult:
    if not parts:
        raise ValueError("At least one analysis job result is required")

    by_notam_id: dict[str, NotamResult] = {}
    for part in parts:
        for result in part.results:
            existing = by_notam_id.get(result.notam_id)
            if existing is None:
                by_notam_id[result.notam_id] = result
                continue
            by_notam_id[result.notam_id] = NotamResult(
                notam_id=result.notam_id,
                category=result.category
                if result.category is not None
                else existing.category,
                summary=result.summary
                if result.summary is not None
                else existing.summary,
            )

    return AnalysisJobResult(
        results=list(by_notam_id.values()),
        category_result=merge_category_batch_results(
            *(part.category_result for part in parts)
        ),
        summary_result=merge_summary_batch_results(
            *(part.summary_result for part in parts)
        ),
        heuristic_category_count=parts[0].heuristic_category_count,
    )


def merge_batch_results(*parts: BatchAnalysisResult) -> BatchAnalysisResult:
    if not parts:
        raise ValueError("At least one batch result is required")

    return BatchAnalysisResult(
        results=[result for part in parts for result in part.results],
        batch_stats=[stat for part in parts for stat in part.batch_stats],
        model=parts[0].model,
        token_limit_hit=any(part.token_limit_hit for part in parts),
        missing_notam_ids=parts[-1].missing_notam_ids,
        rejected_notam_ids=parts[-1].rejected_notam_ids,
    )


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def categorize_notam_batches(
    batches: list[NotamBatchPayload],
    *,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> CategoryBatchResult:
    if settings is None:
        settings = get_settings()
    if client is None:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    if not batches:
        return CategoryBatchResult(
            results=[],
            batch_stats=[],
            model=settings.NOTAM_ANALYSIS_MODEL,
            token_limit_hit=False,
        )

    all_results: list[CategoryResult] = []
    batch_stats: list[BatchCallStats] = []
    all_missing: set[str] = set()
    all_rejected: set[str] = set()

    with ThreadPoolExecutor(max_workers=settings.NOTAM_ANALYSIS_MAX_CONCURRENCY) as pool:
        futures = {
            pool.submit(
                _categorize_batch,
                batch,
                client=client,
                settings=settings,
                system_prompt=get_system_prompt(batch.topic),
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            results, stats, missing, rejected = future.result()
            all_results.extend(results)
            batch_stats.append(stats)
            all_missing.update(missing)
            all_rejected.update(rejected)

    token_limit_hit = any(
        stat.output_tokens
        >= (stat.max_tokens or settings.NOTAM_ANALYSIS_MAX_TOKENS)
        for stat in batch_stats
    )

    return CategoryBatchResult(
        results=all_results,
        batch_stats=batch_stats,
        model=settings.NOTAM_ANALYSIS_MODEL,
        token_limit_hit=token_limit_hit,
        missing_notam_ids=sorted(all_missing),
        rejected_notam_ids=sorted(all_rejected),
    )


def summarize_notam_batches(
    batches: list[SummaryBatchPayload],
    *,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> SummaryBatchResult:
    if settings is None:
        settings = get_settings()
    if client is None:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    if not batches:
        return SummaryBatchResult(
            results=[],
            batch_stats=[],
            model=settings.NOTAM_SUMMARY_MODEL,
            token_limit_hit=False,
        )

    all_results: list[SummaryResult] = []
    batch_stats: list[BatchCallStats] = []
    all_missing: set[str] = set()

    with ThreadPoolExecutor(max_workers=settings.NOTAM_ANALYSIS_MAX_CONCURRENCY) as pool:
        futures = {
            pool.submit(
                _summarize_batch,
                batch,
                client=client,
                settings=settings,
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            results, stats, missing = future.result()
            all_results.extend(results)
            batch_stats.append(stats)
            all_missing.update(missing)

    token_limit_hit = any(
        stat.output_tokens >= settings.NOTAM_SUMMARY_MAX_TOKENS for stat in batch_stats
    )

    return SummaryBatchResult(
        results=all_results,
        batch_stats=batch_stats,
        model=settings.NOTAM_SUMMARY_MODEL,
        token_limit_hit=token_limit_hit,
        missing_notam_ids=sorted(all_missing),
    )


def analyze_notam_job(
    flight: FlightContext,
    notam_rows: list[AnalysisNotamRow],
    *,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> AnalysisJobResult:
    if settings is None:
        settings = get_settings()
    if client is None:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    if not notam_rows:
        return AnalysisJobResult(
            results=[],
            category_result=CategoryBatchResult(
                results=[],
                batch_stats=[],
                model=settings.NOTAM_ANALYSIS_MODEL,
                token_limit_hit=False,
            ),
            summary_result=SummaryBatchResult(
                results=[],
                batch_stats=[],
                model=settings.NOTAM_SUMMARY_MODEL,
                token_limit_hit=False,
            ),
        )

    heuristic_rows, agent_rows = partition_notam_rows(notam_rows, settings=settings)
    heuristic_categories = [
        CategoryResult(notam_id=row.notam_id, category=heuristic_category(row))
        for row in heuristic_rows
    ]

    categorize_batches = build_topic_batches(
        flight,
        agent_rows,
        batch_size=settings.NOTAM_ANALYSIS_BATCH_SIZE,
    )
    summarize_batches = chunk_summary_batches(
        notam_rows,
        batch_size=settings.NOTAM_SUMMARY_BATCH_SIZE,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        category_future = pool.submit(
            categorize_notam_batches,
            categorize_batches,
            client=client,
            settings=settings,
        )
        summary_future = pool.submit(
            summarize_notam_batches,
            summarize_batches,
            client=client,
            settings=settings,
        )
        category_result = category_future.result()
        summary_result = summary_future.result()

    all_categories = heuristic_categories + category_result.results
    results = merge_notam_results(notam_rows, all_categories, summary_result.results)

    return AnalysisJobResult(
        results=results,
        category_result=category_result,
        summary_result=summary_result,
        heuristic_category_count=len(heuristic_rows),
    )


def analyze_notam_batches(
    batches: list[NotamBatchPayload],
    *,
    client: anthropic.Anthropic | None = None,
    settings: Settings | None = None,
) -> BatchAnalysisResult:
    category_result = categorize_notam_batches(
        batches,
        client=client,
        settings=settings,
    )
    return BatchAnalysisResult(
        results=[
            NotamResult(notam_id=result.notam_id, category=result.category)
            for result in category_result.results
        ],
        batch_stats=category_result.batch_stats,
        model=category_result.model,
        token_limit_hit=category_result.token_limit_hit,
        missing_notam_ids=category_result.missing_notam_ids,
        rejected_notam_ids=category_result.rejected_notam_ids,
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
