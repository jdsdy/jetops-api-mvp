# Integration API test

Probe endpoint for verifying integration API key authentication.

## Request

`GET /v1/test`

### Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <integration_api_key>` — SHA-256 hashed and validated against `api_keys` |

## Authentication

All `/v1/*` integration routes (excluding `/v1/app/*`) require a valid integration API key in the `Authorization` header.

Validation flow:

1. Extract Bearer token from `Authorization`
2. Hash the token with SHA-256
3. Lookup `key_hash` in `api_keys` (joined with `api_clients`)
4. Reject with `401 Unauthorized` if:
   - Key not found
   - `api_keys.is_active = false`
   - `api_keys.revoked_at` is set
   - `api_keys.expires_at` is set and in the past
   - `api_clients.is_active = false` (account suspended)
5. On success, `api_client_id` is attached to the request context and `api_keys.last_used_at` is updated asynchronously

Integration keys are issued per `api_clients` record and stored as SHA-256 hashes. Raw keys are never persisted.

Example key format: `jops_dev_sk_<urlsafe-token>`

## Response

### `200 OK`

```json
{
  "status": "ok"
}
```

### `401 Unauthorized`

```json
{
  "detail": "Unauthorized"
}
```

## Example

```bash
curl -X GET "https://api.example.com/v1/test" \
  -H "Authorization: Bearer jops_dev_sk_elq8GPD4KwhqVDr_C0GulNPi2aeyAralk_2rgqkTTN4"
```

## Related code

| File | Role |
|---|---|
| [`app/api/integration_dependencies.py`](../../app/api/integration_dependencies.py) | Bearer extraction, hashing, validation, request context |
| [`app/repositories/api_key_repository.py`](../../app/repositories/api_key_repository.py) | `api_keys` lookup and `last_used_at` update |
| [`app/api/v1/integration/router.py`](../../app/api/v1/integration/router.py) | Integration router with auth dependency |
