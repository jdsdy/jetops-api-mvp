# NOTAM LLM analysis

Batched Claude analysis of parsed NOTAMs for a confirmed flight plan job.

See also: [Begin analysis](../endpoints/v1-jobs-begin-analysis.md) and [Analysis context](analysis-context.md).

## Flow

1. **Sync** (`POST /v1/jobs/analysis`): validate job, build flight context (no NOTAMs), set `processing_analysis`, return `{ "response_begun": true }`.
2. **Background** (`run_analysis_task`): build flight context → fetch `raw_notams` → batch (10 per request) → concurrent Claude calls → on missing NOTAM IDs, set `retrying` and re-analyse only those NOTAMs in batches of 5 → persist `analysed_notams` → set `finished` or `partial_finish`.

## Module layout

| Module | Role |
|---|---|
| [`app/services/analysis_service.py`](../../app/services/analysis_service.py) | Sync validation and status transition |
| [`app/services/analysis_task.py`](../../app/services/analysis_task.py) | Background pipeline orchestration |
| [`app/services/notam_analyzer.py`](../../app/services/notam_analyzer.py) | Batching, prompt assembly, Anthropic `messages.create` with JSON schema |
| [`app/repositories/analysed_notam_repository.py`](../../app/repositories/analysed_notam_repository.py) | Bulk insert into `analysed_notams` |

## Batching

NOTAMs are chunked into groups of `NOTAM_ANALYSIS_BATCH_SIZE` (default 10). Each batch payload repeats the same `FlightContext` with a slice of NOTAM rows:

```json
{ "flight": { ... }, "notams": [ ... ] }
```

Batches run concurrently via `ThreadPoolExecutor` with `NOTAM_ANALYSIS_MAX_CONCURRENCY` workers (default 4).

If the model omits NOTAM IDs from a batch response, those IDs are collected as `missing_notam_ids` rather than failing the whole job. Before retrying, successfully analysed NOTAMs are inserted into `analysed_notams` and missing NOTAMs are inserted with `category` and `summary` set to `null` and `did_error` set to `false`. The pipeline then sets `retrying` and re-analyses only the missing NOTAMs in batches of `NOTAM_ANALYSIS_RETRY_BATCH_SIZE` (default 5). Retry successes update the placeholder rows; retry failures set `did_error` to `true`.

## Claude settings

| Setting | Default |
|---|---|
| `NOTAM_ANALYSIS_MODEL` | `claude-sonnet-4-6` |
| `NOTAM_ANALYSIS_BATCH_SIZE` | `10` |
| `NOTAM_ANALYSIS_RETRY_BATCH_SIZE` | `5` |
| `NOTAM_ANALYSIS_MAX_TOKENS` | `12000` |
| `NOTAM_ANALYSIS_INPUT_COST_PER_M` | `3.0` USD |
| `NOTAM_ANALYSIS_OUTPUT_COST_PER_M` | `15.0` USD |

Structured output uses `client.messages.create()` with `output_config.format` (`json_schema` array of `notam_id`, `category`, `summary`). The system prompt is cached via `cache_control` on the system text block. Thinking/reasoning is disabled. Response JSON is validated into `NotamResult` models.

## Pipeline stage logs

| `stage_name` | Metadata |
|---|---|
| `build_context_object` | `departure_airfield_full_data_found`, `arrival_airfield_full_data_found`, `aircraft_full_data_found` |
| `notam_analysis` | `batches`, `notams_analysed`, `model`, `batch_sizes`, `token_limit_hit`, `slowest_batch_ms`, `input_tokens`, `output_tokens`, `est_cost`, `retried_notam_ids` (when retry ran) |

**Full data found** rules:

- Airfield: `iso_country` and `length_ft` both non-null (runway row matched).
- Aircraft: `icao_wtc` non-null (linked `aircraft_reference` row or `fleet_aircraft.custom_data`).

## Persistence

Results are written to `analysed_notams`:

| Column | Source |
|---|---|
| `anaysis_job_id` | Job UUID (DB column name as stored) |
| `flight_plan_id` | Request flight plan UUID |
| `notam_id` | `raw_notams.id` (bigint FK) |
| `category` | LLM `NotamResult.category` (`null` until retry succeeds) |
| `summary` | LLM `NotamResult.summary` (`null` until retry succeeds) |
| `did_error` | `false` on insert; set `true` when retry still fails for that NOTAM |
| `created_at` | Row insert timestamp (DB default) |

LLM `notam_id` strings (ICAO format) are mapped to `raw_notams.id` before insert. Unknown IDs fail the job.

## Job status

| Outcome | `analysis_jobs.status` |
|---|---|
| All NOTAMs analysed (including after retry) | `finished` |
| Retry completes but some NOTAMs still missing | `partial_finish` |
| Retry in progress | `retrying` |
| Unrecoverable error (API failure, unknown NOTAM id, etc.) | `failed` (+ `error_message`) |

Successfully analysed NOTAMs are persisted even when the final status is `partial_finish`. Rows for NOTAMs that never analysed successfully remain in `analysed_notams` with `category` and `summary` as `null` and `did_error` set to `true`.

## Tests

```bash
pytest tests/unit/test_notam_analyzer.py \
       tests/unit/test_analysis_task.py \
       tests/unit/test_pipeline_stage_metadata.py \
       tests/integration/test_begin_analysis_endpoint.py -v
```
