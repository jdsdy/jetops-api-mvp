from app.services.extraction.notam_parser import (
    E_JOIN,
    _is_page_break,
    _naips_datetime,
    _naips_document_year,
    _parse_foreflight_notams,
    _parse_naips_notams,
    _parse_ozrunways_notams,
    _strip_ozrunways_artifacts,
    _strip_page_breaks,
)

FF_SECTION = "NOTAMs\nDeparture YBBN-Brisbane\n"
NAIPS_HEADER = "0521 UTC 05/06/26 AIRSERVICES AUSTRALIA\nNOTAM INFORMATION\n-----------------\n"
OZ_HEADER = (
    "YPPH-YBRM\n"
    "Total: 903 NM, 3:29 ETD: 10 Jun 0626 UTC\n"
    "NOTAMs\n"
)


def _parse_foreflight(body: str):
    notams = _parse_foreflight_notams(FF_SECTION + body)
    return {notam.notam_id: notam for notam in notams}


def _parse_naips(body: str):
    notams = _parse_naips_notams(NAIPS_HEADER + body)
    return {notam.notam_id: notam for notam in notams}


def _parse_ozrunways(body: str):
    notams = _parse_ozrunways_notams(OZ_HEADER + body)
    return {notam.notam_id: notam for notam in notams}


# --- Shared helpers ---


def test_is_page_break_foreflight() -> None:
    assert _is_page_break("NOTAMs:Page2of37")
    assert _is_page_break("NOTAMs 2 of 14")
    assert not _is_page_break("E) RWY 07/25 CLSD")


def test_is_page_break_naips() -> None:
    assert _is_page_break(
        "https://www.airservicesaustralia.com/naips/Spfib/NewBriefing 5/6/2026, 15:22"
    )
    assert _is_page_break("Page 7 of 19")


def test_strip_page_breaks_removes_mid_notam_footers() -> None:
    text = "A) RJTT\nNOTAMs:Page2of37\n\nB) 2604190300"
    assert _strip_page_breaks(text) == "A) RJTT\n\nB) 2604190300"


def test_e_join_marker() -> None:
    assert E_JOIN.join(["TWY B2 CLSD", "TWY F2 CLSD"]) == (
        "TWY B2 CLSD{\\n} TWY F2 CLSD"
    )


def test_naips_document_year() -> None:
    assert _naips_document_year("0521 UTC 05/06/26 AIRSERVICES AUSTRALIA") == "26"


def test_naips_datetime_expands_token() -> None:
    assert _naips_datetime("02 180155", "26") == "2602180155"


# --- ForeFlight NOTAMs ---


def test_standard_notam_accepts_alphanumeric_sequence_suffix() -> None:
    body = (
        "RUNWAY CLOSED\n"
        "E1428/25A02 NOTAMN\n"
        "Q) YBBB/QMXLC/IV/BO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604191200 C) 2604191900\n"
        "E) RWY 01 CLSD\n"
    )
    notam = _parse_foreflight(body)["E1428/25A02 NOTAMN"]
    assert notam.title == "RUNWAY CLOSED"
    assert notam.e == "RWY 01 CLSD"


def test_shorthand_notam_reference_in_e_field_is_not_new_notam() -> None:
    body = (
        "RUNWAY CLOSED\n"
        "C0481/26 NOTAMN\n"
        "Q) YBBB/QMXLC/IV/BO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604191200 C) 2604191900\n"
        "E) SEE ALSO E1428/25 FOR DETAILS\n"
        "E1428/25\n"
        "OTHER NOTAM\n"
        "C0478/26 NOTAMN\n"
        "Q) YBBB/QFAHX/IV/NBO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604170011 C) 2604220748\n"
        "E) INCREASED BIRD HAZARD\n"
    )
    notams = _parse_foreflight(body)
    assert list(notams) == ["C0481/26 NOTAMN", "C0478/26 NOTAMN"]
    assert notams["C0481/26 NOTAMN"].e == (
        "SEE ALSO E1428/25 FOR DETAILS{\\n} E1428/25"
    )


def test_standard_notam_fields_and_title() -> None:
    body = (
        "TAXIWAY CLOSED (NEW TODAY)\n"
        "C0481/26 NOTAMN\n"
        "Q) YBBB/QMXLC/IV/BO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604191200 C) 2604191900\n"
        "E) TWY B2 CLSD\n"
        "TWY F2 BTN TWY B AND G1 CLSD\n"
        "AERODROME\n"
        "C0478/26 NOTAMN\n"
        "Q) YBBB/QFAHX/IV/NBO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604170011 C) 2604220748\n"
        "D) HJ\n"
        "E) INCREASED BIRD HAZARD\n"
    )
    notams = _parse_foreflight(body)
    first = notams["C0481/26 NOTAMN"]
    assert first.title == "TAXIWAY CLOSED (NEW TODAY)"
    assert first.a == "YBBN"
    assert first.b == "2604191200"
    assert first.c == "2604191900"
    assert first.e == "TWY B2 CLSD{\\n} TWY F2 BTN TWY B AND G1 CLSD"
    assert notams["C0478/26 NOTAMN"].d == "HJ"


