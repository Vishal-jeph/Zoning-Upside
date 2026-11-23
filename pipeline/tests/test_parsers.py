"""Parser tests: examples from the project brief plus real values observed in the Hoboken data."""
import pytest

from pipeline.parsers import (
    parse_additional_lots, parse_bldg_desc, parse_lot_desc, parse_sale_date, parse_year, norm_zone,
)

# (raw, status, stories, stories_min, material_code, units, commercial_units, building_count, tags)
BLDG_CASES = [
    # --- examples from the brief
    ("3F-2U-G", "ok", 3, 3, "F", 2, None, 1, ["G"]),
    ("4B-2U-G", "ok", 4, 4, "B", 2, None, 1, ["G"]),
    ("2F-2U-H-BA", "ok", 2, 2, "F", 2, None, 1, ["H", "BA"]),
    ("5B-GUTTED-WIP", "non_residential", 5, 5, "B", None, None, 1, ["GUTTED", "WIP"]),
    # --- real values from the parcel data
    ("3B-2U-2C-H", "ok", 3, 3, "B", 2, 2, 1, ["H"]),
    ("2.5B-2U-BA", "ok", 2.5, 2.5, "B", 2, None, 1, ["BA"]),
    ("2B-2C-H-HW", "non_residential", 2, 2, "B", None, 2, 1, ["H", "HW"]),
    ("2B-1C-1U", "ok", 2, 2, "B", 1, 1, 1, []),
    ("12B-115U-4C-G", "ok", 12, 12, "B", 115, 4, 1, ["G"]),
    ("5B-6U-X-H-BA", "ok", 5, 5, "B", 6, None, 1, ["X", "H", "BA"]),
    ("3B-4U-H-BA/2B-G", "ok", 3, 2, "B", 4, None, 2, ["H", "BA", "G"]),
    ("4B-2U-2BX-H-BA", "ok", 4, 4, "B", 2, None, 1, ["2BX", "H", "BA"]),
    ("4B-1C-3U-B", "ok", 4, 4, "B", 3, 1, 1, ["B"]),
    ("4B-X-4U-(LE)", "ok", 4, 4, "B", 4, None, 1, ["X", "(LE)"]),
    ("4F-4U-1C", "ok", 4, 4, "F", 4, 1, 1, []),
    ("1B-RETAIL", "non_residential", 1, 1, "B", None, None, 1, ["RETAIL"]),
    ("2CB-1C-2U", "ok", 2, 2, "CB", 2, 1, 1, []),
    ("5B-21U-H-BA", "ok", 5, 5, "B", 21, None, 1, ["H", "BA"]),
    ("4B-4U-1C-X-H/G", "ok", 4, 4, "B", 4, 1, 1, ["X", "H", "G"]),
    ("3B-2U-C/3B-2U", "ok", 3, 3, "B", 4, None, 2, ["C"]),          # two buildings: units summed
    ("3F-2U/2F-1U/GAR", "ok", 3, 2, "F", 3, None, 2, ["GAR"]),
    ("4/5CB-2U-H", "ok", 5, 4, "CB", 2, None, 1, ["H"]),             # 4-to-5-story range
    ("3,4B-2U-H-BA", "ok", 4, 3, "B", 2, None, 1, ["H", "BA"]),       # mixed 3 and 4 stories
    ("4B&5B-14U-H", "ok", 5, 4, "B", 14, None, 2, ["H"]),
    ("2,5B&2B-37U-H", "ok", 5, 2, "B", 37, None, 2, ["H"]),
    ("4 1/2B-10U-BA", "ok", 4.5, 4.5, "B", 10, None, 1, ["BA"]),
    ("2B&S-3U-H", "ok", 2, 2, "B&S", 3, None, 1, ["H"]),             # "B&S" is one material code
    ("2CB-OFF/ STREET", "non_residential", 2, 2, "CB", None, None, 1, ["OFF", "STREET"]),
    ("1B,5B-I-H", "non_residential", 5, 1, "B", None, None, 2, ["I", "H"]),
]


@pytest.mark.parametrize("raw,status,stories,smin,mat,units,comm,nb,tags", BLDG_CASES)
def test_bldg_desc(raw, status, stories, smin, mat, units, comm, nb, tags):
    r = parse_bldg_desc(raw)
    assert r.parse_status == status
    assert r.existing_stories == stories
    assert r.existing_stories_min == smin
    assert r.material_code == mat
    assert r.existing_units == units
    assert r.commercial_units == comm
    assert r.building_count == nb
    assert r.tags == tags


@pytest.mark.parametrize("raw", [
    "2BR-DECK", "2BR-DPLX-PS#37", "RETAIL", "2BR-TERRACE", "1BR", "2BR/2BA", "3BDRM UNIT",
    "STUDIO", "PARKING SPACE", "PS", "LAND-PILOT", "COMMON ELEMENT",
])
def test_condo_units(raw):
    assert parse_bldg_desc(raw).parse_status == "condo_unit"


def test_common_element_flag():
    assert parse_bldg_desc("COMMON ELEMENT").is_common_element


