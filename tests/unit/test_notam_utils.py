from app.services.notam_utils import (
    is_page_break,
    join_e_lines,
    naips_datetime,
    naips_document_year,
    strip_page_breaks,
)


def test_is_page_break_foreflight() -> None:
    assert is_page_break("NOTAMs:Page2of37")
    assert is_page_break("NOTAMs 2 of 14")
    assert not is_page_break("E) RWY 07/25 CLSD")


def test_is_page_break_naips() -> None:
    assert is_page_break(
        "https://www.airservicesaustralia.com/naips/Spfib/NewBriefing 5/6/2026, 15:22"
    )
    assert is_page_break("Page 7 of 19")


def test_strip_page_breaks_removes_mid_notam_footers() -> None:
    text = "A) RJTT\nNOTAMs:Page2of37\n\nB) 2604190300"
    assert strip_page_breaks(text) == "A) RJTT\n\nB) 2604190300"


def test_join_e_lines_uses_marker() -> None:
    assert join_e_lines(["TWY B2 CLSD", "", "TWY F2 CLSD"]) == (
        "TWY B2 CLSD {\\n} TWY F2 CLSD"
    )


def test_naips_document_year() -> None:
    assert naips_document_year("0521 UTC 05/06/26 AIRSERVICES AUSTRALIA") == "26"


def test_naips_datetime_expands_token() -> None:
    assert naips_datetime("02 180155", "26") == "2602180155"
