from app.services.naips_notam_parser import parse_naips_notams

HEADER = "0521 UTC 05/06/26 AIRSERVICES AUSTRALIA\nNOTAM INFORMATION\n-----------------\n"


def _parse(body: str):
    notams = parse_naips_notams(HEADER + body)
    return {notam.notam_id: notam for notam in notams}


def test_section_header_sets_a_and_year_expansion() -> None:
    body = (
        "AUSTRALIA GEN (YBBB/YMMM)\n"
        "G5/26\n"
        "DESIGNATED AIRSPACE HANDBOOK (DAH) AND AIP CHARTS EFFECTIVE 27\n"
        "NOVEMBER 2025 AIRAC AMD\n"
        "FROM 02 180155 TO PERM\n"
    )
    notam = _parse(body)["G5/26"]
    assert notam.a == "YBBB/YMMM"
    assert notam.q is None
    assert notam.title is None
    assert notam.b == "2602180155"
    assert notam.c == "PERM"
    assert notam.e == (
        "DESIGNATED AIRSPACE HANDBOOK (DAH) AND AIP CHARTS EFFECTIVE 27 "
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
    notam = _parse(body)["F2011/26"]
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
    notam = _parse(body)["J2256/26 REPLACE J2071/26"]
    assert notam.a == "YSSY"
    assert notam.c == "2606082030 EST"
    assert notam.d == "DAILY 0830-2030"
