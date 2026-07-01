# Flight data extraction

Rule-based extraction of flight plan fields from ForeFlight, NAIPS, and OzRunways briefing PDFs.

See also: [POST /v1/app/jobs](../endpoints/v1-jobs-create.md) for how extraction is triggered after job creation.

## Extracted fields

| Field | ForeFlight | NAIPS | OzRunways | DB target |
|---|---|---|---|
| `departure_icao` | Header line (`ABCD — EFGH`) | `STAGE` line | first `ABCD-EFGH` line | `flights.departure_icao` |
| `arrival_icao` | Header line (`ABCD — EFGH`) | `STAGE` line | first `ABCD-EFGH` line | `flights.arrival_icao` |
| `planned_dept_time` | Zulu time + header date | always null | `Total: … ETD: DD Mon HHMM UTC` | `flight_plans.planned_dept_time` |
| `planned_arr_time` | Zulu time + header date | always null | ETD + `H:MM` flight duration | `flight_plans.planned_arr_time` |
| `route` | Overflight Report (`Route` … `COUNTRY`), else `Route Report` | Wind cross-section waypoints | always null | `flight_plans.route` |
| `cruise_level` | `@ FLnnn` on cruise line | `STAGE` line | always null | `flight_plans.cruise_level` |
| `alt_icao` | `PRIMARY ALTERNATE` or `ALTERNATE #n` line | `ALTN` line | always null | `flight_plans.alt_icao` |
| `source_app` | `foreflight` | `naips` | `ozrunways` | `flight_plans.source_app` |

## Format detection

- **NAIPS:** document starts with `Specific PreFlight Information Bulletin Number:`
- **OzRunways:** first `ABCD-EFGH` line **and** first `Total: … NM, H:MM ETD: DD Mon HHMM UTC` line
- **ForeFlight:** all other briefing PDFs in the current set

ForeFlight briefings appear in two layouts:

- **Legacy (custom) layout:** `Recall # DEP ETD DEST ETA` line with ICAO-coded times; route from `Route Report` when no Overflight Report is present.
- **Standard layout:** `ETE Distance Avg Wind ETD ETA …` block with zulu times on the following line; route from `Overflight Report` (`Route` through `COUNTRY`); alternate from `ALTERNATE #n ICAO`.

Both layouts share the header line: `ABCD — EFGH (Mon DD, YYYY) in …`.

## Module layout

| Module | Role |
|---|---|
| [`app/services/extraction/pdf_extractor.py`](../../app/services/extraction/pdf_extractor.py) | pdfplumber text extraction (incl. two-column landscape pages) |
| [`app/services/extraction/flight_parser.py`](../../app/services/extraction/flight_parser.py) | Format detection, shared helpers, ForeFlight + NAIPS + OzRunways parsers, `parse_flight_data` |
| [`app/services/extraction/extraction_task.py`](../../app/services/extraction/extraction_task.py) | Background task: download → parse → persist → `awaiting_confirmation` |
| [`app/services/pipeline/pipeline_stage.py`](../../app/services/pipeline/pipeline_stage.py) | Timed stage logs to `pipeline_stage_logs` |

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
| Analysis start (`POST /v1/app/jobs/analysis`, sync) | `processing_analysis` |
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
