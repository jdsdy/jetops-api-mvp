from app.services.extraction.pdf_extractor import extract_pdf_text
from tests.paths import EXAMPLE_PLANS_DIR

YSSY_YPPH_PDF = EXAMPLE_PLANS_DIR / "Briefing: YSSY - YPPH (created Apr 14 01:22:14Z).pdf"


def test_extract_pdf_text_contains_route_report_and_recall_line() -> None:
    result = extract_pdf_text(YSSY_YPPH_PDF)

    assert result.page_count > 0
    assert "Route Report" in result.text
    assert "Recall # DEP ETD DEST ETA" in result.text
