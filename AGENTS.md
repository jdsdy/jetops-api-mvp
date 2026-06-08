## Learned User Preferences

- Store local secrets in `.env.local`; app config loads `.env` then `.env.local` (local overrides).
- Use TDD with pytest when implementing API features.
- Do not edit attached Cursor plan files when implementing from them.
- Run a `/simplify` pass on newly written code to remove dead code and tighten layering without changing behavior.

## Learned Workspace Facts

- FastAPI NOTAM analysis API (`jetops-api-mvp`); Python ≥3.11; venv at `.venv/`; install with `pip install -e ".[dev]"`.
- Package layout: `app/` (`api/`, `core/`, `schemas/`, `services/`, `repositories/`), `tests/` (unit + integration), endpoint docs in `documentation/endpoints/`.
- Supabase env vars (no anon key): `API_KEY`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
- Single Supabase secret-key client handles auth (`get_user`), storage download, and `analysis_jobs` writes.
- `POST /v1/jobs`: dual auth (`x-api-key` + Bearer JWT); verifies PDF in `flight_plan_pdfs` (no copy); early `analysis_jobs` insert with `processing_extraction`; `mark_failed` on post-insert errors; returns `{ "id" }` only — clients get status via Supabase Realtime.
- `storage_path` must start with `{organisation_id}/{flight_id}/{flight_plan_id}/` and end with `.pdf`.
- PDF verification lives in `JobRepository.verify_flight_plan_pdf()`; auth failures use shared `_raise_unauthorized()` helper.
- `ExampleFlightPlans/` holds sample briefing PDFs; `test.py` extracts full text with pdfplumber (two-column handling for landscape pages).
- `overview.txt` describes the broader product (PDF extraction, NOTAM parsing, job pipeline) beyond the current Step 1 endpoint.
