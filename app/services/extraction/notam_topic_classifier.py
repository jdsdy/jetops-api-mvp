import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings
from app.schemas.notam import RawNotam
from app.schemas.notam_topic import MISC_TOPIC, ClassificationResult

Q_CODE_MATCH_CONFIDENCE = 100

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"
_IDENTIFIER_CODES_PATH = _SCHEMAS_DIR / "notam_identifier_codes.json"
_TYPE_SIGNALS_PATH = _SCHEMAS_DIR / "notam_type_signals.json"
_TITLE_SIGNALS_PATH = _SCHEMAS_DIR / "notam_title_signals.json"

_SIGNAL_BOUNDARY = r"(?<![A-Z0-9])"
_SIGNAL_END = r"(?![A-Z0-9])"


# --- Reference data ---


@lru_cache
def _load_q_code_lookup() -> dict[str, str]:
    raw = json.loads(_IDENTIFIER_CODES_PATH.read_text())
    lookup: dict[str, str] = {}
    for topic, codes in raw.items():
        for code in codes:
            lookup[code.upper()] = topic
    return lookup


@lru_cache
def _load_type_signals() -> dict[str, dict[str, list[str]]]:
    return json.loads(_TYPE_SIGNALS_PATH.read_text())


@lru_cache
def _load_title_signals() -> dict[str, dict[str, list[str]]]:
    return json.loads(_TITLE_SIGNALS_PATH.read_text())


# --- Q-line classification ---


def extract_q_code_subject(q_line: str) -> str | None:
    """Extract the 2-letter subject code from a NOTAM Q line."""
    segments = q_line.strip().split("/")
    if len(segments) < 2:
        return None

    q_code = segments[1].strip().upper()
    if len(q_code) < 3:
        return None

    return q_code[1:3]


def classify_by_q_code(q_line: str) -> ClassificationResult:
    subject = extract_q_code_subject(q_line)
    if subject is None:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    topic = _load_q_code_lookup().get(subject)
    if topic is None:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    return ClassificationResult(topic=topic, confidence=Q_CODE_MATCH_CONFIDENCE)


# --- E-line heuristic classification ---


def signal_in_text(text: str, signal: str) -> bool:
    """Return True when signal appears as its own token/phrase in text."""
    if not signal:
        return False

    normalized = text.upper()
    pattern = (
        f"{_SIGNAL_BOUNDARY}{re.escape(signal.upper())}{_SIGNAL_END}"
    )
    return re.search(pattern, normalized) is not None


def _build_search_text(e: str | None, title: str | None) -> str:
    parts = [part for part in (e, title) if part]
    return " ".join(parts)


def _score_topic(
    text: str,
    signals: dict[str, list[str]],
    *,
    strong_score: int,
    moderate_score: int,
    weak_score: int,
) -> int:
    score = 0
    for signal in signals.get("strong", []):
        if signal and signal_in_text(text, signal):
            score += strong_score
    for signal in signals.get("moderate", []):
        if signal and signal_in_text(text, signal):
            score += moderate_score
    for signal in signals.get("weak", []):
        if signal and signal_in_text(text, signal):
            score += weak_score
    return score


def classify_by_e_heuristics(
    e: str | None,
    title: str | None,
    *,
    settings: Settings | None = None,
) -> ClassificationResult:
    if settings is None:
        settings = get_settings()

    text = _build_search_text(e, title)
    if not text:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    topic_scores: dict[str, int] = {}
    for topic, signals in _load_type_signals().items():
        topic_scores[topic] = _score_topic(
            text,
            signals,
            strong_score=settings.NOTAM_TOPIC_STRONG_SCORE,
            moderate_score=settings.NOTAM_TOPIC_MODERATE_SCORE,
            weak_score=settings.NOTAM_TOPIC_WEAK_SCORE,
        )

    top_score = max(topic_scores.values(), default=0)
    if top_score == 0:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    qualifying = [
        topic
        for topic, score in topic_scores.items()
        if score >= settings.NOTAM_TOPIC_SCORE_CUTOFF
    ]

    if len(qualifying) == 1:
        return ClassificationResult(topic=qualifying[0], confidence=top_score)

    return ClassificationResult(topic=MISC_TOPIC, confidence=top_score)


# --- Title heuristic classification ---

TITLE_EXACT_MATCH_CONFIDENCE = 100


def _normalize_title(title: str) -> str:
    return title.strip().upper()


def _title_exact_match(title: str, exact_signals: list[str]) -> bool:
    normalized = _normalize_title(title)
    return any(
        normalized == entry.strip().upper()
        for entry in exact_signals
        if entry
    )


def _count_matching_signals(text: str, signals: list[str]) -> int:
    return sum(1 for signal in signals if signal and signal_in_text(text, signal))


def _title_topic_qualifies(text: str, signals: dict[str, list[str]]) -> bool:
    strong_hits = _count_matching_signals(text, signals.get("strong", []))
    if strong_hits >= 1:
        return True
    moderate_hits = _count_matching_signals(text, signals.get("moderate", []))
    return moderate_hits >= 2


