from app.services.foreflight_notam_parser import parse_foreflight_notams

SECTION = "NOTAMs\nDeparture YBBN-Brisbane\n"


def _parse(body: str):
    notams = parse_foreflight_notams(SECTION + body)
    return {notam.notam_id: notam for notam in notams}


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
    notams = _parse(body)
    first = notams["C0481/26 NOTAMN"]
    assert first.title == "TAXIWAY CLOSED (NEW TODAY)"
    assert first.a == "YBBN"
    assert first.b == "2604191200"
    assert first.c == "2604191900"
    assert first.e == "TWY B2 CLSD {\\n} TWY F2 BTN TWY B AND G1 CLSD"
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
    notam = _parse(body)["J0880/26 NOTAMN"]
    assert notam.a == "RJTT"
    assert notam.e == "OBST LGT U/S {\\n} (CHUO-KU IN TOKYO)"
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
    notams = _parse(body)

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