def test_inline_altitude_fields_not_split_on_brackets_in_e() -> None:
    body = (
        "OBSTACLE LIGHTS ON UNSERVICEABLE\n"
        "J0880/26 NOTAMN\n"
        "Q) RJJJ/QOLAS/IV/M/AE/000/006/3541N13946E005\n"
        "A) RJTT B) 2604161455 C) 2607150800\n"
        "E) OBST LGT U/S\n"
        "(CHUO-KU IN TOKYO)\n"
        "F) SFC G) 371FT AMSL\n"
    )
    notam = _parse_foreflight(body)["J0880/26 NOTAMN"]
    assert notam.a == "RJTT"
    assert notam.e == "OBST LGT U/S{\\n} (CHUO-KU IN TOKYO)"
    assert notam.f == "SFC"
    assert notam.g == "371FT AMSL"


def test_condensed_notams_share_section_title_after_fir() -> None:
    body = (
        "NON-DIRECTIONAL RADIO BEACON UNSERVICEABLE\n"
        "A0377/26 NOTAMR A1660/25\n"
        "Q) AYPM/QNBAS/IV/NBO/AE/000/999/\n"
        "A) AYOC B) 2603242315 C) 2606170700 EST\n"
        "E) NDB 'OKT' 1632 U/S.\n"
        "FIR KZAK\n"
        "NAVIGATION\n"
        "HNL 04/227 TKK NAV NDB U/S 2604180306-2604302359EST\n"
        "AIRSPACE\n"
        "SUAW 04/616 ZAK AIRSPACE W291E ACT SFC-FL500 2604191300-2604201300\n"
    )
    notams = _parse_foreflight(body)

    standard = notams["A0377/26 NOTAMR A1660/25"]
    assert standard.e == "NDB 'OKT' 1632 U/S."
    assert standard.c == "2606170700 EST"

    nav = notams["HNL 04/227"]
    assert nav.title == "NAVIGATION"
    assert nav.e == "TKK NAV NDB U/S"
    assert nav.b == "2604180306"
    assert nav.c == "2604302359EST"

    airspace = notams["SUAW 04/616"]
    assert airspace.title == "AIRSPACE"
    assert airspace.e == "ZAK AIRSPACE W291E ACT"
    assert airspace.f == "SFC"
    assert airspace.g == "FL500"


def test_enroute_section_marker_splits_e_field_from_condensed_notam() -> None:
    body = (
        "TAXIWAY CLOSED\n"
        "E1807/26 NOTAMN\n"
        "Q) RJJJ/QMXLC/IV/M/A/000/999/3533N13947E005\n"
        "A) RJTT B) 2604011430 C) 2604292100\n"
        "D) 01 04-06 08 11-13 15 18-20 22 25-27 29 1430/2100\n"
        "E) TWY A1,A2,A5,A7,A8,A10,A12,A13,L5,L10,L12 CLSD DUE TO MAINT\n"
        "USEnrouteNavigationNOTAMs\n"
        "NAVIGATION\n"
        "GUM 04/059 GUM NAV ILS RWY 06L U/S 2604192200-2604200300\n"
    )
    notams = _parse_foreflight(body)

    std = notams["E1807/26 NOTAMN"]
    assert std.e == "TWY A1,A2,A5,A7,A8,A10,A12,A13,L5,L10,L12 CLSD DUE TO MAINT"

    gum = notams["GUM 04/059"]
    assert gum.title == "NAVIGATION"
    assert gum.e == "GUM NAV ILS RWY 06L U/S"
    assert gum.b == "2604192200"
    assert gum.c == "2604200300"


def test_alternate_line_terminates_std_notam_block() -> None:
    body = (
        "RUNWAY CLOSED\n"
        "C0481/26 NOTAMN\n"
        "Q) YBBB/QMXLC/IV/BO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604191200 C) 2604191900\n"
        "E) RWY 01 CLSD\n"
        "Alternate1 YBLN-Busselton\n"
        "OTHER NOTAM\n"
        "C0478/26 NOTAMN\n"
        "Q) YBBB/QFAHX/IV/NBO/A/000/999/2723S15307E005\n"
        "A) YBBN\n"
        "B) 2604170011 C) 2604220748\n"
        "E) INCREASED BIRD HAZARD\n"
    )
    notams = _parse_foreflight(body)
    assert notams["C0481/26 NOTAMN"].e == "RWY 01 CLSD"
    assert notams["C0478/26 NOTAMN"].title == "OTHER NOTAM"


