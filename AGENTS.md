## Learned User Preferences

- Store local secrets in `.env.local`; app config loads `.env` then `.env.local` (local overrides).
- Use TDD with pytest when implementing API features.
- Do not edit attached Cursor plan files when implementing from them.
- Run a `/simplify` pass on newly written code to remove dead code and tighten layering without changing behavior.
- Co-locate related domain logic in one service file per extraction domain (flight, NOTAM, pipeline stage) instead of splitting format detection, utils, and per-format parsers across files.
- Use `# --- Section name ---` comment headers inside large service files for visual separation.
- Match test files to consolidated services (one test module per service); unit tests for internal parsers call private `_parse_*` helpers, public orchestrators in integration tests.

## Learned Workspace Facts

- FastAPI NOTAM analysis API (`jetops-api-mvp`); Python ≥3.11; venv at `.venv/`; install with `pip install -e ".[dev]"`.
- Package layout: `app/` (`api/`, `core/`, `schemas/`, `services/`, `repositories/`), `tests/` (unit + integration), endpoint docs in `documentation/endpoints/`.
- Keep Pydantic schemas in `app/schemas/`; keep shared thin repositories in `app/repositories/` — colocate a repository in the service module only when used exclusively by that service (e.g. `pipeline_stage.py`).
- Supabase env vars (no anon key): `API_KEY`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
- Single Supabase secret-key client handles auth (`get_user`), storage download, and `analysis_jobs` writes.
- `POST /v1/jobs`: dual auth (`x-api-key` + Bearer JWT); verifies PDF in `flight_plan_pdfs` (no copy); early `analysis_jobs` insert with `processing_extraction`; background extraction persists flight data + NOTAMs; `mark_failed` on post-insert errors; returns `{ "id" }` only — clients get status via Supabase Realtime.
- Extraction services: `flight_parser.py` (ForeFlight/NAIPS flight data), `notam_parser.py` (NOTAMs; imports `detect_plan_format` from flight_parser), `pipeline_stage.py` (logger + colocated log repository), `pdf_extractor.py`, `extraction_task.py` orchestrates background pipeline.
- `pipeline_stage_logs` records timed stages (`pdf_extraction`, `flight_data_parse`, `notam_parse`) via `PipelineStageLogger`; log write failures are swallowed so extraction is not blocked.
- `storage_path` must start with `{organisation_id}/{flight_id}/{flight_plan_id}/` and end with `.pdf`.
- PDF verification lives in `JobRepository.verify_flight_plan_pdf()`; auth failures use shared `_raise_unauthorized()` helper.
- `ExampleFlightPlans/` holds sample briefing PDFs; `test.py` extracts full text with pdfplumber (two-column handling for landscape pages).
