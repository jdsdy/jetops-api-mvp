import re

from app.schemas.notam import RawNotam
from app.services.flight_parser import detect_plan_format

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

LINE_MARKER = "{\\n}"
E_JOIN = f" {LINE_MARKER} "

_PAGE_BREAK_PATTERNS = (
    re.compile(r"^NOTAMs.*\d+\s*of\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"^https?://\S*airservicesaustralia\S*", re.IGNORECASE),
    re.compile(r"^Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
)

_DOCUMENT_YEAR = re.compile(r"UTC\s+\d{2}/\d{2}/(\d{2})")


def _is_page_break(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in _PAGE_BREAK_PATTERNS)


def _strip_page_breaks(text: str) -> str:
    kept = [line for line in text.splitlines() if not _is_page_break(line)]
    return "\n".join(kept)


def _naips_document_year(text: str) -> str:
    match = _DOCUMENT_YEAR.search(text)
    if not match:
        raise ValueError("NAIPS document year not found")
    return match.group(1)


def _naips_datetime(token: str, year: str) -> str:
    month, day_time = token.split()
    return f"{year}{month}{day_time}"


def _clean_notam_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _join_plain(parts: list[str]) -> str | None:
    return _clean_notam_value(" ".join(parts))


def _join_marked(parts: list[str]) -> str | None:
    return _clean_notam_value(E_JOIN.join(part for part in parts if part))


def _join_digits(parts: list[str]) -> str | None:
    joined = " ".join(parts)
    joined = re.sub(r"(?<=\d)\s+(?=\d)", "", joined)
    return _clean_notam_value(joined)


# ---------------------------------------------------------------------------
# ForeFlight NOTAM parser
# ---------------------------------------------------------------------------

_FF_FIELD_ORDER = "QABCDEFG"
_FF_SECTION_HEADER = "NOTAMs"

_FF_STD_ID = re.compile(
    r"^[A-Z]\d{2,4}/\d{1,3}"
    r"( (NOTAM\w*)( [A-Z]\d{2,4}/\d{1,3})?| REPLACE [A-Z]\d{2,4}/\d{1,3})?$"
)
_FF_US_ID = re.compile(r"^[A-Z]{2,4} \d{1,2}/\d{2,4}\b")
_FF_TAG = re.compile(r"(?:(?<=\s)|^)([QABCDEFG])\)")

_FF_FIR = re.compile(r"^FIR\b")
_FF_DEP_DEST = re.compile(r"^(Departure|Destination)\b")
_FF_DESCRIPTOR = re.compile(r"^\[.*\]$")
_FF_ALTERNATE = re.compile(r"^Alternate\d")
_FF_ALPHA_ONLY = re.compile(r"^[A-Za-z]+$")
_FF_ENROUTE_MARKER = re.compile(r"NOTAMs$", re.IGNORECASE)

_FF_DATE_RANGE = re.compile(r"(\d{10})-(\d{10})(EST)?\s*$")
_FF_ALTITUDE = r"(?:SFC|FL\d+|\d+FT (?:AGL|AMSL))"
_FF_FG_PAIR = re.compile(rf"({_FF_ALTITUDE})-({_FF_ALTITUDE})\s*$")


def _parse_foreflight_notams(text: str) -> list[RawNotam]:
    lines = _foreflight_section_lines(_strip_page_breaks(text))
    n = len(lines)

    notams: list[RawNotam] = []
    pending_title: str | None = None
    section_word: str | None = None
    in_condensed = False
    i = 0

    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        if _FF_FIR.match(stripped):
            in_condensed = True
            i += 1
            continue
        if _FF_DEP_DEST.match(stripped):
            in_condensed = False
            i += 1
            continue
        if _FF_DESCRIPTOR.match(stripped):
            i += 1
            continue

        if _FF_STD_ID.match(stripped):
            field_lines, next_title, i = _collect_std_block(lines, i + 1)
            notams.append(_parse_std_notam(stripped, pending_title, field_lines))
            pending_title = next_title
            in_condensed = False
            continue

        if in_condensed and _FF_US_ID.match(stripped):
            entry, i = _collect_condensed(lines, i)
            notams.append(_parse_condensed_notam(entry, section_word))
            continue

        if _FF_ALTERNATE.match(stripped) or (
            _FF_ALPHA_ONLY.match(stripped) and _FF_ENROUTE_MARKER.search(stripped)
        ):
            i += 1
            continue

        if _FF_ALPHA_ONLY.match(stripped):
            nxt = _peek_line(lines, i + 1)
            if nxt and _FF_US_ID.match(nxt):
                section_word = stripped
                in_condensed = True
            else:
                pending_title = stripped
            i += 1
            continue

        pending_title = stripped
        in_condensed = False
        i += 1

    return notams


def _foreflight_section_lines(text: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == _FF_SECTION_HEADER:
            return lines[index + 1 :]
    return lines


def _peek_line(lines: list[str], start: int) -> str | None:
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped:
            return stripped
    return None


def _is_ff_ignored_alpha_line(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if not _FF_ALPHA_ONLY.match(stripped):
        return False
    if _FF_ENROUTE_MARKER.search(stripped):
        return True
    nxt = _peek_line(lines, index + 1)
    return bool(nxt and _FF_US_ID.match(nxt))


def _should_break_std_block(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if (
        _FF_STD_ID.match(stripped)
        or _FF_FIR.match(stripped)
        or _FF_DEP_DEST.match(stripped)
        or _FF_US_ID.match(stripped)
        or _FF_ALTERNATE.match(stripped)
        or _is_ff_ignored_alpha_line(lines, index)
    ):
        return True
    return False


def _collect_std_block(
    lines: list[str], start: int
) -> tuple[list[str], str | None, int]:
    j = start
    n = len(lines)
    while j < n and not _should_break_std_block(lines, j):
        j += 1

    block = [line.strip() for line in lines[start:j]]
    next_is_std = j < n and _FF_STD_ID.match(lines[j].strip()) is not None

    while block and not block[-1]:
        block.pop()
    while block and _FF_DESCRIPTOR.match(block[-1]):
        block.pop()

    next_title: str | None = None
    if next_is_std and block:
        next_title = block.pop()
    while block and not block[-1]:
        block.pop()

    return block, next_title, j


def _collect_condensed(lines: list[str], start: int) -> tuple[list[str], int]:
    n = len(lines)
    entry = [lines[start].strip()]
    if _FF_DATE_RANGE.search(entry[-1]):
        return entry, start + 1

    j = start + 1
    while j < n:
        stripped = lines[j].strip()
        if not stripped:
            j += 1
            continue
        if _should_break_std_block(lines, j):
            break
        entry.append(stripped)
        if _FF_DATE_RANGE.search(stripped):
            j += 1
            break
        j += 1
    return entry, j


def _find_field_tags(line: str, min_index: int) -> list[tuple[str, int, int]]:
    tags: list[tuple[str, int, int]] = []
    last_index = min_index
    for match in _FF_TAG.finditer(line):
        letter = match.group(1)
        order = _FF_FIELD_ORDER.index(letter)
        if order > last_index:
            tags.append((letter, match.start(1), match.end()))
            last_index = order
    return tags


def _parse_std_notam(
    id_line: str, title: str | None, field_lines: list[str]
) -> RawNotam:
    fields: dict[str, list[str]] = {key: [] for key in _FF_FIELD_ORDER}
    current: str | None = None
    current_index = -1

    for line in field_lines:
        stripped = line.strip()
        if not stripped:
            continue
        tags = _find_field_tags(stripped, current_index)
        if not tags:
            if current:
                fields[current].append(stripped)
            continue

        pre = stripped[: tags[0][1]].strip()
        if pre and current:
            fields[current].append(pre)

        for index, (letter, _start, value_start) in enumerate(tags):
            end = tags[index + 1][1] if index + 1 < len(tags) else len(stripped)
            value = stripped[value_start:end].strip()
            current = letter
            current_index = _FF_FIELD_ORDER.index(letter)
            if value:
                fields[letter].append(value)

    return RawNotam(
        notam_id=id_line,
        title=_clean_notam_value(title),
        q=_join_plain(fields["Q"]),
        a=_join_plain(fields["A"]),
        b=_join_digits(fields["B"]),
        c=_join_digits(fields["C"]),
        d=_join_marked(fields["D"]),
        e=_join_marked(fields["E"]),
        f=_join_plain(fields["F"]),
        g=_join_plain(fields["G"]),
    )


def _parse_condensed_notam(entry: list[str], title: str | None) -> RawNotam:
    lines = [line for line in entry if line]
    id_match = _FF_US_ID.match(lines[0])
    assert id_match is not None
    notam_id = id_match.group(0)
    lines[0] = lines[0][id_match.end() :].strip()

    b = c = f = g = None
    last = lines[-1]
    date_match = _FF_DATE_RANGE.search(last)
    if date_match:
        b = date_match.group(1)
        c = date_match.group(2) + (date_match.group(3) or "")
        last = last[: date_match.start()].strip()

    fg_match = _FF_FG_PAIR.search(last)
    if fg_match:
        f = fg_match.group(1)
        g = fg_match.group(2)
        last = last[: fg_match.start()].strip()

    lines[-1] = last
    e = E_JOIN.join(segment for segment in lines if segment)

    return RawNotam(
        notam_id=notam_id,
        title=_clean_notam_value(title),
        b=b,
        c=c,
        e=_clean_notam_value(e),
        f=f,
        g=g,
    )


# ---------------------------------------------------------------------------
# NAIPS NOTAM parser
# ---------------------------------------------------------------------------

_NAIPS_SECTION_HEADER = "NOTAM INFORMATION"

_NAIPS_ID = re.compile(r"^[A-Z]\d{1,4}/\d{2}( REPLACE [A-Z]\d{1,4}/\d{2})?$")
_NAIPS_HEADER = re.compile(r"\(([A-Z0-9/]{2,12})\)\s*$")
_NAIPS_BRACKET = re.compile(r"\(([^)]*)\)")

_NAIPS_FG = re.compile(rf"^({_FF_ALTITUDE})\s+TO\s+({_FF_ALTITUDE})$")
_NAIPS_BC = re.compile(
    r"^FROM\s+(\d{2}\s+\d{6})\s+TO\s+(PERM|\d{2}\s+\d{6})(\s+EST)?$"
)
_NAIPS_D = re.compile(r"^(DAILY\b.*|HJ|HN|H24|(?:MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z0-9 -]*)$")


def _parse_naips_notams(text: str) -> list[RawNotam]:
    year = _naips_document_year(text)
    lines = _naips_section_lines(_strip_page_breaks(text))
    n = len(lines)

    notams: list[RawNotam] = []
    current_a: str | None = None
    i = 0

    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        if _NAIPS_ID.match(stripped):
            notam, i = _collect_naips_notam(lines, i, current_a, year)
            notams.append(notam)
            continue

        if _is_naips_header(stripped):
            current_a = _last_bracket(stripped)

        i += 1

    return notams


def _naips_section_lines(text: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == _NAIPS_SECTION_HEADER:
            return lines[index + 1 :]
    return lines


def _is_naips_header(line: str) -> bool:
    return bool(_NAIPS_HEADER.search(line)) and not _NAIPS_ID.match(line)


def _last_bracket(line: str) -> str | None:
    matches = _NAIPS_BRACKET.findall(line)
    return matches[-1] if matches else None


def _collect_naips_notam(
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

        if _NAIPS_ID.match(stripped):
            break

        fg_match = _NAIPS_FG.match(stripped)
        if fg_match:
            f, g = fg_match.group(1), fg_match.group(2)
            j += 1
            continue

        bc_match = _NAIPS_BC.match(stripped)
        if bc_match:
            b, c = _parse_naips_bc(bc_match, year)
            j += 1
            if j < n and _NAIPS_D.match(lines[j].strip()):
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


def _parse_naips_bc(match: re.Match[str], year: str) -> tuple[str, str]:
    b = _naips_datetime(match.group(1), year)
    if match.group(2) == "PERM":
        return b, "PERM"
    c = _naips_datetime(match.group(2), year)
    if match.group(3):
        c = f"{c} EST"
    return b, c


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PARSERS = {
    "foreflight": _parse_foreflight_notams,
    "naips": _parse_naips_notams,
}


def extract_notams(text: str) -> list[RawNotam]:
    return _PARSERS[detect_plan_format(text)](text)
