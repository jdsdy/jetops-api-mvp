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

- [POST /v1/jobs — Create analysis job](documentation/endpoints/v1-jobs-create.md)

Service docs:

- [Flight data extraction](documentation/services/flight-extraction.md)
- [NOTAM extraction](documentation/services/notam-extraction.md)

## Tests

```bash
pytest tests/ -v
```
