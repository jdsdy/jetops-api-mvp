# Create analysis job

Creates a new NOTAM analysis job for a flight plan PDF that already exists in Supabase Storage.

## Request

`POST /v1/app/jobs`

### Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <supabase_jwt>` — validated via Supabase Auth |
| `x-api-key` | Yes | Must match the server `API_KEY` environment variable |
| `Content-Type` | Yes | `application/json` |

### Body

```json
{
  "organisation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "flight_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "flight_plan_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "storage_path": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/cccccccc-cccc-cccc-cccc-cccccccccccc/briefing.pdf"
}
```

| Field | Type | Description |
|---|---|---|
| `organisation_id` | UUID | Organisation that owns the flight plan |
| `flight_id` | UUID | Flight the plan belongs to |
| `flight_plan_id` | UUID | Flight plan record (FK to `flight_plans.id`) |
| `storage_path` | string | Path to the PDF in the `flight_plan_pdfs` bucket. Must start with `{organisation_id}/{flight_id}/{flight_plan_id}/` and end with a `.pdf` filename |

## Behaviour

1. Validates `x-api-key` and Bearer JWT.
2. Validates `storage_path` against the UUIDs in the request body.
3. Inserts an `analysis_jobs` row with `status: "processing_extraction"` and `triggered_by` set to the authenticated user.
4. Downloads the PDF from the `flight_plan_pdfs` bucket to verify it exists and is accessible.
5. Returns the job ID immediately (`201`).
6. Runs flight data extraction in a background task:
   - Parses the PDF (ForeFlight or NAIPS)
   - Writes extracted fields to `flights` and `flight_plans`
   - On success, sets `analysis_jobs.status` to `awaiting_confirmation`
   - On failure, sets `status` to `failed` with `error_message`

Status updates after the HTTP response are delivered via Supabase Realtime (not in the create response).

If PDF verification fails **before** the response is returned, or if background extraction fails, the job is updated to:

- `status`: `"failed"`
- `error_message`: message from the caught error

The HTTP response still includes `{ "id": "<uuid>" }` so the client can subscribe to Realtime for that job.

## Responses

### 201 Created

Job created and PDF verified.

```json
{
  "id": "dddddddd-dddd-dddd-dddd-dddddddddddd"
}
```

### 400 Bad Request

`storage_path` does not match the organisation, flight, and flight plan IDs, or does not end with `.pdf`.

### 401 Unauthorized

Missing or invalid `x-api-key`, or missing/invalid Bearer JWT.

### 429 Too Many Requests

Per-user rate limit exceeded (1 request per 10 seconds). Response includes a `Retry-After` header (seconds until the next allowed request).

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

### 404 Not Found

PDF not found in storage after the job row was created. Response body:

```json
{
  "id": "dddddddd-dddd-dddd-dddd-dddddddddddd"
}
```

Check Realtime for `status: "failed"` and `error_message`.

### 422 Unprocessable Entity

Request body failed validation (e.g. missing or malformed UUID fields).

### 500 Internal Server Error

Unexpected failure after the job row was created. Response body:

```json
{
  "id": "dddddddd-dddd-dddd-dddd-dddddddddddd"
}
```

## Environment variables

| Variable | Description |
|---|---|
| `API_KEY` | Expected value for the `x-api-key` header |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` | Supabase secret key for auth validation, storage access, and database writes |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL for rate limiting |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST token for rate limiting |

Load order: `.env`, then `.env.local` (local overrides).

## Example

```bash
curl -X POST "https://api.example.com/v1/app/jobs" \
  -H "Authorization: Bearer eyJhbG..." \
  -H "x-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "organisation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "flight_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "flight_plan_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "storage_path": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/cccccccc-cccc-cccc-cccc-cccccccccccc/briefing.pdf"
  }'
```
