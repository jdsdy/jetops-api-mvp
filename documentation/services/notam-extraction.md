# NOTAM extraction

Rule-based extraction of individual NOTAMs from ForeFlight and NAIPS briefing PDFs. Each NOTAM is parsed into the ICAO field structure and written to `raw_notams`.

See also: [Flight data extraction](flight-extraction.md) and [POST /v1/jobs](../endpoints/v1-jobs-create.md) — NOTAM extraction runs in the same background task, after flight data is persisted.

## Extracted fields

Each NOTAM maps to one `raw_notams` row. Fields that are absent are stored as `null`.

| Field | Meaning | ForeFlight | NAIPS |
|---|---|---|---|
| `notam_id` | Full identifier line (incl. `NOTAMR`/`REPLACE` references) | ID line | ID line |
| `title` | NOTAM heading | line above the ID (or condensed section word) | always null |
| `q` | Qualifier line | `Q)` tag | always null |
| `a` | Location indicator | `A)` tag | group header ICAO (last bracket) |
| `b` | Effective from (UTC) | `B)` tag | `FROM MM DDHHmm`, year from header |
| `c` | Effective to (UTC) | `C)` tag | `TO MM DDHHmm` / `PERM` |
| `d` | Schedule | `D)` tag | all lines after `FROM … TO …` until the next NOTAM ID or group header |
| `e` | NOTAM text | `E)` tag (multi-line) | body lines (multi-line) |
| `f` | Lower limit | `F)` tag | `SFC TO ...` lower value |
| `g` | Upper limit | `G)` tag | `... TO <limit>` upper value |

Multi-line `e` (and `d`) values join source lines with a `{\n} ` marker (no leading space before the delimiter) so the original line structure can be re-rendered to the user.

## Format quirks handled

- **Page breaks injected mid-NOTAM** are stripped (`NOTAMs:Page n of m`, NAIPS `Page n of m` and the AirServices URL footer).
- **ForeFlight condensed (US-style) NOTAMs** (e.g. `HNL 04/227 ... 2604180306-2604302359EST`) share a single-word section title (`NAVIGATION`, `AIRSPACE`, `ROUTE`) and carry their dates/altitudes inline.
- **Structural separators** — terminate the preceding NOTAM's text and are not parsed as field content:
  - `FIR ____`, `Departure`/`Destination`, and `[descriptor]` lines
  - `Alternate#...` lines (e.g. `Alternate1 YBLN-Busselton`)
  - Enroute section markers ending in `NOTAMs` (e.g. `USEnrouteNavigationNOTAMs`)
  - Single-word alphabetic section headers immediately before a condensed US-style NOTAM (e.g. `NAVIGATION` before `GUM 04/059 ...`)
  - Short alphabetic E-field continuations (e.g. `AVBL`) are kept when they are not followed by a condensed NOTAM
- **Brackets inside `e`** (e.g. `(CHUO-KU IN TOKYO)`) are not mistaken for field tags; tags are only honoured in canonical `Q A B C D E F G` order.
- **NAIPS abbreviated dates** (`MM DDHHmm`) are expanded to `YYMMDDHHmm` using the two-digit year from the document header line.
- **NAIPS `d` schedule** — every line after `FROM … TO …` is treated as schedule text (including free-form values like `MON-SAT 1945-1300` or `SAT, SUN, PUBLIC HOLIDAY 2200-0830`) until the next NOTAM ID or location group header (e.g. `SYDNEY (YSSY)`).
- Some source `e` values legitimately cut off mid-word (e.g. `... (ERSA`); these are preserved verbatim.

## Module layout

| Module | Role |
|---|---|
| [`app/services/notam_parser.py`](../../app/services/notam_parser.py) | Shared helpers, ForeFlight + NAIPS NOTAM parsers, `extract_notams` |
| [`app/repositories/notam_repository.py`](../../app/repositories/notam_repository.py) | Bulk insert into `raw_notams` |

## Tests

NOTAM fixtures are a hand-curated **subset**: tests assert every fixture NOTAM is present in the parser output (matched by `notam_id`), with `{\n}`/whitespace normalized for comparison.

Fixtures: [`tests/fixtures/notam_expected.json`](../../tests/fixtures/notam_expected.json)

```bash
pytest tests/unit/test_notam_parser.py \
       tests/integration/test_notam_extraction_pdfs.py -v
```
