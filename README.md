# jetops-api-mvp

API for processing NOTAM analysis from flight plan PDFs.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set API_KEY, SUPABASE_URL, SUPABASE_SECRET_KEY in .env.local
fastapi dev
```

## API documentation

Endpoint reference lives in [`documentation/endpoints/`](documentation/endpoints/):

- [POST /v1/app/jobs — Create analysis job](documentation/endpoints/v1-jobs-create.md)
- [GET /v1/test — Integration API auth probe](documentation/endpoints/v1-integration-test.md)
- [POST /v1/analysis — Submit integration analysis](documentation/endpoints/v1-integration-analysis-submit.md)

Service docs:

- [Flight data extraction](documentation/services/flight-extraction.md)
- [NOTAM extraction](documentation/services/notam-extraction.md)

## Tests

```bash
pytest tests/ -v
```
