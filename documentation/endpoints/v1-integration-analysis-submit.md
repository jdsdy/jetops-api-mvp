# Submit integration analysis

Submits flight and NOTAM data for NOTAM analysis via the integration API.

Creates an `analysis_jobs` row with status `accepted`, then runs the full analysis pipeline in the background (topic identification, heuristic + LLM classification, retry). Results are persisted to `raw_notams` and `analysed_notams` when complete.

## Request

`POST /v1/analysis`

### Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <integration_api_key>` |
| `Content-Type` | Yes | `application/json` |

### Required fields

| Path | Description |
|---|---|
| `flight.departure_airfield.icao` | Departure ICAO |
| `flight.arrival_airfield.icao` | Arrival ICAO |
| `flight.planned_dept_time` | ISO 8601 departure time |
| `flight.planned_arr_time` | ISO 8601 arrival time |
| `flight.cruise_level` | Cruise level |
| `flight.aircraft.make` | Aircraft manufacturer |
| `flight.aircraft.model` | Aircraft model |
| `flight.aircraft.rnav_equipped` | RNAV equipped |
| `flight.aircraft.icao_wtc` | ICAO wake turbulence category |
| `flight.aircraft.weight_class` | Weight class |
| `flight.aircraft.instrument_approach_category` | Instrument approach category |
| `flight.aircraft.aircraft_design_group` | Aircraft design group |
| `notams[].id` | NOTAM identifier |
| `notams[].a` | NOTAM A line |
| `notams[].b` | NOTAM B line |
| `notams[].c` | NOTAM C line |
| `notams[].e` | NOTAM E line |

### Limits

- Maximum **800 NOTAMs** per request.

## Status lifecycle

| Status | Meaning |
|---|---|
| `accepted` | Job created; background task not yet started |
| `processing` | Analysis running (see `stage`) |
| `complete` | Results available in poll response |
| `failed` | Pipeline error (see `error`) |

Processing stages (`stage` field): `topic_identification` → `classification` → `retry` (if needed) → `complete`.

## Responses

### `201 Created`

```json
{
  "job_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "status": "accepted",
  "poll_url": "/v1/analysis/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "started_at": "2025-01-15T10:30:00Z"
}
```

### POST errors (no job created)

Structured error envelope:

```json
{
  "error": {
    "code": "invalid_request_format",
    "message": "flight.cruise_level: Field required"
  }
}
```

| HTTP | When |
|---|---|
| `400` | Malformed JSON or validation failure |
| `401` | Missing or invalid API key |
| `413` | More than 800 NOTAMs |

Error codes: `invalid_request_format`, `unsupported_icao`, `internal_error`, `analysis_error`, `timeout`.

## Poll job status

`GET /v1/analysis/{job_id}` — rate limited to **10 req/s** per API key.

All poll responses include base fields: `job_id`, `status`, `started_at`.

### Accepted

```json
{
  "job_id": "...",
  "status": "accepted",
  "started_at": "2025-01-15T10:30:00Z"
}
```

### Processing

```json
{
  "job_id": "...",
  "status": "processing",
  "started_at": "2025-01-15T10:30:00Z",
  "stage": "classification"
}
```

### Complete

```json
{
  "job_id": "...",
  "status": "complete",
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:31:45Z",
  "stage": "complete",
  "result": {
    "summary": {
      "total_notams": 47,
      "priority_1": 3,
      "priority_2": 12,
      "priority_3": 32
    },
    "notams": [
      {
        "notam_id": "A1234/25",
        "category": 1,
        "summary": "some summary"
      }
    ]
  }
}
```

Results are loaded from a join between `analysed_notams` and `raw_notams` (not from in-memory state).

### Failed

Returns **200** with:

```json
{
  "job_id": "...",
  "status": "failed",
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:31:12Z",
  "error": {
    "code": "internal_error",
    "message": "..."
  }
}
```

### `404 Not Found`

Job missing or belongs to another API client.

## List analysis jobs

`GET /v1/analysis`

Returns paginated job summaries for the authenticated API client. Filters are passed as **query parameters** (standard for GET).

| Parameter | Required | Default | Description |
|---|---|---|---|
| `limit` | No | `20` | Page size (max `100`) |
| `offset` | No | `0` | Page offset |
| `status` | No | — | `accepted`, `processing`, `complete`, or `failed` |
| `from` | No | — | ISO 8601 UTC; filter `started_at` ≥ value |
| `to` | No | — | ISO 8601 UTC; filter `started_at` ≤ value |

### `200 OK`

```json
{
  "jobs": [
    {
      "job_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "status": "complete",
      "submitted_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T10:31:45Z",
      "flight": {
        "departure_icao": "YPPH",
        "arrival_icao": "YMML"
      },
      "summary": {
        "total_notams": 47,
        "category_1": 3,
        "category_2": 12,
        "category_3": 32
      }
    }
  ],
  "pagination": {
    "total": 134,
    "limit": 20,
    "offset": 0
  }
}
```

`submitted_at` maps from `analysis_jobs.started_at`. `summary` is included only for `complete` jobs (from `total_notams`, `cat1_notams`, `cat2_notams`, `cat3_notams` columns).

## Related code

| File | Role |
|---|---|
| [`app/schemas/integration_analysis.py`](../../app/schemas/integration_analysis.py) | Request/response models and enums |
| [`app/services/integration/analysis_submission.py`](../../app/services/integration/analysis_submission.py) | Validation |
| [`app/services/integration/integration_analysis_service.py`](../../app/services/integration/integration_analysis_service.py) | Job creation and polling |
| [`app/services/integration/integration_analysis_task.py`](../../app/services/integration/integration_analysis_task.py) | Background analysis pipeline |
| [`app/services/analysis/analysis_task.py`](../../app/services/analysis/analysis_task.py) | Shared in-memory analysis runner |
| [`app/api/v1/integration/endpoints/analysis.py`](../../app/api/v1/integration/endpoints/analysis.py) | Route handlers |
