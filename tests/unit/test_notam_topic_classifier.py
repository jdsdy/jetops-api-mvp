import pytest

from app.schemas.notam import RawNotam
from app.schemas.notam_topic import MISC_TOPIC
from app.services.extraction.notam_topic_classifier import (
    Q_CODE_MATCH_CONFIDENCE,
    classify_by_e_heuristics,
    classify_by_q_code,
    classify_by_title_heuristics,
    classify_foreflight_notam,
    classify_notam,
    extract_q_code_subject,
    resolve_foreflight_vote,
    signal_in_text,
)
from app.schemas.notam_topic import ClassificationResult


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


def test_classify_notam_with_unmapped_q_uses_e_channel_when_e_identifies() -> None:
    notam = RawNotam(
        notam_id="C0481/26 NOTAMN",
        q="YMMM/QZZZZ/IV/NBO/A/000/999/3357S15111E005",
        e="OBST CRANE MARKED AND LIT",
    )

    result = classify_notam(notam)

    assert result.topic == "OBSTACLE"
    assert result.confidence == 30


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
    assert result.confidence == 8


def test_classify_by_e_heuristics_below_cutoff_stores_top_score() -> None:
    result = classify_by_e_heuristics("OBST", title=None)

    assert result.topic == MISC_TOPIC
    assert result.confidence == 8


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
    assert result.confidence == 3


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
    assert result.confidence >= 23


@pytest.mark.parametrize(
    ("q", "e", "title", "expected_topic", "expected_confidence"),
    [
        (
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic="RUNWAY", confidence=23),
            ClassificationResult(topic="RUNWAY", confidence=23),
            "RUNWAY",
            100,
        ),
        (
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic="RUNWAY", confidence=100),
            "RUNWAY",
            80,
        ),
        (
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic="OBSTACLE", confidence=30),
            ClassificationResult(topic="RUNWAY", confidence=100),
            "RUNWAY",
            40,
        ),
        (
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic="OBSTACLE", confidence=30),
            ClassificationResult(topic="OBSTACLE", confidence=30),
            "OBSTACLE",
            70,
        ),
        (
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic="OBSTACLE", confidence=30),
            "RUNWAY",
            50,
        ),
        (
            ClassificationResult(topic="COMMS", confidence=100),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            "COMMS",
            50,
        ),
        (
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic="NAVAID", confidence=30),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            "NAVAID",
            30,
        ),
        (
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic="LIGHTING", confidence=30),
            MISC_TOPIC,
            30,
        ),
        (
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            ClassificationResult(topic=MISC_TOPIC, confidence=0),
            MISC_TOPIC,
            0,
        ),
        (
            ClassificationResult(topic="RUNWAY", confidence=100),
            ClassificationResult(topic="OBSTACLE", confidence=30),
            ClassificationResult(topic="COMMS", confidence=30),
            MISC_TOPIC,
            0,
        ),
    ],
)
def test_resolve_foreflight_vote_rules(
    q: ClassificationResult,
    e: ClassificationResult,
    title: ClassificationResult,
    expected_topic: str,
    expected_confidence: int,
) -> None:
    result = resolve_foreflight_vote(q, e, title)

    assert result.topic == expected_topic
    assert result.confidence == expected_confidence


def test_classify_by_title_heuristics_empty_title_returns_misc() -> None:
    result = classify_by_title_heuristics(None)

    assert result.topic == MISC_TOPIC
    assert result.confidence == 0


def test_classify_by_title_heuristics_no_signals_returns_misc() -> None:
    result = classify_by_title_heuristics("RWY CLSD")

    assert result.topic == MISC_TOPIC
    assert result.confidence == 0


def test_classify_by_title_heuristics_exact_match_qualifies() -> None:
    result = classify_by_title_heuristics("AERODROME")

    assert result.topic == "AERODROME_GENERAL"
    assert result.confidence == 100


def test_classify_by_title_heuristics_exact_match_is_case_insensitive() -> None:
    result = classify_by_title_heuristics("  aerodrome  ")

    assert result.topic == "AERODROME_GENERAL"
    assert result.confidence == 100


def test_classify_by_title_heuristics_exact_does_not_match_partial_title() -> None:
    result = classify_by_title_heuristics("AERODROME LIMITED TO CAT C")

    assert result.topic == "AERODROME_GENERAL"
    assert result.confidence == 15


def test_classify_by_title_heuristics_exact_overrides_other_topic_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.extraction.notam_topic_classifier._load_title_signals",
        lambda: {
            "AERODROME_GENERAL": {"strong": [], "moderate": [], "exact": ["BIRDS"]},
            "OBSTACLE": {"strong": ["BIRDS"], "moderate": []},
        },
    )

    result = classify_by_title_heuristics("BIRDS")

    assert result.topic == "AERODROME_GENERAL"
    assert result.confidence == 100


def test_classify_by_title_heuristics_multiple_exact_matches_returns_misc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.extraction.notam_topic_classifier._load_title_signals",
        lambda: {
            "AERODROME_GENERAL": {"strong": [], "moderate": [], "exact": ["FOO"]},
            "RUNWAY": {"strong": [], "moderate": [], "exact": ["FOO"]},
        },
    )

    result = classify_by_title_heuristics("FOO")

    assert result.topic == MISC_TOPIC
    assert result.confidence == 0


def test_classify_by_title_heuristics_single_strong_signal_qualifies() -> None:
    result = classify_by_title_heuristics("OBSTACLE ERECTED AT AD")

    assert result.topic == "OBSTACLE"
    assert result.confidence == 15


def test_classify_by_title_heuristics_two_moderate_signals_qualify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.extraction.notam_topic_classifier._load_title_signals",
        lambda: {
            "RUNWAY": {
                "strong": [],
                "moderate": ["RWY", "CLSD"],
            }
        },
    )

    result = classify_by_title_heuristics("RWY 03 CLSD")

    assert result.topic == "RUNWAY"
    assert result.confidence == 16


def test_classify_by_title_heuristics_one_moderate_returns_misc_with_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.extraction.notam_topic_classifier._load_title_signals",
        lambda: {
            "RUNWAY": {
                "strong": [],
                "moderate": ["RWY", "CLSD"],
            }
        },
    )

    result = classify_by_title_heuristics("RWY 03")

    assert result.topic == MISC_TOPIC
    assert result.confidence == 8


def test_classify_by_title_heuristics_multiple_qualifying_topics_returns_misc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.extraction.notam_topic_classifier._load_title_signals",
        lambda: {
            "RUNWAY": {"strong": ["RWY CLSD"], "moderate": []},
            "OBSTACLE": {"strong": ["OBSTACLE"], "moderate": []},
        },
    )

    result = classify_by_title_heuristics("RWY CLSD OBSTACLE")

    assert result.topic == MISC_TOPIC
    assert result.confidence == 15


def test_classify_foreflight_notam_q_and_e_agree_when_title_unmatched() -> None:
    notam = RawNotam(
        notam_id="C0481/26 NOTAMN",
        q="YMMM/QMDCH/IV/NBO/A/000/999/3357S15111E005",
        e="RWY CLSD DUE WIP",
        title="RWY CLSD",
    )

    result = classify_foreflight_notam(notam)

    assert result.topic == "RUNWAY"
    assert result.confidence == 50
