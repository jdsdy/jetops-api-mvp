# NOTAM heuristic classification

Analysis-time category assignment that skips Sonnet categorization for high-confidence specialist topics.

See also: [NOTAM LLM analysis](notam-analysis.md) and [NOTAM topic classification](notam-topic-classification.md).

## Eligibility

A NOTAM is a heuristic category candidate when **both** conditions hold:

1. `raw_notams.topic` is one of: `OBSTACLE`, `GROUND_MOVEMENT`, `LIGHTING`, `COMMS`, `NAVAID`
2. `raw_notams.topic_confidence` is **strictly greater than** `NOTAM_HEURISTIC_TOPIC_CONFIDENCE_MIN` (default `40`, so `41+` qualifies)

`topic_confidence` is set during extraction topic classification and read at analysis time from `raw_notams` — no re-classification occurs in the analysis pipeline.

## Assignment

Eligible NOTAMs receive **category 3** without a Sonnet categorization call. They still go through the Haiku summarization leg like all other NOTAMs.

| Setting | Default |
|---|---|
| `NOTAM_HEURISTIC_TOPIC_CONFIDENCE_MIN` | `40` (eligibility uses `> 40`) |

## Module layout

| Module | Role |
|---|---|
| [`app/services/analysis/notam_heuristic_category.py`](../../app/services/analysis/notam_heuristic_category.py) | Eligibility check and category assignment |
| [`app/schemas/notam_analysis.py`](../../app/schemas/notam_analysis.py) | `topic_confidence` on `AnalysisNotamRow` |
| [`app/repositories/analysis_context_repository.py`](../../app/repositories/analysis_context_repository.py) | Fetches `topic_confidence` with NOTAM rows |

## Tests

```bash
pytest tests/unit/test_notam_heuristic_category.py \
       tests/unit/test_notam_analyzer.py \
       tests/unit/test_analysis_task.py -v
```
