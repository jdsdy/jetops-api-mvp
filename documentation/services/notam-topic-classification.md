# NOTAM topic classification

Heuristic topic assignment for parsed NOTAMs. Runs during extraction (after `notam_parse`, before `awaiting_confirmation`).

Flow: identify topics in memory → merge with parsed NOTAM fields → single bulk insert to `raw_notams` (including `topic` and `topic_confidence`).

See also: [NOTAM extraction](notam-extraction.md) and [NOTAM LLM analysis](notam-analysis.md).

## Classification paths

| NOTAM source | Condition | Method |
|---|---|---|
| ForeFlight standard | `q` field populated | Triple-channel vote (Q, E-only, Title-only) |
| ForeFlight condensed, NAIPS, OzRunways | `q` is null | E-line (and title) heuristic scoring |
| Any | no confident match | `MISC` |

## ForeFlight triple-channel vote

When `q` is present, three independent channels classify the NOTAM:

| Channel | Input | Method |
|---|---|---|
| Q | `notam.q` | Q-code subject lookup |
| E | `notam.e` only | E-line heuristic scoring (`title=None`) |
| Title | `notam.title` only | Title heuristic scoring via [`notam_title_signals.json`](../../app/schemas/notam_title_signals.json) |

`resolve_foreflight_vote` applies the voting table below. Confidence is the **rule score**, not the underlying E-line signal sum.

| Condition | Confidence | Final topic |
|---|---|---|
| Q = E = Title (same non-MISC) | 100 | that topic |
| Q = Title, E = MISC | 80 | Q/Title topic |
| Q = Title, E disagrees | 40 | Q/Title topic |
| E = Title, Q disagrees | 70 | E/Title topic |
| Q = E, Title disagrees | 50 | Q/E topic |
| Q identifies, E = Title = MISC | 50 | Q topic |
| E identifies, Q = Title = MISC | 30 | E topic |
| Title identifies, Q = E = MISC | 30 | **MISC** (title alone never wins) |
| all MISC | 0 | MISC |
| all disagree (3 distinct non-MISC) | 0 | MISC |

## Q-code lookup

Q line example: `YMMM/QMDCH/IV/NBO/A/000/999/3357S15111E005`

1. Take the segment after the first `/` → `QMDCH`
2. Take characters at index 1–2 → `MD`
3. Match against [`app/schemas/notam_identifier_codes.json`](../../app/schemas/notam_identifier_codes.json)

| Outcome | `topic` | `topic_confidence` |
|---|---|---|
| Match | specialist topic | `100` |
| No match | `MISC` | `0` |

## E-line heuristic scoring

Signals live in [`app/schemas/notam_type_signals.json`](../../app/schemas/notam_type_signals.json), grouped per topic as `strong`, `moderate`, and `weak`.

| Setting | Default |
|---|---|
| `NOTAM_TOPIC_STRONG_SCORE` | 15 |
| `NOTAM_TOPIC_MODERATE_SCORE` | 8 |
| `NOTAM_TOPIC_WEAK_SCORE` | 3 |
| `NOTAM_TOPIC_SCORE_CUTOFF` | 23 |

Signals must match as whole tokens/phrases (alphanumeric boundaries). `HELLO` does not match inside `HELLOWORLD`.

Resolution:

- Exactly one topic ≥ cutoff → that topic; confidence = its score
- Zero or multiple qualifying topics → `MISC`; confidence = highest topic score (useful for near-miss debugging)

## Title heuristic scoring

Title-only matching for the ForeFlight triple vote uses [`app/schemas/notam_title_signals.json`](../../app/schemas/notam_title_signals.json). Each topic has `strong` and `moderate` signal lists only (no `weak`).

Qualification per topic:

- **`exact`** — whole title must match an entry exactly (case-insensitive, trimmed). Checked first; when exactly one topic exact-matches, strong/moderate rules are skipped
- **One strong** signal match → topic qualifies
- **No strong** match → **two or more moderate** signal matches required to qualify
- Otherwise → topic does not qualify

Exactly one qualifying topic wins; zero or multiple qualifying topics → `MISC`. Confidence uses `NOTAM_TOPIC_STRONG_SCORE` for a strong match, or `moderate_count × NOTAM_TOPIC_MODERATE_SCORE` when qualifying via moderates only. A lone moderate match returns `MISC` with a single moderate score for near-miss debugging.

Condensed / NAIPS paths without a Q line still combine E-line + title text against `notam_type_signals.json`.

## Specialist analysis prompts

The general (MISC) system prompt lives in [`app/services/analysis/notam_prompts/generic.py`](../../app/services/analysis/notam_prompts/generic.py) as `GENERIC`. Specialist topic prompts live alongside it under `app/services/analysis/notam_prompts/` and are registered in [`app/services/analysis/notam_topic_prompts.py`](../../app/services/analysis/notam_topic_prompts.py).

## Module layout

| Module | Role |
|---|---|
| [`app/services/extraction/notam_topic_classifier.py`](../../app/services/extraction/notam_topic_classifier.py) | Q-code, E-line, and ForeFlight triple vote |
| [`app/repositories/notam_repository.py`](../../app/repositories/notam_repository.py) | Bulk insert classified NOTAM rows |
| [`app/services/extraction/extraction_task.py`](../../app/services/extraction/extraction_task.py) | `notam_topic_classification` pipeline stage |

## Pipeline stage log

| `stage_name` | Metadata |
|---|---|
| `notam_topic_classification` | `notams_classified`, `topic_counts`, `misc_count`, `classification_errors` |

## Tests

```bash
pytest tests/unit/test_notam_topic_classifier.py \
       tests/unit/test_extraction_task.py \
       tests/unit/test_pipeline_stage_metadata.py -v
```