# --- NAIPS NOTAMs ---


def test_section_header_sets_a_and_year_expansion() -> None:
    body = (
        "AUSTRALIA GEN (YBBB/YMMM)\n"
        "G5/26\n"
        "DESIGNATED AIRSPACE HANDBOOK (DAH) AND AIP CHARTS EFFECTIVE 27\n"
        "NOVEMBER 2025 AIRAC AMD\n"
        "FROM 02 180155 TO PERM\n"
    )
    notam = _parse_naips(body)["G5/26"]
    assert notam.a == "YBBB/YMMM"
    assert notam.q is None
    assert notam.title is None
    assert notam.b == "2602180155"
    assert notam.c == "PERM"
    assert notam.e == (
        "DESIGNATED AIRSPACE HANDBOOK (DAH) AND AIP CHARTS EFFECTIVE 27"
        "{\\n} NOVEMBER 2025 AIRAC AMD"
    )


def test_last_bracket_is_icao_and_fg_bc_d_detected() -> None:
    body = (
        "RICHMOND (NSW) (YSRI)\n"
        "F2011/26\n"
        "UA OPS WILL TAKE PLACE WI 3NM RADIUS OF ARP\n"
        "SFC TO 400FT AGL\n"
        "FROM 06 010610 TO 08 280000\n"
        "HJ\n"
    )
    notam = _parse_naips(body)["F2011/26"]
    assert notam.a == "YSRI"
    assert notam.f == "SFC"
    assert notam.g == "400FT AGL"
    assert notam.b == "2606010610"
    assert notam.c == "2608280000"
    assert notam.d == "HJ"


def test_replace_id_and_est_expiry() -> None:
    body = (
        "SYDNEY (YSSY)\n"
        "J2256/26 REPLACE J2071/26\n"
        "RWY 14/32 WIP\n"
        "FROM 05 170649 TO 06 082030 EST\n"
        "DAILY 0830-2030\n"
    )
    notam = _parse_naips(body)["J2256/26 REPLACE J2071/26"]
    assert notam.a == "YSSY"
    assert notam.c == "2606082030 EST"
    assert notam.d == "DAILY 0830-2030"


def test_d_field_collects_all_lines_after_bc_until_next_id() -> None:
    body = (
        "RICHMOND (NSW) (YSRI)\n"
        "F1717/26 REPLACE F784/26\n"
        "AIP DEP AND APCH (DAP) AMD\n"
        "FROM 05 070227 TO 06 301300 EST\n"
        "MON-SAT 1945-1300\n"
        "F1583/26\n"
        "TACAN 'RIC' 110.7/44X PILOT MNT\n"
        "FROM 04 260011 TO 06 250000 EST\n"
    )
    notam = _parse_naips(body)["F1717/26 REPLACE F784/26"]
    assert notam.d == "MON-SAT 1945-1300"
    assert notam.e == "AIP DEP AND APCH (DAP) AMD"


def test_d_field_supports_free_text_and_multiline_schedules() -> None:
    body = (
        "TINDAL (YPTN)\n"
        "L459/26\n"
        "ATS AND 'RIX' AIRSPACE SUBJ TO RESTRICTIONS\n"
        "SUBJ TO SHORT NOTICE ACTIVATION/DEACTIVATION DUE OPERATIONAL\n"
        "RESTRICTIONS. FOR KNOWN MILITARY ARRIVALS AND DEPARTURES ONLY.\n"
        "FROM 05 092200 TO 08 020830\n"
        "SAT, SUN, PUBLIC HOLIDAY 2200-0830\n"
        "J2544/26\n"
        "RWY THR DATA AMD\n"
        "FROM 06 020238 TO PERM\n"
    )
    notam = _parse_naips(body)["L459/26"]
    assert notam.d == "SAT, SUN, PUBLIC HOLIDAY 2200-0830"
    assert notam.e == (
        "ATS AND 'RIX' AIRSPACE SUBJ TO RESTRICTIONS"
        "{\\n} SUBJ TO SHORT NOTICE ACTIVATION/DEACTIVATION DUE OPERATIONAL"
        "{\\n} RESTRICTIONS. FOR KNOWN MILITARY ARRIVALS AND DEPARTURES ONLY."
    )


def test_d_field_stops_at_group_header() -> None:
    body = (
        "AUSTRALIA GEN (YBBB/YMMM)\n"
        "G5/26\n"
        "DESIGNATED AIRSPACE HANDBOOK (DAH) AND AIP CHARTS EFFECTIVE 27\n"
        "FROM 02 180155 TO PERM\n"
        "SYDNEY (YSSY)\n"
        "H4506/26 REPLACE H4378/26\n"
        "OBSTACLE CRANES\n"
        "FROM 06 040456 TO 06 300000 EST\n"
    )
    notam = _parse_naips(body)["G5/26"]
    assert notam.d is None
    assert _parse_naips(body)["H4506/26 REPLACE H4378/26"].a == "YSSY"


