import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings
from app.schemas.notam import RawNotam
from app.schemas.notam_topic import MISC_TOPIC, ClassificationResult

Q_CODE_MATCH_CONFIDENCE = 100

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
_IDENTIFIER_CODES_PATH = _SCHEMAS_DIR / "notam_identifier_codes.json"
_TYPE_SIGNALS_PATH = _SCHEMAS_DIR / "notam_type_signals.json"

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


# --- Public API ---


def classify_notam(
    notam: RawNotam,
    *,
    settings: Settings | None = None,
) -> ClassificationResult:
    if notam.q:
        return classify_by_q_code(notam.q)
    return classify_by_e_heuristics(notam.e, notam.title, settings=settings)
