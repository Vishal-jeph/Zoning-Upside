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
from datetime import date

import geopandas as gpd
import pandas as pd

from . import config

# ---------------------------------------------------------------- method settings (shown as assumptions)
# Used to turn a height limit in feet into stories when the zone states no minimum floor-to-floor.
DEFAULT_FLOOR_TO_FLOOR_FT = 10.0
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
    "exempt": -10,           # church / school / public owner: rarely for sale
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


def allowed_stories(fields: dict) -> dict:
    """Binding story limit from max stories and max height. A building must meet every stated limit,
    so the lower one binds ("whichever is less" and "both apply" give the same answer)."""
    max_st, max_ft = _val(fields, "max_stories"), _val(fields, "max_height_ft")
    ftf_rule = _val(fields, "min_floor_to_floor_ft")
    ftf = float(ftf_rule) if ftf_rule else DEFAULT_FLOOR_TO_FLOOR_FT
    ftf_basis = "zone minimum floor-to-floor" if ftf_rule else "assumed typical floor-to-floor"
    from_height = math.floor(float(max_ft) / ftf) if max_ft else None

    if max_st is None and from_height is None:
        return {"value": None, "formula": None, "note": "No height or story limit in the approved rules."}
    if max_st is not None and from_height is not None:
        value = min(float(max_st), from_height)
        binding = "story limit" if float(max_st) <= from_height else "height limit"
        formula = (f"min({_n(max_st)} stories, floor({_n(max_ft)} ft ÷ {_n(ftf)} ft {ftf_basis}) = {from_height})"
                   f" = {_n(value)} ({binding} binds)")
    elif max_st is not None:
        value, formula = float(max_st), f"{_n(max_st)} stories (stated limit)"
    else:
        value = float(from_height)
        formula = f"floor({_n(max_ft)} ft ÷ {_n(ftf)} ft {ftf_basis}) = {from_height}"
    return {"value": value, "formula": formula, "note": None}


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
def site_flags(s: pd.Series, district: dict | None, zone: dict | None, nonconf: list[str]) -> list[dict]:
    out = []
    add = lambda code, text: out.append({"code": code, "text": text})
    if s.in_historic_district:
        add("historic", f"In a historic district{f' ({s.historic_code})' if s.historic_code else ''}: changes need "
                        "Historic Preservation Commission review, and extra height rules may apply.")
    if s.in_flood_hazard_area:
        abfe = f" (advisory base flood elevation {s.flood_abfe_ft:g} ft)" if pd.notna(s.flood_abfe_ft) else ""
        add("flood", f"In a FEMA flood zone {s.flood_zone_codes}{abfe}: ground floor elevation rules apply"
                     + ("; height is measured from the design flood elevation." if district and
                        _val(district["fields"], "height_measured_from") == "design_flood_elevation" else "."))
    if s.in_redev_area:
        add("redev_area", f"Inside {s.redev_area_name or 'a redevelopment area'} ({s.redev_area_kind or 'plan'}): "
                          "that plan's rules may replace or add to the zone rules.")
    if s.has_redev_agreement:
        add("redev_agreement", f"A redevelopment agreement covers this site ({s.redev_agreement_name}): "
                               "a developer already has a deal with the City.")
    if s.in_zoning_in_progress:
        add("zoning_in_progress", f"Rules are being changed here ({s.zoning_in_progress_name}).")
    if s.lot_irregular:
        add("irregular_lot", "Irregular lot shape: buildable area may be smaller than the lot area suggests.")
    if s.is_exempt:
        add("exempt", "Tax-exempt property (public, religious or nonprofit owner): rarely for sale.")
    if s.area_mismatch:
        add("area_mismatch", f"Tax-record lot area and mapped lot area disagree (ratio {s.lot_area_ratio:.2f}); "
                             f"using {s.lot_area_basis}.")
    if s.zone_split:
        add("zone_split", f"Lot crosses a zone boundary; {s.zone_share:.0%} is in {s.zone}.")
    if s.zone_mismatch:
        add("zone_mismatch", f"The tax record lists zone {s.tax_zone}; the zoning map says {s.zone}.")
    if district:
        min_lot, q = _val(district["fields"], "min_lot_area_sqft"), (district["fields"].get("min_lot_area_sqft") or {}).get("quote") or ""
        if min_lot and pd.notna(s.lot_area_best_sqft) and s.lot_area_best_sqft < float(min_lot) \
                and "as existing" not in q.lower():
            add("below_min_lot", f"Lot ({s.lot_area_best_sqft:,.0f} sq ft) is smaller than the zone minimum "
                                 f"({float(min_lot):,.0f} sq ft): rebuilding may need a variance.")
    if zone and len(zone["districts"]) > 1:
        others = [d["name"] for d in zone["districts"] if d["name"]]
        add("subdistrict", f"This zone has a sub-district ({', '.join(others)}) with different rules; "
                           "check whether this lot is in it.")
    if nonconf:
        add("nonconforming", "Existing building already exceeds the zone limit (" + "; ".join(nonconf) +
            "): not an expansion opportunity.")
    return out