def test_d_field_null_when_bc_immediately_followed_by_next_id() -> None:
    body = (
        "SYDNEY (YSSY)\n"
        "H3992/26\n"
        "RWY 34L NOT TO STD\n"
        "FROM 05 180442 TO 06 300000 EST\n"
        "H3991/26\n"
        "RWY 34R NOT TO STD\n"
        "FROM 05 180440 TO 06 300000 EST\n"
    )
    notam = _parse_naips(body)["H3992/26"]
    assert notam.d is None
    assert notam.e == "RWY 34L NOT TO STD"


# --- OzRunways NOTAMs ---


def test_ozrunways_id_strips_stars_and_sets_a() -> None:
    body = (
        "YPJT - C124/26 ★☆☆☆☆\n"
        "8 OBST TOWER CRANES (LIT) 385FT AMSL ERECTED\n"
        "FROM 05 052300 TO 07 310900\n"
    )
    notam = _parse_ozrunways(body)["C124/26"]
    assert notam.a == "YPJT"
    assert notam.b == "2605052300"
    assert notam.c == "2607310900"
    assert notam.d is None


def test_ozrunways_replace_id_and_hj_d_field() -> None:
    body = (
        "YPPH - C373/26 REPLACE C113/26 ★★★☆☆\n"
        "LOC 'IGD' 109.5 RWY 21 SUBJ TO INTRP\n"
        "FROM 05 150339 TO 07 151000 EST\n"
        "HJ\n"
    )
    notam = _parse_ozrunways(body)["C373/26 REPLACE C113/26"]
    assert notam.a == "YPPH"
    assert notam.c == "2607151000 EST"
    assert notam.d == "HJ"


def test_ozrunways_schedule_d_line() -> None:
    body = (
        "YPPH - C412/26 ★★★☆☆\n"
        "LINK 8 CL LGT U/S\n"
        "FROM 06 082300 TO 06 100800\n"
        "DAILY 2300-0800\n"
    )
    notam = _parse_ozrunways(body)["C412/26"]
    assert notam.d == "DAILY 2300-0800"


def test_ozrunways_expanded_validity_windows_go_to_d_not_bc() -> None:
    body = (
        "PEX - C1141/26 REPLACE C1135/26 ★★★☆☆\n"
        "R153A ACT (RA2) DUE MIL FLYING\n"
        "SFC TO 2000FT AMSL\n"
        "FROM 06 090000 TO 06 120900\n"
        "2606090000 TO 2606090900\n"
        "2606100000 TO 2606100900\n"
        "2606110000 TO 2606110900\n"
        "2606120000 TO 2606120900\n"
    )
    notam = _parse_ozrunways(body)["C1141/26 REPLACE C1135/26"]
    assert notam.a == "PEX"
    assert notam.b == "2606090000"
    assert notam.c == "2606120900"
    assert notam.f == "SFC"
    assert notam.g == "2000FT AMSL"
    assert notam.d == (
        "2606090000 TO 2606090900"
        f"{E_JOIN}2606100000 TO 2606100900"
        f"{E_JOIN}2606110000 TO 2606110900"
        f"{E_JOIN}2606120000 TO 2606120900"
    )


def test_ozrunways_perm_expiry() -> None:
    body = (
        "YMEK - C33/26 ★☆☆☆☆\n"
        "DECLARED DISTANCE AND GRADIENT CHANGES\n"
        "FROM 05 080808 TO PERM\n"
    )
    notam = _parse_ozrunways(body)["C33/26"]
    assert notam.c == "PERM"


def test_strip_ozrunways_artifacts_removes_footers() -> None:
    lines = [
        "FROM 06 082300 TO 06 100800",
        "OzRunways 10 Jun 2026 at 14:48",
        "YPPH - C412/26 ★★★☆☆",
        "LINK 8 CL LGT U/S",
        "FROM 06 090000 TO 06 120900",
        "8:37 AWST OzRunways 10 Jun 2026 at 14:48:37 AWST",
        "Runways 10 Jun 2026 at 14:48:37 AWST",
        "YPPH - C435/26 REPLACE C201/26 ★★★★★",
    ]
    assert _strip_ozrunways_artifacts(lines) == [
        "FROM 06 082300 TO 06 100800",
        "YPPH - C412/26 ★★★☆☆",
        "LINK 8 CL LGT U/S",
        "FROM 06 090000 TO 06 120900",
        "YPPH - C435/26 REPLACE C201/26 ★★★★★",
    ]
