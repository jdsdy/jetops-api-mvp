# NOTAM topic classification

Heuristic topic assignment for parsed NOTAMs. Runs during extraction (after `notam_parse`, before `awaiting_confirmation`) and writes `raw_notams.topic` and `raw_notams.topic_confidence`.

See also: [NOTAM extraction](notam-extraction.md) and [NOTAM LLM analysis](notam-analysis.md).

## Classification paths

| NOTAM source | Condition | Method |
|---|---|---|
| ForeFlight standard | `q` field populated | Q-code subject lookup |
| ForeFlight condensed, NAIPS, OzRunways | `q` is null | E-line (and title) heuristic scoring |
| Any | no confident match | `MISC` |

ForeFlight NOTAMs with a Q line do **not** fall back to E-line heuristics when the Q code is unmapped.

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
| `NOTAM_TOPIC_STRONG_SCORE` | 10 |
| `NOTAM_TOPIC_MODERATE_SCORE` | 5 |
| `NOTAM_TOPIC_WEAK_SCORE` | 2 |
| `NOTAM_TOPIC_SCORE_CUTOFF` | 15 |

Signals must match as whole tokens/phrases (alphanumeric boundaries). `HELLO` does not match inside `HELLOWORLD`.

Resolution:

- Exactly one topic ≥ cutoff → that topic; confidence = its score
- Zero or multiple qualifying topics → `MISC`; confidence = highest topic score (useful for near-miss debugging)

## Specialist analysis prompts

The general (MISC) system prompt lives unchanged in [`app/services/notam_topic_prompts.py`](../../app/services/notam_topic_prompts.py) as `PLACEHOLDER_SYSTEM_PROMPT`. Add specialist topic prompts to the same file before running analysis on non-`MISC` topics.

## Module layout

| Module | Role |
|---|---|
| [`app/services/notam_topic_classifier.py`](../../app/services/notam_topic_classifier.py) | Q-code and E-line classification |
| [`app/repositories/notam_repository.py`](../../app/repositories/notam_repository.py) | Persist `topic` and `topic_confidence` |
| [`app/services/extraction_task.py`](../../app/services/extraction_task.py) | `notam_topic_classification` pipeline stage |

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
