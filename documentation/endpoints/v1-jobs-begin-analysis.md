# Begin analysis

Starts NOTAM LLM analysis for a confirmed job. Validates the request, ensures flight context is loadable, sets `processing_analysis`, and returns immediately while analysis runs in the background.

See also: [NOTAM analysis](../services/notam-analysis.md) and [Analysis context](../services/analysis-context.md).

## Request

`POST /v1/app/jobs/analysis`

### Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <supabase_jwt>` |
| `x-api-key` | Yes | Must match the server `API_KEY` environment variable |
| `Content-Type` | Yes | `application/json` |

### Body

```json
{
  "organisation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "flight_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "flight_plan_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "job_id": "dddddddd-dddd-dddd-dddd-dddddddddddd"
}
```

| Field | Type | Description |
|---|---|---|
| `organisation_id` | UUID | Organisation that owns the job |
| `flight_id` | UUID | Flight linked to the job's flight plan |
| `flight_plan_id` | UUID | Flight plan the job was created for |
| `job_id` | UUID | Existing `analysis_jobs.id` |

All body fields must match the stored job record.

## Preconditions

- Job must exist.
- Job `status` must be `awaiting_confirmation` (extraction completed successfully).

## Response

`200 OK`

```json
{
  "response_begun": true
}
```

Analysis results are not returned in the HTTP response. Clients should subscribe to job status via Supabase Realtime.

## Background behaviour

After the response is sent, `run_analysis_task` runs:

1. Build flight context and log `build_context_object` stage.
2. Fetch all `raw_notams`, batch into groups of 10, call Claude concurrently.
3. If any NOTAM IDs are missing from batch responses, insert completed rows plus placeholder rows (`category`/`summary` `null`) for missing NOTAMs, set status to `retrying`, and re-analyse only those NOTAMs in batches of 5. Update placeholder rows when retry succeeds.
4. Persist any remaining rows (no-retry path) to `analysed_notams` and log `notam_analysis` stage.
5. Set job status to `finished` (all NOTAMs analysed), `partial_finish` (some still missing after retry), or `failed` on error.

## Side effects

| Before | After (sync) | After (background success) |
|---|---|---|
| `awaiting_confirmation` | `processing_analysis` | `finished` or `partial_finish` |

During retry of missing NOTAMs the status is briefly `retrying`.

## Errors

| Status | Condition |
|---|---|
| `400` | Job exists but status is not `awaiting_confirmation`, or body fields do not match the job |
| `404` | Job not found |
| `401` | Missing or invalid auth |
| `429` | Per-user rate limit exceeded (1 request per 2 minutes) |
| `422` | Invalid or incomplete request body |

## Tests

```bash
pytest tests/integration/test_begin_analysis_endpoint.py \
       tests/unit/test_analysis_service.py \
       tests/unit/test_analysis_task.py \
       tests/unit/test_notam_analyzer.py -v
```
