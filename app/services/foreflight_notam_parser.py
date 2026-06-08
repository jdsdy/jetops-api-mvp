import re

from app.schemas.notam import RawNotam
from app.services.notam_utils import E_JOIN, strip_page_breaks

FIELD_ORDER = "QABCDEFG"

SECTION_HEADER = "NOTAMs"

STD_ID = re.compile(
    r"^[A-Z]\d{2,4}/\d{1,3}"
    r"( (NOTAM\w*)( [A-Z]\d{2,4}/\d{1,3})?| REPLACE [A-Z]\d{2,4}/\d{1,3})?$"
)
US_ID = re.compile(r"^[A-Z]{2,4} \d{1,2}/\d{2,4}\b")
TAG = re.compile(r"(?:(?<=\s)|^)([QABCDEFG])\)")

_FIR = re.compile(r"^FIR\b")
_DEP_DEST = re.compile(r"^(Departure|Destination)\b")
_DESCRIPTOR = re.compile(r"^\[.*\]$")
_SINGLE_WORD = re.compile(r"^[A-Z][A-Z]+$")

_DATE_RANGE = re.compile(r"(\d{10})-(\d{10})(EST)?\s*$")
_ALTITUDE = r"(?:SFC|FL\d+|\d+FT (?:AGL|AMSL))"
_FG_PAIR = re.compile(rf"({_ALTITUDE})-({_ALTITUDE})\s*$")


def parse_foreflight_notams(text: str) -> list[RawNotam]:
    lines = _section_lines(strip_page_breaks(text))
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

        if _FIR.match(stripped):
            in_condensed = True
            i += 1
            continue
        if _DEP_DEST.match(stripped):
            in_condensed = False
            i += 1
            continue
        if _DESCRIPTOR.match(stripped):
            i += 1
            continue

        if STD_ID.match(stripped):
            field_lines, next_title, i = _collect_std_block(lines, i + 1)
            notams.append(_parse_std(stripped, pending_title, field_lines))
            pending_title = next_title
            in_condensed = False
            continue

        if in_condensed and US_ID.match(stripped):
            entry, i = _collect_condensed(lines, i)
            notams.append(_parse_condensed(entry, section_word))
            continue

        if _SINGLE_WORD.match(stripped):
            nxt = _peek(lines, i + 1)
            if nxt and US_ID.match(nxt):
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


def _section_lines(text: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == SECTION_HEADER:
            return lines[index + 1 :]
    return lines


def _peek(lines: list[str], start: int) -> str | None:
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped:
            return stripped
    return None


def _collect_std_block(
    lines: list[str], start: int
) -> tuple[list[str], str | None, int]:
    j = start
    n = len(lines)
    while j < n:
        stripped = lines[j].strip()
        if STD_ID.match(stripped) or _FIR.match(stripped) or _DEP_DEST.match(stripped):
            break
        j += 1

    block = [line.strip() for line in lines[start:j]]
    next_is_std = j < n and STD_ID.match(lines[j].strip()) is not None

    while block and not block[-1]:
        block.pop()
    while block and _DESCRIPTOR.match(block[-1]):
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
    if _DATE_RANGE.search(entry[-1]):
        return entry, start + 1

    j = start + 1
    while j < n:
        stripped = lines[j].strip()
        if not stripped:
            j += 1
            continue
        if US_ID.match(stripped) or STD_ID.match(stripped) or _FIR.match(stripped):
            break
        entry.append(stripped)
        if _DATE_RANGE.search(stripped):
            j += 1
            break
        j += 1
    return entry, j


def _find_tags(line: str, min_index: int) -> list[tuple[str, int, int]]:
    tags: list[tuple[str, int, int]] = []
    last_index = min_index
    for match in TAG.finditer(line):
        letter = match.group(1)
        order = FIELD_ORDER.index(letter)
        if order > last_index:
            tags.append((letter, match.start(1), match.end()))
            last_index = order
    return tags


def _parse_std(
    id_line: str, title: str | None, field_lines: list[str]
) -> RawNotam:
    fields: dict[str, list[str]] = {key: [] for key in FIELD_ORDER}
    current: str | None = None
    current_index = -1

    for line in field_lines:
        stripped = line.strip()
        if not stripped:
            continue
        tags = _find_tags(stripped, current_index)
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
            current_index = FIELD_ORDER.index(letter)
            if value:
                fields[letter].append(value)

    return RawNotam(
        notam_id=id_line,
        title=_clean(title),
        q=_join_plain(fields["Q"]),
        a=_join_plain(fields["A"]),
        b=_join_digits(fields["B"]),
        c=_join_digits(fields["C"]),
        d=_join_marked(fields["D"]),
        e=_join_marked(fields["E"]),
        f=_join_plain(fields["F"]),
        g=_join_plain(fields["G"]),
    )


def _parse_condensed(entry: list[str], title: str | None) -> RawNotam:
    lines = [line for line in entry if line]
    id_match = US_ID.match(lines[0])
    assert id_match is not None
    notam_id = id_match.group(0)
    lines[0] = lines[0][id_match.end() :].strip()

    b = c = f = g = None
    last = lines[-1]
    date_match = _DATE_RANGE.search(last)
    if date_match:
        b = date_match.group(1)
        c = date_match.group(2) + (date_match.group(3) or "")
        last = last[: date_match.start()].strip()

    fg_match = _FG_PAIR.search(last)
    if fg_match:
        f = fg_match.group(1)
        g = fg_match.group(2)
        last = last[: fg_match.start()].strip()

    lines[-1] = last
    e = E_JOIN.join(segment for segment in lines if segment)

    return RawNotam(
        notam_id=notam_id,
        title=_clean(title),
        b=b,
        c=c,
        e=_clean(e),
        f=f,
        g=g,
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _join_plain(parts: list[str]) -> str | None:
    return _clean(" ".join(parts))


def _join_marked(parts: list[str]) -> str | None:
    return _clean(E_JOIN.join(part for part in parts if part))


def _join_digits(parts: list[str]) -> str | None:
    joined = " ".join(parts)
    joined = re.sub(r"(?<=\d)\s+(?=\d)", "", joined)
    return _clean(joined)
