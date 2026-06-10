# Flight data extraction

Rule-based extraction of flight plan fields from ForeFlight and NAIPS briefing PDFs.

See also: [POST /v1/jobs](../endpoints/v1-jobs-create.md) for how extraction is triggered after job creation.

## Extracted fields

| Field | ForeFlight | NAIPS | DB target |
|---|---|---|---|
| `departure_icao` | Header + ETD/ETA line | `STAGE` line | `flights.departure_icao` |
| `arrival_icao` | Header + ETD/ETA line | `STAGE` line | `flights.arrival_icao` |
| `planned_dept_time` | Zulu time + header date | always null | `flight_plans.planned_dept_time` |
| `planned_arr_time` | Zulu time + header date | always null | `flight_plans.planned_arr_time` |
| `route` | `Route Report` section | Wind cross-section waypoints | `flight_plans.route` |
| `cruise_level` | `@ FLnnn` on cruise line | `STAGE` line | `flight_plans.cruise_level` |
| `alt_icao` | `PRIMARY ALTERNATE` page | `ALTN` line | `flight_plans.alt_icao` |
| `source_app` | `foreflight` | `naips` | `flight_plans.source_app` |

## Format detection

- **NAIPS:** document starts with `Specific PreFlight Information Bulletin Number:`
- **ForeFlight:** all other briefing PDFs in the current set

## Module layout

| Module | Role |
|---|---|
| [`app/services/pdf_extractor.py`](../../app/services/pdf_extractor.py) | pdfplumber text extraction (incl. two-column landscape pages) |
| [`app/services/flight_parser.py`](../../app/services/flight_parser.py) | Format detection, shared helpers, ForeFlight + NAIPS parsers, `parse_flight_data` |
| [`app/services/extraction_task.py`](../../app/services/extraction_task.py) | Background task: download → parse → persist → `awaiting_confirmation` |
| [`app/services/pipeline_stage.py`](../../app/services/pipeline_stage.py) | Timed stage logs to `pipeline_stage_logs` |

## Pipeline stage logs

Each background extraction run writes up to three rows to `pipeline_stage_logs` (one per completed stage):

| `stage_name` | Metadata |
|---|---|
| `pdf_extraction` | `page_count`, `file_size_bytes`, `download_url` (request `storage_path`) |
| `flight_data_parse` | `fields_extracted`, `fields_missing` (direct `FlightData` field names), `source_type` |
| `notam_parse` | `notams_found`, `aerodromes_found`, `multiformat_notams`, `parse_failures`, `source_type` |

Stages that complete before an error are logged; stages not reached are omitted. A failed log write does not fail the extraction pipeline.

## Job status after extraction

| Outcome | `analysis_jobs.status` |
|---|---|
| Extraction + DB write succeed | `awaiting_confirmation` |
| Analysis start (`POST /v1/jobs/analysis`, sync) | `processing_analysis` |
| NOTAM analysis completes | `finished` |
| Any extraction/persistence error | `failed` (+ `error_message`) |

## Tests

Fixtures: [`tests/fixtures/flight_data_expected.json`](../../tests/fixtures/flight_data_expected.json)

Example PDFs: [`ExampleFlightPlans/`](../../ExampleFlightPlans/)

```bash
pytest tests/unit/test_pdf_extractor.py \
       tests/unit/test_flight_parser.py \
       tests/unit/test_extraction_task.py \
       tests/unit/test_pipeline_stage_logger.py \
       tests/unit/test_pipeline_stage_metadata.py \
       tests/integration/test_flight_extraction_pdfs.py -v
```
