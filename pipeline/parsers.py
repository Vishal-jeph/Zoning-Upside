"""Parsers for NJ MOD-IV tax-record text fields (M4_Bldg_Desc, M4_Lot_Desc, etc.).

These fields are free text typed by assessors, so parsing is pattern-based and
conservative: when a value doesn't match a known pattern we return
parse_status="unparsed" instead of guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

def _text(v) -> str:
    """Normalise a raw field: None/NaN -> '', else stripped upper-case string."""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v).strip().upper()


# ---------------------------------------------------------------- building description
# Material codes. Only F and B have meanings confirmed in the project brief; other codes
# (CB, ST, B&S, S, ...) are kept raw and labelled "unknown" until verified.
MATERIAL_NAMES = {"F": "Frame", "B": "Brick"}
# Tag meanings confirmed in the brief. Others (H, BA, X, BX, FX, DK, ...) stay raw.
TAG_NAMES = {"G": "Garage", "GUTTED": "Gutted", "WIP": "Work in progress"}

# Condo unit descriptions: "2BR-DECK", "2BR/1BA", "3BDRM UNIT", "STUDIO", "PARKING SPACE", "PS", "RETAIL"...
CONDO_UNIT_RE = re.compile(
    r"^(\d+\s*(BR|BDRM|BED)|BR\b|BDRM|STUDIO|PARKING\s*(SPACE|SPOT)|PS\b|PS\s*#|LAND-PILOT)"
)
# Descriptions that mean "no building": vacant, fenced or paved land ("WIP" = work in progress).
VACANT_RE = re.compile(r"^(VACAN?TE?( LAND| LOT)?|LAND|PAVED LOT|PARKING (LOT|AREA)|FENCED LOT)([- ]WIP)?$")
# Non-building uses with no usable story count: parks, streets, rail, telecom sites, etc.
NONRES_KEYWORDS_RE = re.compile(
    r"^(PARK\b|PLAYGROUND|ROW STREETS|STREET|DRIVEWAY|MAIN STEM|TELE?COMM?|GAS STATION|CANOPY|LAND[- ]CLASS)"
)

# First segment of a building: stories + material, e.g. "3F", "4B", "3,4B" (mixed 3 & 4 stories),
# "4/5CB", "2B&S", "3ST&CB", "3 CB". Stories may be a decimal ("2.5F").
STORIES_MATERIAL_RE = re.compile(r"^(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d+(?:\.\d+)?))?\s*([A-Z][A-Z&]*)$")
UNITS_RE = re.compile(r"^(\d+)U$")          # "2U" -> 2 residential units
COMM_UNITS_RE = re.compile(r"^(\d+)C$")     # "1C" -> 1 commercial unit (store front)
# Letters after a leading number that are unit counts, not a building material ("15U-1C", "10 UNITS").
NOT_MATERIAL = {"U", "UNIT", "UNITS", "C", "COM", "BR"}


@dataclass
class BldgParse:
    parse_status: str                      # ok | condo_unit | non_residential | unparsed
    existing_stories: float | None = None  # tallest building on the record
    existing_stories_min: float | None = None
    material_code: str | None = None
    material: str | None = None
    existing_units: int | None = None      # residential units ("#U"), summed over buildings
    commercial_units: int | None = None    # "#C" segments
    building_count: int | None = None
    tags: list[str] = field(default_factory=list)
    is_vacant: bool = False
    is_common_element: bool = False


def _split_buildings(s: str) -> list[str]:
    """Split a multi-building description on "/".

    '3B-2U-C/3B-2U' -> ['3B-2U-C', '3B-2U']   (new building: piece starts with stories+material)
    '4/5CB-2U-H'    -> ['4/5CB-2U-H']          (4-to-5-story range, kept whole)
    '4B-4U-H-BA/G'  -> ['4B-4U-H-BA-G']        (anything else after "/" is another tag)
    """
    out: list[str] = []
    for p in (x.strip() for x in s.split("/")):
        if not p:
            continue
        if not out:
            out.append(p)
        elif re.fullmatch(r"\d+(\.\d+)?", out[-1]):
            out[-1] = out[-1] + "/" + p
        elif re.match(r"\d+(\.\d+)?\s*[A-Z]", p):
            out.append(p)
        else:
            out[-1] = out[-1] + "-" + p
    return out


def parse_bldg_desc(raw: str | None) -> BldgParse:
    s = _text(raw)
    if not s:
        return BldgParse("unparsed")
    if s == "COMMON ELEMENT":  # condo master record for the building's common areas
        return BldgParse("condo_unit", is_common_element=True, tags=["COMMON_ELEMENT"])
    if CONDO_UNIT_RE.match(s) or s in ("RETAIL", "COMMERCIAL", "PARKING", "STORAGE"):
        return BldgParse("condo_unit")
    s = re.sub(r"\s+1/2(?=[A-Z])", ".5", s)  # "4 1/2B" = 4.5 stories
    s = re.sub(r"(?<![\d.])(\d)1/2(?=[A-Z])", r"\1.5", s)  # "21/2CB" = 2 1/2 stories (not 21)
    if NONRES_KEYWORDS_RE.match(s):
        return BldgParse("non_residential", tags=[s])
    if VACANT_RE.match(s):
        # Explicitly vacant: zero stories / units is a fact here, not a default.
        return BldgParse("non_residential", existing_stories=0, existing_stories_min=0,
                         existing_units=0, building_count=0, is_vacant=True, tags=[s])

    stories, stories_min, units, comm, tags, materials = [], [], 0, 0, [], []
    saw_units = False
    for b in _split_buildings(s):
        segs = [x.strip() for x in b.split("-") if x.strip()]
        # Some records write stories after other text ("2,3B-H-2U"); first seg must be stories+material.
        if not segs:
            return BldgParse("unparsed")
        # "3B,4B" or "4B&5B" = several structures in one segment ("B&S" alone is a material).
        heads = re.split(r"(?<=[A-Z])[,&](?=\d)", segs[0])
        for head in heads:
            m = STORIES_MATERIAL_RE.match(head.strip())
            if not m or m.group(3) in NOT_MATERIAL:
                return BldgParse("unparsed")
            hi = float(m.group(2) or m.group(1))
            lo = float(m.group(1))
            stories.append(max(hi, lo))
            stories_min.append(min(hi, lo))
            materials.append(m.group(3))
        for seg in segs[1:]:
            if um := UNITS_RE.match(seg):
                units += int(um.group(1))
                saw_units = True
            elif cm := COMM_UNITS_RE.match(seg):
                comm += int(cm.group(1))
            else:
                tags.append(seg)

    mat = materials[0] if len(set(materials)) == 1 else "MIXED"
    result = BldgParse(
        parse_status="ok" if saw_units else "non_residential",
        existing_stories=max(stories),
        existing_stories_min=min(stories_min),
        material_code=mat,
        material=MATERIAL_NAMES.get(mat, "unknown"),
        existing_units=units if saw_units else None,
        commercial_units=comm or None,
        building_count=len(stories),
        tags=tags,
    )
    return result


# ---------------------------------------------------------------- lot description
SQFT_PER_ACRE = 43_560

DIMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)")
AREA_SF_RE = re.compile(r"([\d,]*\.?\d+)\s*(?:SQ\.?\s*FT|SQ\s*SF|SQ|SF)\b")
ACRES_RE = re.compile(r"(\d*\.?\d+)\s*(?:ACRES?|ACS?)\b")
# Condo-unit lot descriptions: ".0394-1300 SF" (ownership share - unit sq ft), ".05", "CONDOMINIUM .0123"
CONDO_LOT_RE = re.compile(r"^(\.\d+|CONDOMINIUM|\d+(\.\d+)?-\d+(\s*SF)?$|\d+\s*SF-\.\d+)")


@dataclass
class LotParse:
    parse_status: str                   # ok | condo_unit | unparsed
    lot_width_ft: float | None = None   # frontage of the first (or only) rectangle
    lot_depth_ft: float | None = None
    lot_area_sqft: float | None = None
    irregular: bool = False
    average: bool = False               # "AVG": dimensions are averages of an uneven lot
    corner: bool = False
    multi_part: bool = False            # several rectangles, e.g. "25X100&25X50"
    area_source: str | None = None      # dims | stated_sqft | stated_acres


def parse_lot_desc(raw: str | None) -> LotParse:
    s = _text(raw)
    if not s:
        return LotParse("unparsed")
    if CONDO_LOT_RE.match(s) and not DIMS_RE.search(s) and not ACRES_RE.search(s):
        return LotParse("condo_unit")

    flags = dict(
        irregular=bool(re.search(r"IRR|TRI", s)),
        average=bool(re.search(r"AVG|\bAV\b", s)),
        corner=bool(re.search(r"COR|CR\b|\dC\b", s)),
    )
    dims = [(float(w), float(d)) for w, d in DIMS_RE.findall(s)]
    # An explicitly stated area wins over computed width x depth.
    if (m := AREA_SF_RE.search(s)) and not DIMS_RE.search(s[m.start():m.end()]):
        area = float(m.group(1).replace(",", ""))
        w, d = dims[0] if dims else (None, None)
        return LotParse("ok", w, d, area, area_source="stated_sqft", multi_part=len(dims) > 1, **flags)
    if m := ACRES_RE.search(s):
        area = float(m.group(1)) * SQFT_PER_ACRE  # 1 acre = 43,560 sq ft
        return LotParse("ok", lot_area_sqft=round(area), area_source="stated_acres", **flags)
    if dims:
        area = sum(w * d for w, d in dims)  # multi-part lots: sum of the rectangles
        return LotParse("ok", dims[0][0], dims[0][1], round(area, 1),
                        multi_part=len(dims) > 1, area_source="dims", **flags)
    return LotParse("unparsed")


# ---------------------------------------------------------------- small helpers
def to_int(v) -> int | None:
    try:
        s = str(v).replace(",", "").strip()
        return int(float(s)) if s else None
    except (TypeError, ValueError):
        return None


def parse_year(v) -> int | None:
    y = to_int(v)
    return y if y and 1700 <= y <= date.today().year + 1 else None


def parse_sale_date(v) -> str | None:
    """'05/20/21' -> '2021-05-20'. Two-digit years above the current year are 19xx."""
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", _text(v))
    if not m:
        return None
    mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yr < 100:
        yr += 2000 if yr <= date.today().year % 100 else 1900
    try:
        return date(yr, mo, dy).isoformat()
    except ValueError:
        return None


def parse_additional_lots(v: str | None) -> tuple[list[str], bool]:
    """'2,3,4,30' / '9-26,37' -> lot numbers in the same block.

    Returns (lots, fully_resolved). Text such as 'L15&B139.01L1' (other blocks),
    'NEW CONDO' or 'PS #21,22' is not a lot list and is reported unresolved.
    """
    s = _text(v)
    if not s:
        return [], True
    if not re.fullmatch(r"[\d.,\s-]+", s):
        return [], False
    lots: list[str] = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if m := re.fullmatch(r"(\d+)-(\d+)", tok):
            a, b = int(m.group(1)), int(m.group(2))
            if b < a or b - a > 200:
                return lots, False
            lots += [str(i) for i in range(a, b + 1)]
        elif re.fullmatch(r"\d+(\.\d+)?", tok):
            lots.append(tok)
        else:
            return lots, False
    return lots, True


def norm_lot(lot: str) -> str:
    """'1.00' / '01' -> '1'; '1.01' stays. Used to match lot numbers across fields."""
    try:
        f = float(lot)
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return _text(lot)


def norm_zone(z: str | None) -> str:
    """Compare zone codes across sources: 'I-1 (W)' and 'I-1W' -> 'I1W'."""
    return re.sub(r"[^A-Z0-9]", "", _text(z))
