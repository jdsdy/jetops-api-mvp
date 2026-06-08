import re

LINE_MARKER = "{\\n}"
E_JOIN = f" {LINE_MARKER} "

_PAGE_BREAK_PATTERNS = (
    re.compile(r"^NOTAMs.*\d+\s*of\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"^https?://\S*airservicesaustralia\S*", re.IGNORECASE),
    re.compile(r"^Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
)

_DOCUMENT_YEAR = re.compile(r"UTC\s+\d{2}/\d{2}/(\d{2})")


def is_page_break(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in _PAGE_BREAK_PATTERNS)


def strip_page_breaks(text: str) -> str:
    """Drop page-footer lines that inject themselves mid-NOTAM."""
    kept = [line for line in text.splitlines() if not is_page_break(line)]
    return "\n".join(kept)


def join_e_lines(lines: list[str]) -> str:
    """Join multi-line NOTAM content with the renderer line marker."""
    segments = [line.strip() for line in lines if line.strip()]
    return E_JOIN.join(segments)


def naips_document_year(text: str) -> str:
    """Two-digit year from the NAIPS header line (e.g. '05/06/26' -> '26')."""
    match = _DOCUMENT_YEAR.search(text)
    if not match:
        raise ValueError("NAIPS document year not found")
    return match.group(1)


def naips_datetime(token: str, year: str) -> str:
    """Expand a NAIPS 'MM DDHHmm' token into 'YYMMDDHHmm'."""
    month, day_time = token.split()
    return f"{year}{month}{day_time}"