def _title_topic_confidence(
    text: str,
    signals: dict[str, list[str]],
    *,
    strong_score: int,
    moderate_score: int,
) -> int:
    strong_hits = _count_matching_signals(text, signals.get("strong", []))
    if strong_hits >= 1:
        return strong_score
    moderate_hits = _count_matching_signals(text, signals.get("moderate", []))
    if moderate_hits >= 2:
        return moderate_hits * moderate_score
    if moderate_hits == 1:
        return moderate_score
    return 0


def classify_by_title_heuristics(
    title: str | None,
    *,
    settings: Settings | None = None,
) -> ClassificationResult:
    if settings is None:
        settings = get_settings()

    if not title:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    exact_matches: list[str] = []
    for topic, signals in _load_title_signals().items():
        if _title_exact_match(title, signals.get("exact", [])):
            exact_matches.append(topic)

    if len(exact_matches) == 1:
        return ClassificationResult(
            topic=exact_matches[0],
            confidence=TITLE_EXACT_MATCH_CONFIDENCE,
        )
    if len(exact_matches) > 1:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    qualifying: list[str] = []
    topic_confidence: dict[str, int] = {}
    for topic, signals in _load_title_signals().items():
        confidence = _title_topic_confidence(
            title,
            signals,
            strong_score=settings.NOTAM_TOPIC_STRONG_SCORE,
            moderate_score=settings.NOTAM_TOPIC_MODERATE_SCORE,
        )
        topic_confidence[topic] = confidence
        if _title_topic_qualifies(title, signals):
            qualifying.append(topic)

    if len(qualifying) == 1:
        topic = qualifying[0]
        return ClassificationResult(topic=topic, confidence=topic_confidence[topic])

    top_score = max(topic_confidence.values(), default=0)
    return ClassificationResult(topic=MISC_TOPIC, confidence=top_score)


# --- ForeFlight triple-channel vote ---


def _is_misc(topic: str) -> bool:
    return topic == MISC_TOPIC


def _identifies(topic: str) -> bool:
    return topic != MISC_TOPIC


def resolve_foreflight_vote(
    q: ClassificationResult,
    e: ClassificationResult,
    title: ClassificationResult,
) -> ClassificationResult:
    q_topic, e_topic, title_topic = q.topic, e.topic, title.topic
    non_misc = {topic for topic in (q_topic, e_topic, title_topic) if _identifies(topic)}

    if (
        _identifies(q_topic)
        and q_topic == e_topic == title_topic
    ):
        return ClassificationResult(topic=q_topic, confidence=100)

    if all(_is_misc(topic) for topic in (q_topic, e_topic, title_topic)):
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    if len(non_misc) == 3:
        return ClassificationResult(topic=MISC_TOPIC, confidence=0)

    if (
        q_topic == title_topic
        and _identifies(q_topic)
        and _is_misc(e_topic)
    ):
        return ClassificationResult(topic=q_topic, confidence=80)

    if (
        q_topic == title_topic
        and _identifies(q_topic)
        and _identifies(e_topic)
        and e_topic != q_topic
    ):
        return ClassificationResult(topic=q_topic, confidence=40)

    if (
        e_topic == title_topic
        and _identifies(e_topic)
        and e_topic != q_topic
    ):
        return ClassificationResult(topic=e_topic, confidence=70)

    if (
        q_topic == e_topic
        and _identifies(q_topic)
        and title_topic != q_topic
    ):
        return ClassificationResult(topic=q_topic, confidence=50)

    if _identifies(q_topic) and _is_misc(e_topic) and _is_misc(title_topic):
        return ClassificationResult(topic=q_topic, confidence=50)

    if _identifies(e_topic) and _is_misc(q_topic) and _is_misc(title_topic):
        return ClassificationResult(topic=e_topic, confidence=30)

    if _identifies(title_topic) and _is_misc(q_topic) and _is_misc(e_topic):
        return ClassificationResult(topic=MISC_TOPIC, confidence=30)

    return ClassificationResult(topic=MISC_TOPIC, confidence=0)


def classify_foreflight_notam(
    notam: RawNotam,
    *,
    settings: Settings | None = None,
) -> ClassificationResult:
    if settings is None:
        settings = get_settings()

    if not notam.q:
        return classify_by_e_heuristics(notam.e, notam.title, settings=settings)

    q_result = classify_by_q_code(notam.q)
    e_result = classify_by_e_heuristics(notam.e, None, settings=settings)
    title_result = classify_by_title_heuristics(notam.title, settings=settings)
    return resolve_foreflight_vote(q_result, e_result, title_result)


# --- Public API ---


def classify_notam(
    notam: RawNotam,
    *,
    settings: Settings | None = None,
) -> ClassificationResult:
    if notam.q:
        return classify_foreflight_notam(notam, settings=settings)
    return classify_by_e_heuristics(notam.e, notam.title, settings=settings)
