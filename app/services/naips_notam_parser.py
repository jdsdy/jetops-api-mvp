import re

from app.schemas.notam import RawNotam
from app.services.notam_utils import (
    E_JOIN,
    naips_datetime,
    naips_document_year,
    strip_page_breaks,
)

SECTION_HEADER = "NOTAM INFORMATION"

NAIPS_ID = re.compile(r"^[A-Z]\d{1,4}/\d{2}( REPLACE [A-Z]\d{1,4}/\d{2})?$")
_HEADER = re.compile(r"\(([A-Z0-9/]{2,12})\)\s*$")
_BRACKET = re.compile(r"\(([^)]*)\)")

_ALTITUDE = r"(?:SFC|FL\d+|\d+FT (?:AGL|AMSL))"
_FG = re.compile(rf"^({_ALTITUDE})\s+TO\s+({_ALTITUDE})$")
_BC = re.compile(
    r"^FROM\s+(\d{2}\s+\d{6})\s+TO\s+(PERM|\d{2}\s+\d{6})(\s+EST)?$"
)
_D = re.compile(r"^(DAILY\b.*|HJ|HN|H24|(?:MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z0-9 -]*)$")


def parse_naips_notams(text: str) -> list[RawNotam]:
    year = naips_document_year(text)
    lines = _section_lines(strip_page_breaks(text))
    n = len(lines)

    notams: list[RawNotam] = []
    current_a: str | None = None
    i = 0

    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        if NAIPS_ID.match(stripped):
            notam, i = _collect(lines, i, current_a, year)
            notams.append(notam)
            continue

        if _is_header(stripped):
            current_a = _last_bracket(stripped)

        i += 1

    return notams


def _section_lines(text: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == SECTION_HEADER:
            return lines[index + 1 :]
    return lines


def _is_header(line: str) -> bool:
    return bool(_HEADER.search(line)) and not NAIPS_ID.match(line)


def _last_bracket(line: str) -> str | None:
    matches = _BRACKET.findall(line)
    return matches[-1] if matches else None


def _collect(
    lines: list[str], start: int, current_a: str | None, year: str
) -> tuple[RawNotam, int]:
    notam_id = lines[start].strip()
    e_lines: list[str] = []
    b = c = d = f = g = None

    j = start + 1
    n = len(lines)
    while j < n:
        stripped = lines[j].strip()
        if not stripped:
            j += 1
            continue

        if NAIPS_ID.match(stripped):
            break

        fg_match = _FG.match(stripped)
        if fg_match:
            f, g = fg_match.group(1), fg_match.group(2)
            j += 1
            continue

        bc_match = _BC.match(stripped)
        if bc_match:
            b, c = _parse_bc(bc_match, year)
            j += 1
            if j < n and _D.match(lines[j].strip()):
                d = lines[j].strip()
                j += 1
            break

        e_lines.append(stripped)
        j += 1

    return (
        RawNotam(
            notam_id=notam_id,
            a=current_a,
            b=b,
            c=c,
            d=d,
            e=E_JOIN.join(e_lines) or None,
            f=f,
            g=g,
        ),
        j,
    )


def _parse_bc(match: re.Match[str], year: str) -> tuple[str, str]:
    b = naips_datetime(match.group(1), year)
    if match.group(2) == "PERM":
        return b, "PERM"
    c = naips_datetime(match.group(2), year)
    if match.group(3):
        c = f"{c} EST"
    return b, c