# ---------------------------------------------------------------- score
def upside_score(r: dict) -> tuple[int, list[str], dict]:
    """Transparent 0–100 score. `r` holds the computed numbers; returns (score, reasons, points per part)."""
    W, pts, reasons = SCORE_WEIGHTS, {}, []
    uu, us = r.get("unused_units"), r.get("unused_stories")
    if uu is not None and uu > 0:
        pts["unused_units"] = W["unused_units"] * min(uu, UNUSED_UNITS_CAP) / UNUSED_UNITS_CAP
        reasons.append(f"Zone allows {r['allowed_units']} units; currently {r['existing_units']}")
    if us is not None and us > 0:
        pts["unused_stories"] = W["unused_stories"] * min(us, UNUSED_STORIES_CAP) / UNUSED_STORIES_CAP
        reasons.append(f"Zone allows {_n(r['allowed_stories'])} stories; currently {_n(r['existing_stories'])}")
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
    for code, why in [("historic", "In a historic district (review required)"),
                      ("redev_agreement", "Redevelopment agreement already on site"),
                      ("nonconforming", "Already larger than zoning allows"),
                      ("irregular_lot", "Irregular lot shape"),
                      ("exempt", "Tax-exempt owner")]:
        if r.get(code):
            pts[code] = W[code]
            reasons.append(why)
    score = int(round(max(0.0, min(100.0, sum(pts.values())))))
    return score, reasons, {k: round(v, 1) for k, v in pts.items()}


# ---------------------------------------------------------------- main
def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def compute(sites: gpd.GeoDataFrame, approved: dict) -> pd.DataFrame:
    rows = []
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
            r.update(allowed_stories=st["value"], stories_formula=st["formula"], stories_note=st["note"],
                     allowed_units=un["value"], units_formula=un["formula"], units_note=un["note"],
                     residential_permitted=_val(district["fields"], "residential_permitted"))
            if st["value"] is not None and ex_st is not None:
                r["unused_stories"] = max(0.0, st["value"] - ex_st)
                if ex_st > st["value"]:
                    nonconf.append(f"{_n(ex_st)} stories vs {_n(st['value'])} allowed")
            if un["value"] is not None and ex_u is not None:
                r["unused_units"] = max(0, un["value"] - int(ex_u))
                if ex_u > un["value"]:
                    nonconf.append(f"{int(ex_u)} units vs {un['value']} allowed")
            r["nonconforming"] = bool(nonconf)

        net = (_num(s.land_value) or 0) + (_num(s.impr_value) or 0)
        r["building_value_share"] = (_num(s.impr_value) or 0) / net if net > 0 else None
        r["flags"] = site_flags(s, district, zone, nonconf) if status != "condo_building" else []

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


def write_web(sites: gpd.GeoDataFrame, pot: pd.DataFrame, approved_file: dict) -> None:
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
            "default_rounding": DEFAULT_ROUNDING,
            "binding_limit": "When both a story limit and a height limit are stated, the lower one is used.",
            "subdistricts": "Sites use the zone's main district; sub-districts are flagged, not assigned.",
        },
        "score_weights": SCORE_WEIGHTS,
        "score_caps": {"unused_units": UNUSED_UNITS_CAP, "unused_stories": UNUSED_STORIES_CAP,
                       "lot_area_sqft": LOT_AREA_CAP_SQFT, "old_building_before": OLD_BUILDING_YEAR},
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
             "## Score distribution", "", sc.score.describe().round(1).to_frame().to_markdown(), "",
             "## Top 25", ""]
    top = sc.nlargest(25, "score")
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


def main() -> None:
    sites = gpd.read_parquet(config.PROCESSED / "sites.parquet")
    approved_file = json.loads((config.RULES / "hoboken_rules.json").read_text())
    approved = approved_file["zones"]
    print(f"Approved zones: {', '.join(sorted(approved))}")
    pot = compute(sites, approved)
    pot.drop(columns=["flags", "score_reasons", "score_parts"]).to_parquet(config.PROCESSED / "potential.parquet")
    (config.PROCESSED / "potential_report.md").write_text(write_report(sites, pot))
    write_web(sites, pot, approved_file)
    write_overlays()
    print(pot.status.value_counts().to_string())
    print("Wrote data/processed/potential_report.md, web/public/data/sites.geojson, web/public/data/rules.json")


if __name__ == "__main__":
    main()
