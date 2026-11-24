"""Phase 3: allowed vs existing, upside score, and the static files for the web app.

    python -m pipeline.potential

Inputs:  data/processed/sites.parquet, data/rules/hoboken_rules.json (approved zones only)
Outputs: data/processed/potential.parquet, data/processed/potential_report.md,
         web/public/data/sites.geojson, web/public/data/rules.json

Every allowed number comes from an approved rule (with its quote). The only non-rule inputs are
the method settings below, which are shown on the site as assumptions.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date

import geopandas as gpd
import pandas as pd

from . import config
from .rules_schema import SEEDS

# ---------------------------------------------------------------- method settings (shown as assumptions)
# Legal minimum floor-to-floor when the zone states none (sets the theoretical maximum floors).
DEFAULT_FLOOR_TO_FLOOR_FT = 10.0
# Copied from config so they can be overridden in one place (and in tests / what-if runs).
TYPICAL_FLOOR_TO_FLOOR_FT = config.TYPICAL_FLOOR_TO_FLOOR_FT
LARGE_SITE_SQFT = config.LARGE_SITE_SQFT
BUILDING_DETECTED_COVERAGE_PCT = config.BUILDING_DETECTED_COVERAGE_PCT
FLOORS_DISAGREE_MIN = config.FLOORS_DISAGREE_MIN
# Tax building-description tags that suggest construction/renovation is already under way.
UNDER_CONSTRUCTION_RE = r"\bWIP\b|GUTTED|\bGUT\b|NEW ?CONST|UNDER ?CONST|\bU/C\b|\bDEMO"
# Construction-like words that are NOT treated as under construction; logged for human review.
SIMILAR_TAG_RE = r"CONST|RENOV|REHAB|UNFIN|INCOMPL|PARTIAL|SHELL|PERMIT"
# "Rounding not stated" → round down, so we never overstate what is allowed.
DEFAULT_ROUNDING = "down"

# Upside score: positive parts add up to 95, penalties subtract. Final score clipped to 0–100.
SCORE_WEIGHTS = {
    "unused_units": 35,      # full points at UNUSED_UNITS_CAP or more
    "unused_stories": 20,    # full points at UNUSED_STORIES_CAP or more
    "lot_area": 10,          # full points at LOT_AREA_CAP_SQFT or more
    "land_value_share": 15,  # full points when the building is worth ~0% of total value, none at ≥50%
    "old_building": 5,       # built before OLD_BUILDING_YEAR
    "vacant_land": 10,
    "historic": -10,
    "redev_agreement": -25,
    "nonconforming": -10,
    "irregular_lot": -5,
    "exempt": -30,              # government / school / religious / nonprofit owner: rarely for sale
    "under_construction": -40,  # "WIP", "GUTTED"… in the tax description: someone may already be building
    "building_detected": -40,   # tax says vacant, but building footprints cover the lot
}
UNUSED_UNITS_CAP = 10
UNUSED_STORIES_CAP = 3
LOT_AREA_CAP_SQFT = 5000
OLD_BUILDING_YEAR = 1940

WEB_DATA = config.ROOT / "web" / "public" / "data"
SIMPLIFY_TOLERANCE_FT = 0.5


# ---------------------------------------------------------------- allowed stories / units
def _val(fields: dict, key: str):
    v = (fields.get(key) or {}).get("value")
    return None if v in ("", None) else v


def effective_limits(fields: dict) -> dict:
    """Height/story limits used for residential or mixed-use redevelopment.
    Order: residential/mixed-use limits → limits stated for all buildings → commercial limits (fallback,
    flagged). Each piece is picked independently, so a zone may state a residential height but a
    general story limit."""
    def pick(base):
        for suffix, basis in (("_residential", "residential/mixed-use"), ("", "all buildings"),
                              ("_commercial", "commercial (no residential limit stated)")):
            v = _val(fields, base + suffix)
            if v is not None:
                return v, basis
        return None, None
    h, hb = pick("max_height_ft")
    st, sb = pick("max_stories")
    return {"max_height_ft": h, "max_stories": st, "height_basis": hb, "stories_basis": sb,
            "commercial_fallback": "commercial" in (hb or "") or "commercial" in (sb or "")}


def allowed_stories(fields: dict) -> dict:
    """allowed floors, annotated with which building-type limits were used."""
    r = _allowed_stories_core(fields)
    lim = effective_limits(fields)
    r["limits_basis"] = lim["height_basis"] or lim["stories_basis"]
    r["commercial_fallback"] = lim["commercial_fallback"]
    if r["formula"] and lim["commercial_fallback"]:
        r["formula"] += (" Uses the zone's commercial limits because no residential/mixed-use limit is "
                         "stated in the approved rules.")
    return r


def _allowed_stories_core(fields: dict) -> dict:
    """Floors allowed. Returns `value` (used for upside and score) and `max_value` (theoretical legal
    maximum, used for the nonconforming check).

    - Zone states a story limit: the zone itself says that many floors fit, so value = max_value =
      min(story limit, floor(height ÷ legal minimum floor-to-floor)). A building must meet every stated
      limit, so the lower one binds.
    - Zone states only a height: max_value uses the legal minimum floor-to-floor; value uses a realistic
      floor-to-floor (TYPICAL_FLOOR_TO_FLOOR_FT), because real buildings rarely build at the minimum."""
    lim = effective_limits(fields)
    max_st, max_ft = lim["max_stories"], lim["max_height_ft"]
    ftf_rule = _val(fields, "min_floor_to_floor_ft")
    ftf = float(ftf_rule) if ftf_rule else DEFAULT_FLOOR_TO_FLOOR_FT
    ftf_basis = "zone minimum floor-to-floor" if ftf_rule else "assumed minimum floor-to-floor"
    from_height = math.floor(float(max_ft) / ftf) if max_ft else None

    if max_st is None and from_height is None:
        return {"value": None, "max_value": None, "formula": None,
                "note": "No height or story limit in the approved rules."}
    if max_st is not None and from_height is not None:
        value = min(float(max_st), from_height)
        binding = "story limit" if float(max_st) <= from_height else "height limit"
        formula = (f"min({_n(max_st)} stories, floor({_n(max_ft)} ft ÷ {_n(ftf)} ft {ftf_basis}) = {from_height})"
                   f" = {_n(value)} ({binding} binds)")
        return {"value": value, "max_value": value, "formula": formula, "note": None}
    if max_st is not None:
        return {"value": float(max_st), "max_value": float(max_st),
                "formula": f"{_n(max_st)} stories (stated limit)", "note": None}
    # Height only: realistic estimate, with the legal-minimum result as the theoretical maximum.
    typ = max(TYPICAL_FLOOR_TO_FLOOR_FT, ftf)
    realistic = math.floor(float(max_ft) / typ)
    formula = (f"floor({_n(max_ft)} ft ÷ {_n(typ)} ft realistic floor-to-floor) = {realistic}. Theoretical maximum: "
               f"floor({_n(max_ft)} ft ÷ {_n(ftf)} ft {ftf_basis}) = {from_height}. The zone sets no story limit.")
    return {"value": float(realistic), "max_value": float(from_height), "formula": formula, "note": None,
            "realistic_ftf": typ, "min_ftf": ftf}


def _round(x: float, how: str | None) -> int:
    how = how if how in ("nearest", "down", "up") else DEFAULT_ROUNDING
    if how == "nearest":
        return int(math.floor(x + 0.5))
    return int(math.ceil(x)) if how == "up" else int(math.floor(x))


def allowed_units(density: dict | None, lot_area: float | None) -> dict:
    if not density or density.get("type") in (None, "none"):
        return {"value": None, "formula": None,
                "note": "The approved rules give no numeric density for this zone (e.g. it refers to use "
                        "conditions in another section), so allowed units are not estimated."}
    if lot_area is None or not lot_area > 0:
        return {"value": None, "formula": None, "note": "Lot area unknown."}
    t = density["type"]
    rnd = density.get("rounding")
    rnd_txt = rnd if rnd in ("nearest", "down", "up") else f"{DEFAULT_ROUNDING}, as the rule does not say how to round"
    if t == "site_area_per_unit" and density.get("site_area_per_unit_sqft"):
        per = float(density["site_area_per_unit_sqft"])
        v = _round(lot_area / per, rnd)
        return {"value": v, "formula": f"{lot_area:,.0f} sq ft ÷ {per:,.0f} sq ft per unit = {lot_area / per:.2f} → "
                                       f"{v} rounded {rnd_txt}", "note": None}
    if t == "units_per_acre" and density.get("units_per_acre"):
        upa = float(density["units_per_acre"])
        raw = lot_area / 43560 * upa
        v = _round(raw, rnd)
        return {"value": v, "formula": f"{lot_area:,.0f} sq ft ÷ 43,560 × {upa:g} units/acre = {raw:.2f} → {v} "
                                       f"rounded {rnd_txt}", "note": None}
    if t == "max_units" and density.get("max_units"):
        v = int(density["max_units"])
        return {"value": v, "formula": f"{v} units (stated maximum)", "note": None}
    return {"value": None, "formula": None,
            "note": "The density rule could not be turned into a formula automatically; see the rule text."}


def _n(x) -> str:
    return f"{float(x):g}"


# ---------------------------------------------------------------- flags
# Flag levels:
#   warning: may change the decision → coloured badge in the table, "Things to check" in the drawer
#   note:    context that changes the calculation but applies widely → subtle grey badge in the table
#   info:    context only → drawer ("Good to know"), no table badge
INFO_FLAGS = {"flood", "below_min_lot"}
NOTE_FLAGS = {"floors_disagree"}


def site_flags(s: pd.Series, district: dict | None, zone: dict | None, nonconf: list[str],
               conflicts: list[str] | None = None, fp: dict | None = None, release: str | None = None,
               possible_master: bool = False) -> list[dict]:
    out = []

    def add(code: str, text: str, level: str | None = None):
        out.append({"code": code, "text": text,
                    "level": level or ("info" if code in INFO_FLAGS else "note" if code in NOTE_FLAGS else "warning")})

    if under_construction(s.bldg_desc):
        add("under_construction", f"Tax record shows “{s.bldg_desc}” — the site may already be under development; "
                                  "check permits and current photos.")
    if fp and building_detected(s, fp):
        add("building_detected", f"Building detected — tax record may be outdated: the tax record says "
                                 f"“{s.bldg_desc or 'no building'}”, but building footprints cover "
                                 f"{fp['footprint_coverage_pct']:.0f}% of the lot (Overture Maps, release {release}).")
    if possible_master:
        add("possible_condo_master", "Possible condo master lot: this land-only record shares its block and lot "
                                     "number with condo unit records, so it is likely the land under a condo "
                                     "building, not a separate buildable lot.")
    if s.is_exempt:
        add("exempt", "Tax-exempt owner (government/nonprofit/religious); rarely available to buy.")
    if s.has_redev_agreement:
        add("redev_agreement", f"A redevelopment agreement covers this site ({s.redev_agreement_name}): "
                               "a developer already has a deal with the City.")
    if s.in_historic_district:
        add("historic", f"In a historic district{f' ({s.historic_code})' if s.historic_code else ''}: changes need "
                        "Historic Preservation Commission review, and extra height rules may apply.")
    if pd.notna(s.lot_area_best_sqft) and s.lot_area_best_sqft >= LARGE_SITE_SQFT and district:
        add("large_site", f"Large site — density alone overstates potential ({s.lot_area_best_sqft:,.0f} sq ft): "
                          "parking, setbacks, open space and site plan review usually reduce the real unit count.")
    if zone and zone.get("needs_reapproval"):
        add("rule_pending", f"The {zone['label']} rules are being re-checked ({zone.get('reapproval_reason', '')}); "
                            "values may change after re-approval.")
    for c in conflicts or []:
        add("rule_conflict", c)
    if s.in_redev_area:
        add("redev_area", f"Inside {s.redev_area_name or 'a redevelopment area'} ({s.redev_area_kind or 'plan'}): "
                          "that plan's rules may replace or add to the zone rules.")
    if s.in_zoning_in_progress:
        add("zoning_in_progress", f"Rules are being changed here ({s.zoning_in_progress_name}).")
    if s.lot_irregular:
        add("irregular_lot", "Irregular lot shape: buildable area may be smaller than the lot area suggests.")
    if s.area_mismatch:
        add("area_mismatch", f"Tax-record lot area and mapped lot area disagree (ratio {s.lot_area_ratio:.2f}); "
                             f"using {s.lot_area_basis}.")
    if s.zone_split:
        add("zone_split", f"Lot crosses a zone boundary; {s.zone_share:.0%} is in {s.zone}.")
    if s.zone_mismatch:
        add("zone_mismatch", f"The tax record lists zone {s.tax_zone}; the zoning map says {s.zone}.")
    if zone and len(zone["districts"]) > 1:
        others = [d["name"] for d in zone["districts"] if d["name"]]
        add("subdistrict", f"This zone has a sub-district ({', '.join(others)}) with different rules; "
                           "check whether this lot is in it.")
    if nonconf:
        add("nonconforming", "Existing building already exceeds the zone limit (" + "; ".join(nonconf) +
            "): not an expansion opportunity.")
    if fp and (fd := floors_disagree(s, fp)):
        add("floors_disagree", f"Floors disagree: tax record says {_n(fd[0])}, building footprint data suggests "
                               f"{_n(fd[1])} ({fd[2]}). One of them may be outdated.")
    if s.in_flood_hazard_area:
        dfe = district is not None and _val(district["fields"], "height_measured_from") == "design_flood_elevation"
        abfe = f" (advisory base flood elevation {s.flood_abfe_ft:g} ft)" if pd.notna(s.flood_abfe_ft) else ""
        # Shown in the table (grey) only where it changes the calculation: height measured from the DFE.
        add("flood", f"In a FEMA flood zone {s.flood_zone_codes}{abfe}: ground floor elevation rules apply"
                     + ("; height is measured from the design flood elevation, not the ground." if dfe else "."),
            level="note" if dfe else "info")
    if district:
        min_lot, q = _val(district["fields"], "min_lot_area_sqft"), (district["fields"].get("min_lot_area_sqft") or {}).get("quote") or ""
        if min_lot and pd.notna(s.lot_area_best_sqft) and s.lot_area_best_sqft < float(min_lot) \
                and "as existing" not in q.lower():
            add("below_min_lot", f"Lot ({s.lot_area_best_sqft:,.0f} sq ft) is smaller than the zone minimum "
                                 f"({float(min_lot):,.0f} sq ft): rebuilding may need a variance.")
    return out


# ---------------------------------------------------------------- footprint cross-check
def tax_says_empty(s) -> bool:
    desc = (s.bldg_desc or "").upper() if isinstance(s.bldg_desc, str) else ""
    no_floors = pd.isna(s.existing_stories) or s.existing_stories == 0
    # "PARKING" alone means a parking lot; "6B-99U-PARKING" is a building with garage parking.
    return bool(s.is_vacant_land) or s.existing_stories == 0 or ("PARKING" in desc and no_floors)


def building_detected(s, fp: dict) -> bool:
    return tax_says_empty(s) and (fp.get("footprint_coverage_pct") or 0) >= BUILDING_DETECTED_COVERAGE_PCT


def overture_floors(fp: dict) -> tuple[float, str] | None:
    """Floors from footprint data: stated num_floors, else height ÷ typical floor-to-floor (rounded)."""
    nf, h = _num(fp.get("overture_num_floors")), _num(fp.get("overture_max_height_ft"))
    if nf:
        return float(nf), "stated floors"
    if h:
        return float(round(h / TYPICAL_FLOOR_TO_FLOOR_FT)), f"{h:.0f} ft tall ÷ {_n(TYPICAL_FLOOR_TO_FLOOR_FT)} ft"
    return None


def floors_disagree(s, fp: dict) -> tuple[float, float, str] | None:
    tax = _num(s.existing_stories)
    ov = overture_floors(fp)
    if tax is None or tax == 0 or ov is None or ov[0] == 0:
        return None
    return (tax, ov[0], ov[1]) if abs(tax - ov[0]) >= FLOORS_DISAGREE_MIN else None


# ---------------------------------------------------------------- score
SCORE_PENALTY_REASONS = [
    ("under_construction", "Possibly under construction (tax record shows work in progress)"),
    ("building_detected", "Building detected on a lot the tax record calls empty"),
    ("exempt", "Tax-exempt owner (rarely available to buy)"),
    ("redev_agreement", "Redevelopment agreement already on site"),
    ("historic", "In a historic district (review required)"),
    ("nonconforming", "Already larger than zoning allows"),
    ("irregular_lot", "Irregular lot shape"),
]


def upside_score(r: dict) -> tuple[int, list[str], dict]:
    """Transparent 0–100 score. `r` holds the computed numbers; returns (score, reasons, points per part)."""
    W, pts, reasons = SCORE_WEIGHTS, {}, []
    uu, us = r.get("unused_units"), r.get("unused_stories")
    if uu is not None and uu > 0:
        pts["unused_units"] = W["unused_units"] * min(uu, UNUSED_UNITS_CAP) / UNUSED_UNITS_CAP
        reasons.append(f"Zone allows {r['allowed_units']} units; currently {r['existing_units']}")
    if us is not None and us > 0:
        pts["unused_stories"] = W["unused_stories"] * min(us, UNUSED_STORIES_CAP) / UNUSED_STORIES_CAP
        mx = r.get("allowed_stories_max")
        extra = f" (up to {_n(mx)} at the minimum floor height)" if mx is not None and mx > r["allowed_stories"] else ""
        about = "about " if extra else ""
        reasons.append(f"Zone allows {about}{_n(r['allowed_stories'])} floors{extra}; currently {_n(r['existing_stories'])}")
    if r.get("lot_area"):
        pts["lot_area"] = W["lot_area"] * min(r["lot_area"], LOT_AREA_CAP_SQFT) / LOT_AREA_CAP_SQFT
        if r["lot_area"] >= LOT_AREA_CAP_SQFT:
            reasons.append(f"Large lot: {r['lot_area']:,.0f} sq ft")
    share = r.get("building_value_share")
    if share is not None:
        pts["land_value_share"] = W["land_value_share"] * max(0.0, (0.5 - share) / 0.5)
        if share < 0.3:
            reasons.append(f"Building value is {share:.0%} of total — land-driven value")
    if r.get("year_built") and r["year_built"] < OLD_BUILDING_YEAR:
        pts["old_building"] = W["old_building"]
        reasons.append(f"Older building (built {r['year_built']})")
    if r.get("vacant"):
        pts["vacant_land"] = W["vacant_land"]
        reasons.append("Vacant land")
    for code, why in SCORE_PENALTY_REASONS:
        if r.get(code) and W.get(code):
            pts[code] = W[code]
            reasons.append(why)
    score = int(round(max(0.0, min(100.0, sum(pts.values())))))
    return score, reasons, {k: round(v, 1) for k, v in pts.items()}


# ---------------------------------------------------------------- main
def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def under_construction(bldg_desc) -> bool:
    return isinstance(bldg_desc, str) and re.search(UNDER_CONSTRUCTION_RE, bldg_desc.upper()) is not None


def similar_tags_report(records: pd.DataFrame) -> str:
    """Construction-like descriptions that are NOT treated as under construction, for human review."""
    d = records.bldg_desc.dropna().astype(str).str.upper()
    hit = d[d.str.contains(UNDER_CONSTRUCTION_RE, regex=True)]
    sim = d[d.str.contains(SIMILAR_TAG_RE, regex=True) & ~d.str.contains(UNDER_CONSTRUCTION_RE, regex=True)]
    lines = ["# Construction-like tags in tax building descriptions", "",
             f"Treated as *possibly under construction* (pattern `{UNDER_CONSTRUCTION_RE}`): "
             f"{len(hit)} records, {hit.nunique()} distinct descriptions.", "",
             hit.value_counts().to_frame("records").to_markdown(), "",
             f"## Similar-looking, NOT flagged — please review (pattern `{SIMILAR_TAG_RE}`)", "",
             sim.value_counts().to_frame("records").to_markdown() if len(sim) else "_none_"]
    return "\n".join(lines) + "\n"


def condo_master_ids(records: pd.DataFrame, sites: gpd.GeoDataFrame) -> tuple[set[str], set[str]]:
    """(condo buildings whose lot also holds a land-only master record, non-condo land-only sites that share
    block + base lot number with condo unit records — e.g. lot 1.02 next to condo lot 1.01)."""
    land = (~records.is_condo_record) & ((records.impr_value.fillna(0) == 0) | records.b_is_vacant.fillna(False))
    grp = records.groupby(["block", "site_lot"])
    has_condo = grp.is_condo_record.any()
    has_land = records[land].groupby(["block", "site_lot"]).size()
    masters = {f"{b}-{l}" for b, l in has_condo[has_condo].index.intersection(has_land.index)}
    base = lambda l: str(l).split(".")[0]
    condo_keys = set(zip(records[records.is_condo_record].block, records[records.is_condo_record].lot.map(base)))
    ns = sites[~sites.is_condo_building]
    land_only = (ns.impr_value.fillna(0) == 0) | ns.is_vacant_land
    possible = {sid for sid, b, l, lo in zip(ns.site_id, ns.block, ns.lot, land_only) if lo and (b, base(l)) in condo_keys}
    return masters, possible


def source_conflicts(approved: dict) -> dict[str, list[str]]:
    """Where another source (the project brief's ordinance quotes in rules_schema.SEEDS) disagrees with the
    height/story limit actually used, describe both values and whether the floors result changes. Approved
    values are still the ones used; this only surfaces the disagreement."""
    out: dict[str, list[str]] = {}
    for zk, seed in SEEDS.items():
        zone = approved.get(zk)
        if not zone:
            continue
        d = next((x for x in zone["districts"] if not x["name"]), zone["districts"][0])
        f = d["fields"]
        lim = effective_limits(f)
        for key, other in seed["values"].items():
            if key not in ("max_height_ft", "max_stories") or not isinstance(other, (int, float)):
                continue
            mine = lim[key]
            if mine is None or float(mine) == float(other):
                continue
            alt = {k: v for k, v in f.items() if not k.startswith(key)}  # drop all building-type variants
            alt[key] = {"value": other}
            a, b = allowed_stories(f)["value"], allowed_stories(alt)["value"]
            effect = (f"allowed floors are {_n(a)} either way" if a == b else
                      f"allowed floors would be {_n(b)} instead of {_n(a)}")
            label = key.replace("_ft", "").replace("_", " ")
            basis = lim["height_basis" if key == "max_height_ft" else "stories_basis"]
            out.setdefault(zk, []).append(
                f"Sources disagree on {label}: the approved rules say {_n(mine)} ({basis}), the ordinance text in "
                f"the {seed['source']} says {_n(other)} (“{seed['text']}”). Using the approved value; {effect}. "
                "Confirm with the ordinance.")
    return out


def compute(sites: gpd.GeoDataFrame, approved: dict, footprints: pd.DataFrame | None = None,
            release: str | None = None, masters: set[str] | None = None,
            possible_masters: set[str] | None = None) -> pd.DataFrame:
    rows = []
    conflicts = source_conflicts(approved)
    fp_by_id = footprints.set_index("site_id").to_dict("index") if footprints is not None else {}
    masters, possible_masters = masters or set(), possible_masters or set()
    for _, s in sites.iterrows():
        zone = approved.get(s.zone_key)
        if s.is_condo_building:
            status, district = "condo_building", None
        elif zone is None:
            status, district = "rules_not_loaded", None
        else:
            status = "scored"
            # A site uses the zone's main district (no name); sub-districts can't be located on the map.
            district = next((d for d in zone["districts"] if not d["name"]), zone["districts"][0])

        r: dict = {"site_id": s.site_id, "status": status, "rule_district": district["name"] if district else None}
        lot_area = _num(s.lot_area_best_sqft)
        fp = fp_by_id.get(s.site_id)
        if fp:
            ov = overture_floors(fp)
            r.update(footprint_coverage_pct=fp["footprint_coverage_pct"],
                     overture_max_height_ft=_num(fp["overture_max_height_ft"]),
                     overture_num_floors=_num(fp["overture_num_floors"]),
                     overture_floors_est=ov[0] if ov else None, overture_floors_basis=ov[1] if ov else None)

        # existing
        ex_st = _num(s.existing_stories)
        ex_u, ex_u_basis = _num(s.existing_units), "tax building description" if pd.notna(s.existing_units) else None
        if ex_u is None and s.parse_status == "non_residential" and ex_st is not None:
            ex_u, ex_u_basis = 0, "no residential units listed in tax building description"
        if s.parse_status == "condo_unit" or s.is_condo_building:
            ex_u_basis = s.existing_units_source
        r.update(existing_stories=ex_st, existing_units=None if ex_u is None else int(ex_u),
                 existing_units_basis=ex_u_basis, lot_area=lot_area)

        nonconf: list[str] = []
        if district:
            st = allowed_stories(district["fields"])
            un = allowed_units(district["density_structured"], lot_area)
            r.update(allowed_stories=st["value"], allowed_stories_max=st["max_value"],
                     realistic_floor_to_floor_ft=st.get("realistic_ftf"), min_floor_to_floor_ft=st.get("min_ftf"),
                     stories_formula=st["formula"], stories_note=st["note"], limits_basis=st.get("limits_basis"),
                     allowed_units=un["value"], units_formula=un["formula"], units_note=un["note"],
                     residential_permitted=_val(district["fields"], "residential_permitted"))
            if st["value"] is not None and ex_st is not None:
                r["unused_stories"] = max(0.0, st["value"] - ex_st)
                if ex_st > st["max_value"]:  # nonconforming only against the legal maximum
                    nonconf.append(f"{_n(ex_st)} stories vs {_n(st['max_value'])} allowed")
            if un["value"] is not None and ex_u is not None:
                r["unused_units"] = max(0, un["value"] - int(ex_u))
                if ex_u > un["value"]:
                    nonconf.append(f"{int(ex_u)} units vs {un['value']} allowed")
            r["nonconforming"] = bool(nonconf)

        net = (_num(s.land_value) or 0) + (_num(s.impr_value) or 0)
        r["building_value_share"] = (_num(s.impr_value) or 0) / net if net > 0 else None
        r["under_construction"] = under_construction(s.bldg_desc)
        r["building_detected"] = bool(fp and building_detected(s, fp))
        r["possible_condo_master"] = s.site_id in possible_masters
        r["condo_master_lot"] = s.site_id in masters
        if status == "condo_building":
            r["flags"] = ([{"code": "condo_master_lot", "level": "info",
                            "text": "Condo building — land record only: this lot's land-only master record belongs to "
                                    "a condo building, so it is not a buildable site and is excluded from ranking."}]
                          if r["condo_master_lot"] else [])
        else:
            r["flags"] = site_flags(s, district, zone, nonconf, conflicts.get(s.zone_key), fp, release,
                                    r["possible_condo_master"])

        if status == "scored":
            score, reasons, parts = upside_score({
                **r, "year_built": _num(s.year_built), "vacant": bool(s.is_vacant_land),
                "historic": bool(s.in_historic_district), "redev_agreement": bool(s.has_redev_agreement),
                "irregular_lot": bool(s.lot_irregular), "exempt": bool(s.is_exempt)})
            r.update(score=score, score_reasons=reasons, score_parts=parts)
        rows.append(r)
    return pd.DataFrame(rows)


# Only these columns ever reach the web app (no owner data exists in the pipeline at all).
WEB_SITE_COLS = [
    "site_id", "block", "lot", "merged_lots", "location", "prop_class", "zone", "zone_key", "district_name",
    "bldg_desc", "lot_desc", "year_built", "sale_date", "sale_price", "land_value", "impr_value", "net_value",
    "lot_area_basis", "lot_width_ft", "lot_depth_ft", "is_condo_building", "condo_unit_count", "commercial_units",
    "is_vacant_land", "in_historic_district", "in_flood_hazard_area", "in_redev_area", "has_redev_agreement",
    "in_zoning_in_progress", "redev_area_url", "redev_agreement_url", "ordinance_url", "guide_url",
]


def _clean_json(v):
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 3)
    if hasattr(v, "tolist"):
        return v.tolist()
    if hasattr(v, "item"):
        return v.item()
    return v


def data_dates(release: str | None) -> dict:
    """When each source was downloaded (date folder of the cached file) and the footprint release."""
    from .http_client import find_cached
    def d(name):
        p = find_cached(name)
        return p.parent.name if p else None
    out = {"tax_data": d("parcels.geojson"), "zoning_layers": d("zoning.geojson"),
           "zoning_guide": d("guide_site.json"), "overture_release": release}
    meta = (config.RAW / "overture" / release / "meta.json") if release else None
    if meta and meta.exists():
        out["overture_downloaded"] = json.loads(meta.read_text()).get("downloaded_at", "")[:10]
    return out


def write_web(sites: gpd.GeoDataFrame, pot: pd.DataFrame, approved_file: dict, dates: dict | None = None) -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    g = sites[WEB_SITE_COLS + ["geometry"]].merge(pot, on="site_id")
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=sites.crs)
    g["geometry"] = g.geometry.simplify(SIMPLIFY_TOLERANCE_FT, preserve_topology=True)
    g = g.to_crs(config.CRS_WGS84)
    feats = []
    for rec, geom in zip(g.drop(columns="geometry").to_dict("records"), g.geometry):
        props = {k: _clean_json(v) for k, v in rec.items()}
        feats.append({"type": "Feature", "properties": props, "geometry": _round_geom(geom.__geo_interface__)})
    (WEB_DATA / "sites.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                       separators=(",", ":")))
    rules = {
        "generated_at": date.today().isoformat(),
        "disclaimer": "Estimate based on public zoning text; verify with the Hoboken Zoning Office.",
        "assumptions": {
            "default_floor_to_floor_ft": DEFAULT_FLOOR_TO_FLOOR_FT,
            "typical_floor_to_floor_ft": TYPICAL_FLOOR_TO_FLOOR_FT,
            "large_site_sqft": LARGE_SITE_SQFT,
            "building_detected_coverage_pct": BUILDING_DETECTED_COVERAGE_PCT,
            "floors_disagree_min": FLOORS_DISAGREE_MIN,
            "default_rounding": DEFAULT_ROUNDING,
            "binding_limit": "When both a story limit and a height limit are stated, the lower one is used.",
            "subdistricts": "Sites use the zone's main district; sub-districts are flagged, not assigned.",
        },
        "score_weights": SCORE_WEIGHTS,
        "score_caps": {"unused_units": UNUSED_UNITS_CAP, "unused_stories": UNUSED_STORIES_CAP,
                       "lot_area_sqft": LOT_AREA_CAP_SQFT, "old_building_before": OLD_BUILDING_YEAR},
        "source_conflicts": source_conflicts(approved_file["zones"]),
        "data_dates": dates or {},
        "zones": approved_file["zones"],
    }
    (WEB_DATA / "rules.json").write_text(json.dumps(rules, indent=1))


def _round_geom(gi: dict) -> dict:
    def r(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 6), round(c[1], 6)]
        return [r(x) for x in c]
    return {"type": gi["type"], "coordinates": r(gi["coordinates"])}


def write_report(sites: gpd.GeoDataFrame, pot: pd.DataFrame) -> str:
    sc = pot[pot.status == "scored"].merge(sites[["site_id", "block", "lot", "location", "zone_key", "bldg_desc"]],
                                           on="site_id")
    flag_counts = pd.Series([f["code"] for fl in sc["flags"] for f in fl]).value_counts()
    lines = [f"# Potential report — {date.today().isoformat()}", "",
             "Estimate based on public zoning text; verify with the Hoboken Zoning Office.", "",
             "## Coverage", "", pot.status.value_counts().to_frame("sites").to_markdown(), "",
             "## Scored sites", "",
             f"- allowed stories known: {sc.allowed_stories.notna().sum()}",
             f"- allowed units known: {sc.allowed_units.notna().sum()} (C-1 has no numeric density rule)",
             f"- unused stories > 0: {(sc.unused_stories > 0).sum()}",
             f"- unused units > 0: {(sc.unused_units > 0).sum()}",
             f"- nonconforming (already over a limit): {sc.nonconforming.sum()}", "",
             "## Flags on scored sites", "", flag_counts.to_frame("sites").to_markdown(), "",
             f"- condo buildings with a land-only master record (excluded): {int(pot.condo_master_lot.sum())}",
             f"- hidden by default (exempt / possibly under construction / possible condo master): "
             f"{int(hidden_by_default(sc, sites).sum())} scored sites", "",
             "## Score distribution", "", sc.score.describe().round(1).to_frame().to_markdown(), "",
             "## Top 25", ""]
    vis = sc[~hidden_by_default(sc, sites).values]
    lines[-1] = "## Top 25 (as shown by default: exempt, under-construction and condo-master sites hidden)"
    top = vis.nlargest(25, "score")
    lines.append(top[["score", "block", "lot", "location", "zone_key", "bldg_desc", "existing_units", "allowed_units",
                      "existing_stories", "allowed_stories"]].to_markdown(index=False))
    lines += ["", "### Reasons for the top 5", ""]
    for _, t in top.head(5).iterrows():
        lines.append(f"- **{t.location}** (block {t.block} lot {t.lot}, score {t.score}): " + "; ".join(t.score_reasons))
    return "\n".join(lines) + "\n"


# Map overlay layers for the web app: (layer key, {source column: output name}, dissolve-by column or None)
OVERLAYS = [
    ("zoning", {"Zone_": "zone", "CommZone": "name"}, None),
    ("rehab_redev", {"Rehab_Area": "name", "RehabRedev": "kind"}, None),
    ("historic", {"Historic_D": "code"}, "Historic_D"),
    ("flood", {"ZONE": "zone", "ABFE_1Pct": "abfe_ft"}, None),
]


def write_overlays() -> None:
    from .clean import load_layer
    for key, cols, dissolve in OVERLAYS:
        g = load_layer(key)[[*cols, "geometry"]]
        if dissolve:
            g = g.dissolve(by=dissolve, as_index=False)
        g["geometry"] = g.geometry.simplify(1.0, preserve_topology=True)
        g = g.rename(columns=cols).to_crs(config.CRS_WGS84)
        feats = [{"type": "Feature", "properties": {k: _clean_json(v) for k, v in rec.items()},
                  "geometry": _round_geom(geom.__geo_interface__)}
                 for rec, geom in zip(g.drop(columns="geometry").to_dict("records"), g.geometry)]
        (WEB_DATA / f"layer_{key}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))


def hidden_by_default(pot: pd.DataFrame, sites: gpd.GeoDataFrame) -> pd.Series:
    """Mirror of the web app's default filters for scored sites (exempt, under construction, condo master)."""
    exempt = pot.site_id.map(sites.set_index("site_id").is_exempt).fillna(False).astype(bool)
    return exempt | pot.under_construction.fillna(False).astype(bool) | \
        pot.possible_condo_master.fillna(False).astype(bool)


def main() -> None:
    from . import overture
    sites = gpd.read_parquet(config.PROCESSED / "sites.parquet")
    records = pd.read_parquet(config.PROCESSED / "records.parquet")
    approved_file = json.loads((config.RULES / "hoboken_rules.json").read_text())
    approved = approved_file["zones"]
    print(f"Approved zones: {', '.join(sorted(approved))}")
    release = overture.fetch(overture.hoboken_bbox(sites))
    footprints = overture.footprint_stats(sites, overture.load(release))
    masters, possible = condo_master_ids(records, sites)
    pot = compute(sites, approved, footprints, release, masters, possible)
    pot.drop(columns=["flags", "score_reasons", "score_parts"]).to_parquet(config.PROCESSED / "potential.parquet")
    (config.PROCESSED / "potential_report.md").write_text(write_report(sites, pot))
    (config.PROCESSED / "construction_tags.md").write_text(similar_tags_report(records))
    write_web(sites, pot, approved_file, data_dates(release))
    write_overlays()
    print(pot.status.value_counts().to_string())
    print("Wrote data/processed/potential_report.md, web/public/data/sites.geojson, web/public/data/rules.json")


if __name__ == "__main__":
    main()
