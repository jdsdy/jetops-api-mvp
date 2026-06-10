# NOTAM LLM analysis

Batched Claude analysis of parsed NOTAMs for a confirmed flight plan job.

See also: [Begin analysis](../endpoints/v1-jobs-begin-analysis.md) and [Analysis context](analysis-context.md).

## Flow

1. **Sync** (`POST /v1/jobs/analysis`): validate job, build flight context (no NOTAMs), set `processing_analysis`, return `{ "response_begun": true }`.
2. **Background** (`run_analysis_task`): build flight context → fetch `raw_notams` → batch (10 per request) → concurrent Claude calls → persist `analysed_notams` → set `finished`.

## Module layout

| Module | Role |
|---|---|
| [`app/services/analysis_service.py`](../../app/services/analysis_service.py) | Sync validation and status transition |
| [`app/services/analysis_task.py`](../../app/services/analysis_task.py) | Background pipeline orchestration |
| [`app/services/notam_analyzer.py`](../../app/services/notam_analyzer.py) | Batching, prompt assembly, Anthropic `messages.parse` |
| [`app/repositories/analysed_notam_repository.py`](../../app/repositories/analysed_notam_repository.py) | Bulk insert into `analysed_notams` |

## Batching

NOTAMs are chunked into groups of `NOTAM_ANALYSIS_BATCH_SIZE` (default 10). Each batch payload repeats the same `FlightContext` with a slice of NOTAM rows:

```json
{ "flight": { ... }, "notams": [ ... ] }
```

Batches run concurrently via `ThreadPoolExecutor` with `NOTAM_ANALYSIS_MAX_CONCURRENCY` workers (default 4).

## Claude settings

| Setting | Default |
|---|---|
| `NOTAM_ANALYSIS_MODEL` | `claude-sonnet-4-6` |
| `NOTAM_ANALYSIS_MAX_TOKENS` | `12000` |
| `NOTAM_ANALYSIS_INPUT_COST_PER_M` | `3.0` USD |
| `NOTAM_ANALYSIS_OUTPUT_COST_PER_M` | `15.0` USD |

Structured output uses `client.messages.parse()` with `AnalysisOutput` (list of `NotamResult`: `notam_id`, `category`, `summary`). Thinking/reasoning is disabled.

## Pipeline stage logs

| `stage_name` | Metadata |
|---|---|
| `build_context_object` | `departure_airfield_full_data_found`, `arrival_airfield_full_data_found`, `aircraft_full_data_found` |
| `notam_analysis` | `batches`, `notams_analysed`, `model`, `batch_sizes`, `token_limit_hit`, `slowest_batch_ms`, `input_tokens`, `output_tokens`, `est_cost` |

**Full data found** rules:

- Airfield: `iso_country` and `length_ft` both non-null (runway row matched).
- Aircraft: `icao_wtc` non-null (linked `aircraft_reference` row).

## Persistence

Results are written to `analysed_notams`:

| Column | Source |
|---|---|
| `anaysis_job_id` | Job UUID (DB column name as stored) |
| `flight_plan_id` | Request flight plan UUID |
| `notam_id` | `raw_notams.id` (bigint FK) |
| `category` | LLM `NotamResult.category` |
| `summary` | LLM `NotamResult.summary` |
| `was_cached` | `null` |

LLM `notam_id` strings (ICAO format) are mapped to `raw_notams.id` before insert. Unknown IDs fail the job.

## Job status

| Outcome | `analysis_jobs.status` |
|---|---|
| Analysis completes | `finished` |
| Any analysis error | `failed` (+ `error_message`) |

## Tests

```bash
pytest tests/unit/test_notam_analyzer.py \
       tests/unit/test_analysis_task.py \
       tests/unit/test_pipeline_stage_metadata.py \
       tests/integration/test_begin_analysis_endpoint.py -v
```
