from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pdfplumber


@dataclass
class PdfExtractionResult:
    text: str
    page_count: int


def find_column_boundary(page: pdfplumber.page.Page) -> float:
    words = page.extract_words()
    if not words:
        return page.width / 2

    page_width = page.width
    center_min = page_width * 0.3
    center_max = page_width * 0.7

    x_positions = sorted(
        {
            x
            for w in words
            for x in (w["x0"], w["x1"])
            if center_min < x < center_max
        }
    )

    if not x_positions:
        return page_width / 2

    max_gap = 0.0
    boundary = page_width / 2

    for i in range(len(x_positions) - 1):
        gap = x_positions[i + 1] - x_positions[i]
        if gap > max_gap:
            max_gap = gap
            boundary = (x_positions[i] + x_positions[i + 1]) / 2

    return boundary


def extract_two_column_page(page: pdfplumber.page.Page) -> str:
    height = page.height
    width = page.width
    mid = find_column_boundary(page)

    left_text = page.crop((0, 0, mid, height)).extract_text() or ""
    right_text = page.crop((mid, 0, width, height)).extract_text() or ""

    return left_text + "\n" + right_text


def extract_page_text(page: pdfplumber.page.Page) -> str:
    if page.width > page.height:
        return extract_two_column_page(page)
    return page.extract_text() or ""


def extract_pdf_text(source: str | bytes | Path) -> PdfExtractionResult:
    if isinstance(source, bytes):
        pdf_file: str | BytesIO = BytesIO(source)
    else:
        pdf_file = str(source)

    with pdfplumber.open(pdf_file) as pdf:
        pages = [extract_page_text(page) for page in pdf.pages]
    return PdfExtractionResult(text="\n\n".join(pages), page_count=len(pages))
