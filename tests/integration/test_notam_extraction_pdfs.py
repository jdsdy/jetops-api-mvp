import json
import re

import pytest

from app.schemas.notam import RawNotam
from app.services.extraction.notam_parser import extract_notams
from app.services.extraction.pdf_extractor import extract_pdf_text
from tests.paths import EXAMPLE_PLANS_DIR, NOTAM_FIXTURES

FIELDS = ("title", "q", "a", "b", "c", "d", "e", "f", "g")


def load_expected_cases() -> list[dict]:
    return json.loads(NOTAM_FIXTURES.read_text(encoding="utf-8"))


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value.replace("{\\n}", " ")).strip()


def assert_contains_expected(notams: list[RawNotam], expected: list[dict]) -> None:
    by_id = {notam.notam_id: notam for notam in notams}
    for case in expected:
        notam_id = case["notam_id"]
        assert notam_id in by_id, f"missing NOTAM {notam_id}"
        actual = by_id[notam_id]
        for field in FIELDS:
            assert _normalize(getattr(actual, field)) == _normalize(case[field]), (
                f"{notam_id} field {field}"
            )


@pytest.mark.parametrize("case", load_expected_cases(), ids=lambda c: c["pdf"])
def test_extract_notams_from_txt(case: dict) -> None:
    txt_name = case["pdf"].replace(".pdf", ".txt")
    text = (EXAMPLE_PLANS_DIR / txt_name).read_text(encoding="utf-8")
    assert_contains_expected(extract_notams(text), case["notams"])


@pytest.mark.parametrize("case", load_expected_cases(), ids=lambda c: c["pdf"])
def test_extract_notams_from_pdf(case: dict) -> None:
    result = extract_pdf_text(EXAMPLE_PLANS_DIR / case["pdf"])
    assert_contains_expected(extract_notams(result.text), case["notams"])