@pytest.mark.parametrize("raw", ["VACANT LAND", "LAND", "PAVED LOT", "PARKING LOT", "VACANT LAND WIP", "FENCED LOT"])
def test_vacant_is_zero_not_missing(raw):
    r = parse_bldg_desc(raw)
    assert r.parse_status == "non_residential" and r.is_vacant
    assert r.existing_stories == 0 and r.existing_units == 0


@pytest.mark.parametrize("raw", ["PARK", "ROW STREETS", "MAIN STEM CL 1", "TELECOM ANTENNA"])
def test_nonres_keywords_have_no_stories(raw):
    r = parse_bldg_desc(raw)
    assert r.parse_status == "non_residential" and r.existing_stories is None


@pytest.mark.parametrize("raw", [None, "", float("nan"), "3B TEMPLE/CNTR", "1C B I"])
def test_bldg_unparsed(raw):
    assert parse_bldg_desc(raw).parse_status == "unparsed"


# (raw, status, width, depth, area, irregular, average, corner, multi_part, area_source)
LOT_CASES = [
    # --- examples from the brief
    ("25 X 100", "ok", 25, 100, 2500, False, False, False, False, "dims"),
    ("25 X 113 AVG.", "ok", 25, 113, 2825, False, True, False, False, "dims"),
    ("22 X 50 IRREG.", "ok", 22, 50, 1100, True, False, False, False, "dims"),
    ("25X75CORNER", "ok", 25, 75, 1875, False, False, True, False, "dims"),
    ("368X200 AVG", "ok", 368, 200, 73600, False, True, False, False, "dims"),
    # --- real values from the parcel data
    ("21.59X100", "ok", 21.59, 100, 2159, False, False, False, False, "dims"),
    ("117460 SQ FT", "ok", None, None, 117460, False, False, False, False, "stated_sqft"),
    ("20.67X45.17 IRR", "ok", 20.67, 45.17, 933.7, True, False, False, False, "dims"),
    ("20X110 IRR", "ok", 20, 110, 2200, True, False, False, False, "dims"),
    ("24.12 X 104", "ok", 24.12, 104, 2508.5, False, False, False, False, "dims"),
    ("11246SQ FT", "ok", None, None, 11246, False, False, False, False, "stated_sqft"),
    ("200X150&25X100", "ok", 200, 150, 32500, False, False, False, True, "dims"),
    ("28X99.73CORNER", "ok", 28, 99.73, 2792.4, False, False, True, False, "dims"),
    ("100X100 CORNER", "ok", 100, 100, 10000, False, False, True, False, "dims"),
    ("1.862 ACRES", "ok", None, None, 81109, False, False, False, False, "stated_acres"),  # x 43,560
    (".12 ACRES", "ok", None, None, 5227, False, False, False, False, "stated_acres"),
    ("10,000 SF", "ok", None, None, 10000, False, False, False, False, "stated_sqft"),
    ("35000 SQ FT", "ok", None, None, 35000, False, False, False, False, "stated_sqft"),
    ("50X100 COR", "ok", 50, 100, 5000, False, False, True, False, "dims"),
    ("76.50X91.50", "ok", 76.5, 91.5, 6999.8, False, False, False, False, "dims"),
]


@pytest.mark.parametrize("raw,status,w,d,area,irr,avg,cor,mp,src", LOT_CASES)
def test_lot_desc(raw, status, w, d, area, irr, avg, cor, mp, src):
    r = parse_lot_desc(raw)
    assert r.parse_status == status
    assert r.lot_width_ft == w and r.lot_depth_ft == d
    assert r.lot_area_sqft == pytest.approx(area, abs=0.1)
    assert (r.irregular, r.average, r.corner, r.multi_part) == (irr, avg, cor, mp)
    assert r.area_source == src


@pytest.mark.parametrize("raw", [".0394-1300 SF", ".05-1652 SF", ".0394", "CONDOMINIUM .0123"])
def test_condo_lot_desc(raw):
    r = parse_lot_desc(raw)
    assert r.parse_status == "condo_unit" and r.lot_area_sqft is None


@pytest.mark.parametrize("raw", [None, "", "88 AVG.X25 COR."])
def test_lot_unparsed(raw):
    assert parse_lot_desc(raw).parse_status == "unparsed"


def test_additional_lots():
    assert parse_additional_lots("2,3,4,30") == (["2", "3", "4", "30"], True)
    assert parse_additional_lots("9-11,37") == (["9", "10", "11", "37"], True)
    assert parse_additional_lots("L15&B139.01L1")[1] is False
    assert parse_additional_lots("NEW CONDO")[1] is False
    assert parse_additional_lots(None) == ([], True)


def test_small_helpers():
    assert parse_sale_date("05/20/21") == "2021-05-20"
    assert parse_sale_date("06/01/96") == "1996-06-01"
    assert parse_sale_date("") is None
    assert parse_year("1901") == 1901 and parse_year("") is None and parse_year("0") is None
    assert norm_zone("I-1 (W)") == norm_zone("I-1W") == "I1W"
    assert norm_zone("W (N)") == norm_zone("W-N")
