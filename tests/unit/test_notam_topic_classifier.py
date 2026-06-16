import pytest

from app.schemas.notam import RawNotam
from app.schemas.notam_topic import MISC_TOPIC
from app.services.notam_topic_classifier import (
    Q_CODE_MATCH_CONFIDENCE,
    classify_by_e_heuristics,
    classify_by_q_code,
    classify_notam,
    extract_q_code_subject,
    signal_in_text,
)


def test_extract_q_code_subject_returns_two_letter_code() -> None:
    assert extract_q_code_subject("YMMM/QMDCH/IV/NBO/A/000/999/3357S15111E005") == "MD"


def test_classify_by_q_code_maps_md_to_runway() -> None:
    result = classify_by_q_code("YMMM/QMDCH/IV/NBO/A/000/999/3357S15111E005")

    assert result.topic == "RUNWAY"
    assert result.confidence == Q_CODE_MATCH_CONFIDENCE


def test_classify_by_q_code_unknown_subject_returns_misc_with_zero_confidence() -> None:
    result = classify_by_q_code("YMMM/QZZZZ/IV/NBO/A/000/999/3357S15111E005")

    assert result.topic == MISC_TOPIC
    assert result.confidence == 0


def test_classify_notam_with_q_line_does_not_use_e_heuristics() -> None:
    notam = RawNotam(
        notam_id="C0481/26 NOTAMN",
        q="YMMM/QZZZZ/IV/NBO/A/000/999/3357S15111E005",
        e="OBST CRANE MARKED AND LIT",
    )

    result = classify_notam(notam)

    assert result.topic == MISC_TOPIC
    assert result.confidence == 0


def test_classify_by_e_heuristics_qualifies_with_strong_and_moderate() -> None:
    result = classify_by_e_heuristics(
        "ILS RWY 35 ON TEST, DO NOT USE FALSE INDICATIONS POSSIBLE",
        title=None,
    )

    assert result.topic == "APPROACH_PROCEDURE"
    assert result.confidence >= 15


def test_classify_by_e_heuristics_moderate_only_returns_misc_with_score() -> None:
    result = classify_by_e_heuristics("RADAR COVERAGE LIMITED", title=None)

    assert result.topic == MISC_TOPIC
    assert result.confidence == 5


def test_classify_by_e_heuristics_below_cutoff_stores_top_score() -> None:
    result = classify_by_e_heuristics("OBST", title=None)

    assert result.topic == MISC_TOPIC
    assert result.confidence == 5


def test_signal_in_text_rejects_mid_string_match() -> None:
    assert signal_in_text("HELLOWORLD", "HELLO") is False


def test_signal_in_text_matches_whole_token() -> None:
    assert signal_in_text("HELLO WORLD", "HELLO") is True


def test_signal_in_text_matches_multi_word_phrase() -> None:
    assert signal_in_text("ILS RWY 35 ON TEST", "ILS RWY") is True


def test_classify_by_e_heuristics_tie_returns_misc_with_top_score() -> None:
    text = "OBST CRANE MARKED AND LIT ILS RWY 35 ON TEST"
    result = classify_by_e_heuristics(text, title=None)

    assert result.topic == MISC_TOPIC
    assert result.confidence >= 15


def test_classify_by_e_heuristics_skips_empty_signals() -> None:
    result = classify_by_e_heuristics("ROUTE CHANGE", title=None)

    assert result.topic == MISC_TOPIC
    assert result.confidence == 2


def test_classify_notam_uses_e_heuristics_when_q_missing() -> None:
    notam = RawNotam(
        notam_id="C316/23",
        e="ILS 'ICB' 109.5 RWY 35 ON TEST, DO NOT USE FALSE INDICATIONS POSSIBLE",
    )

    result = classify_notam(notam)

    assert result.topic == "APPROACH_PROCEDURE"
    assert result.confidence >= 15


def test_classify_by_e_heuristics_includes_title_in_search_text() -> None:
    result = classify_by_e_heuristics("DECLARED DISTANCE", title="RWY CLSD")

    assert result.topic == "RUNWAY"
    assert result.confidence >= 15
