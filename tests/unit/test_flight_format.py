import pytest

from app.services.flight_format import detect_plan_format
from tests.paths import EXAMPLE_PLANS_DIR


@pytest.mark.parametrize(
    ("txt_name", "expected"),
    [
        ("Specific Pre-Flight Information Bulletin.txt", "naips"),
        ("Briefing: YSSY - YPPH (created Apr 14 01:22:14Z).txt", "foreflight"),
    ],
)
def test_detect_plan_format(txt_name: str, expected: str) -> None:
    text = (EXAMPLE_PLANS_DIR / txt_name).read_text(encoding="utf-8")
    assert detect_plan_format(text) == expected
