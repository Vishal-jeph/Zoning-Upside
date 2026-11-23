"""Turn cached raw layers into one row per development site.

Usage:
    python -m pipeline.clean          # uses the newest data/raw/YYYY-MM-DD/
Outputs:
    data/processed/sites.parquet      GeoParquet, EPSG:3424 (NJ State Plane, US ft)
    data/processed/records.parquet    per-tax-record parse results (no geometry), for debugging
    data/processed/data_quality.md    counts, parse rates, mismatches, top unparsed patterns
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date

import geopandas as gpd
import pandas as pd
from shapely import make_valid
from shapely.ops import unary_union

from . import config
from .http_client import find_cached
from .parsers import (
    norm_lot, norm_zone, parse_additional_lots, parse_bldg_desc, parse_lot_desc,
    parse_sale_date, parse_year, to_int,
)

# A constraint polygon must cover at least this share of a site to flag it; this
# ignores slivers where neighbouring polygons touch along a shared edge.
MIN_OVERLAP_SHARE = 0.10
# Tax-record lot area vs polygon area: flag when the ratio leaves this band.
AREA_RATIO_OK = (0.67, 1.5)

HREF_RE = re.compile(r'href="([^"]+)"', re.I)


def href(html: str | None) -> str | None:
    """Extract the URL from an ArcGIS HTML anchor string like '<a href="...">C-1</a>'."""
    m = HREF_RE.search(html or "")
    return m.group(1).strip() if m else None


def clean_str(v) -> str | None:
    s = "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()
    return s or None


def load_layer(key: str) -> gpd.GeoDataFrame:
    path = find_cached(f"{key}.geojson")
    if path is None:
        raise SystemExit(f"No cached {key}.geojson — run `python -m pipeline.fetch` first.")
    gdf = gpd.read_file(path).set_crs(config.CRS_WGS84, allow_override=True).to_crs(config.CRS_FEET)
    gdf["geometry"] = gdf.geometry.apply(make_valid)
    return gdf


# ------------------------------------------------------------------ records
def parse_records(parcels: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    for r in parcels.itertuples():
        b = parse_bldg_desc(r.M4_Bldg_Desc)
        lot = parse_lot_desc(r.M4_Lot_Desc)
        qual = clean_str(r.Parcel_QUAL) or ""
        # Condo detection: any one of the three signals marks the record as a condo unit.
        is_condo = qual.upper().startswith("C") or b.parse_status == "condo_unit" or lot.parse_status == "condo_unit"
        rows.append({
            "objectid": r.OBJECTID,
            "block": clean_str(r.Parcel_BLOCK),
            "lot": norm_lot(clean_str(r.Parcel_LOT)),
            "qual": qual,
            "pams_pin": clean_str(r.M4_PAMSPIN),
            "location": clean_str(r.M4_Location),
            "prop_class": clean_str(r.M4_Class),
            "bldg_desc": clean_str(r.M4_Bldg_Desc),
            "lot_desc": clean_str(r.M4_Lot_Desc),
            "additional_lots_raw": clean_str(r.M4_Additional_Lots),
            "tax_zone": clean_str(r.M4_Zone),
            "year_built": parse_year(r.M4_Year_Built),
            "sf_area": to_int(r.M4_Sf_Area),
            "land_value": to_int(r.M4_Land_Value),
            "impr_value": to_int(r.M4_Impr_Value),
            "net_value": to_int(r.M4_Net_Value),
            "sale_date": parse_sale_date(r.M4_Sale_Date),
            "sale_price": to_int(r.M4_Sale_Price),
            "is_condo_record": is_condo,
            **{f"b_{k}": v for k, v in asdict(b).items()},
            **{f"l_{k}": v for k, v in asdict(lot).items()},
            "geometry": r.geometry,
        })
    df = pd.DataFrame(rows)
    df["site_lot"] = df["lot"]
    return df


def assign_additional_lots(rec: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fold "additional lots" into their lead lot's site.

    Observed in the data: a lead record lists e.g. '2,3,4,30' in M4_Additional_Lots, and
    each of those lots has its own parcel record repeating the lead's lot description
    (the combined area). Treating them separately would count that land several times.
    Only same-block numeric lists are resolved; other text is flagged as unresolved.
    """
    by_key = rec.groupby(["block", "lot"]).groups
    stats = Counter()
    unresolved_leads = set()
    leads = rec[(~rec.is_condo_record) & rec.additional_lots_raw.notna()]
    for r in leads.itertuples():
        lots, ok = parse_additional_lots(r.additional_lots_raw)
        if not ok:
            unresolved_leads.add((r.block, r.lot))
            stats["unresolved_lists"] += 1
        for other in lots:
            other = norm_lot(other)
            idx = by_key.get((r.block, other))
            if other == r.lot or idx is None:
                continue
            rec.loc[idx, "site_lot"] = r.lot
            stats["lots_merged"] += 1
    rec["additional_lots_unresolved"] = [(b, l) in unresolved_leads for b, l in zip(rec.block, rec.lot)]
    stats["lots_merged_duplicate_records"] = merge_duplicate_records(rec)
    return rec, dict(stats)


def _lot_sort_key(lot: str):
    try:
        return (0, float(lot))
    except ValueError:
        return (1, lot)


def merge_duplicate_records(rec: pd.DataFrame) -> int:
    """Merge lots whose tax records are identical copies of one combined property.

    Observed in the data: a property spanning several lots often has the SAME tax record
    (location, lot description, building description, land and improvement value) on each
    lot, without listing them in M4_Additional_Lots. E.g. block 10 lots 9-26 all read
    '2CB-OFF/ STREET', '61229 SQ FT', land $2,632,000. Those are one site.
    The lead is the lot whose record lists additional lots, else the lowest lot number.
    """
    key = ["block", "location", "lot_desc", "bldg_desc", "land_value", "impr_value"]
    cand = rec[~rec.is_condo_record & rec.location.notna() & rec.lot_desc.notna()]
    merged = 0
    for _, g in cand.groupby(key, dropna=False):
        site_lots = set(g.site_lot)
        if len(site_lots) < 2:
            continue
        with_list = g[g.additional_lots_raw.notna()]
        lead = with_list.site_lot.iloc[0] if len(with_list) else min(site_lots, key=_lot_sort_key)
        block = g.block.iloc[0]
        move = (rec.block == block) & rec.site_lot.isin(site_lots - {lead})
        merged += int(rec.loc[move, "lot"].nunique())
        rec.loc[move, "site_lot"] = lead
    return merged


# ------------------------------------------------------------------ sites
def _primary(g: pd.DataFrame) -> pd.Series:
    """Record that describes the site as a whole: the lead lot's unqualified, non-condo record."""
    for mask in (
        (g.lot == g.site_lot) & (g.qual == "") & ~g.is_condo_record,
        ~g.is_condo_record,
        g.b_is_common_element,
    ):
        if mask.any():
            return g[mask].iloc[0]
    return g.iloc[0]


def build_sites(rec: pd.DataFrame) -> gpd.GeoDataFrame:
    out = []
    for (block, site_lot), g in rec.groupby(["block", "site_lot"], sort=False):
        p = _primary(g)
        condo_units = g[g.is_condo_record & ~g.b_is_common_element]
        is_condo_building = len(condo_units) > 0 or bool(g.b_is_common_element.any())
        row = {
            "site_id": f"{block}-{site_lot}",
            "block": block,
            "lot": site_lot,
            "merged_lots": sorted(set(g.lot) - {site_lot}),
            "record_count": len(g),
            "quals": sorted(q for q in set(g.qual) if q),
            "location": p.location,
            "prop_class": p.prop_class,
            "bldg_desc": p.bldg_desc,
            "lot_desc": p.lot_desc,
            "tax_zone": p.tax_zone,
            "additional_lots_raw": p.additional_lots_raw,
            "additional_lots_unresolved": bool(g.additional_lots_unresolved.any()),
            "is_condo_building": is_condo_building,
            "condo_unit_count": len(condo_units),
            "year_built": p.year_built,
            "sale_date": p.sale_date,
            "sale_price": p.sale_price,
            "parse_status": p.b_parse_status,
            "existing_stories": p.b_existing_stories,
            "existing_stories_min": p.b_existing_stories_min,
            "material_code": p.b_material_code,
            "material": p.b_material,
            "existing_units": p.b_existing_units,
            "existing_units_source": "bldg_desc" if p.b_existing_units is not None else None,
            "commercial_units": p.b_commercial_units,
            "building_count": p.b_building_count,
            "bldg_tags": list(p.b_tags),
            "is_vacant_desc": bool(p.b_is_vacant),
            "lot_parse_status": p.l_parse_status,
            "lot_width_ft": p.l_lot_width_ft,
            "lot_depth_ft": p.l_lot_depth_ft,
            "lot_area_sqft": p.l_lot_area_sqft,
            "lot_area_source": p.l_area_source,
            "lot_irregular": bool(p.l_irregular),
            "lot_average": bool(p.l_average),
            "lot_corner": bool(p.l_corner),
            "lot_multi_part": bool(p.l_multi_part),
            "land_value": p.land_value,
            "impr_value": p.impr_value,
            "net_value": p.net_value,
            "geometry": unary_union(list(g.geometry)),
        }
        if is_condo_building:
            # Unit owners are taxed individually: building value = sum of unit records.
            row["parse_status"] = "condo_unit"
            for col in ("land_value", "impr_value", "net_value"):
                row[col] = int(g[col].fillna(0).sum())
            res = g[g.bldg_desc.fillna("").str.contains(r"\d\s*(?:BR|BDRM)|^BR|STUDIO", regex=True)]
            row["existing_units"] = len(res) or None
            row["existing_units_source"] = "count of bedroom/studio condo records" if len(res) else None
            years = g.year_built.dropna()
            row["year_built"] = int(years.mode().iloc[0]) if len(years) else None
        out.append(row)
    gdf = gpd.GeoDataFrame(out, geometry="geometry", crs=config.CRS_FEET)

    # Polygon area in sq ft (EPSG:3424 units are US survey feet; the tiny
    # survey-vs-international foot difference, 2 ppm, is irrelevant here).
    gdf["geom_area_sqft"] = gdf.geometry.area.round(1)
    ratio = gdf.lot_area_sqft / gdf.geom_area_sqft
    gdf["lot_area_ratio"] = ratio.round(3)
    gdf["area_mismatch"] = ratio.notna() & ((ratio < AREA_RATIO_OK[0]) | (ratio > AREA_RATIO_OK[1]))
    # Best available lot area for later calculations, with its basis recorded.
    gdf["lot_area_best_sqft"] = gdf.lot_area_sqft.fillna(gdf.geom_area_sqft)
    gdf["lot_area_basis"] = gdf.lot_area_sqft.notna().map({True: "tax lot description", False: "parcel polygon area"})
    gdf["is_exempt"] = gdf.prop_class.fillna("").str.startswith("15")
    gdf["is_vacant_land"] = (gdf.prop_class == "1") | gdf.is_vacant_desc
    return gdf


# ------------------------------------------------------------------ spatial joins
def overlap(sites: gpd.GeoDataFrame, layer: gpd.GeoDataFrame, cols: list[str]) -> pd.DataFrame:
    """Intersections between sites and a polygon layer, with share of site area covered."""
    left = sites[["site_id", "geom_area_sqft", "geometry"]]
    right = layer[cols + ["geometry"]].copy()
    right["_lid"] = range(len(right))
    inter = gpd.overlay(left, right, how="intersection", keep_geom_type=True)
    inter["share"] = inter.geometry.area / inter.geom_area_sqft.where(inter.geom_area_sqft > 0)
    return inter.drop(columns="geometry")


def join_zoning(sites: gpd.GeoDataFrame, zoning: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    z = zoning.copy()
    z["zone"] = z.Zone_.map(clean_str)
    z["district_name"] = z.CommZone.map(clean_str)
    # RPA polygons are redevelopment plan areas: the plan, not the base district, sets the rules.
    z["redev_plan"] = [re.sub(r"\s*-\s*RPA$", "", c or "") if zn == "RPA" else None
                       for zn, c in zip(z.zone, z.district_name)]
    z["zone_key"] = [f"RPA:{p}" if zn == "RPA" else zn for zn, p in zip(z.zone, z.redev_plan)]
    z["ordinance_url"] = z.Hyperlink.map(href)
    z["plan_url"] = z.Hyperlink2.map(href)
    z["guide_url"] = z.Guide.map(href)
    cols = ["zone", "zone_key", "district_name", "redev_plan", "ordinance_url", "plan_url", "guide_url"]
    inter = overlap(sites, z, cols)
    # Each site takes the zone covering most of its area; split sites are flagged.
    best = inter.sort_values("share", ascending=False).drop_duplicates("site_id")
    n_zones = inter[inter.share >= MIN_OVERLAP_SHARE].groupby("site_id").zone_key.nunique()
    out = sites.merge(best[["site_id", *cols, "share"]].rename(columns={"share": "zone_share"}),
                      on="site_id", how="left")
    out["zone_split"] = out.site_id.map(n_zones).fillna(0) > 1
    tz, pz = out.tax_zone.map(norm_zone), out.zone.map(norm_zone)
    out["zone_mismatch"] = (tz != "") & (pz != "") & (tz != pz)
    return out


def join_constraints(sites: gpd.GeoDataFrame, layers: dict[str, gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    def agg(inter: pd.DataFrame, col: str) -> pd.Series:
        hit = inter[inter.share >= MIN_OVERLAP_SHARE]
        return hit.groupby("site_id")[col].apply(lambda s: "; ".join(sorted({str(v) for v in s if v})) or None)

    # Redevelopment / rehabilitation areas (some are not RPA polygons on the zoning layer).
    rr = layers["rehab_redev"].copy()
    rr["name"] = [clean_str(a) or clean_str(b) for a, b in zip(rr.Rehab_Area, rr.CommZone)]
    rr["kind"] = rr.RehabRedev.map(clean_str) + " (" + rr.OverlaySup.map(clean_str).fillna("?") + ")"
    rr["url"] = rr.Hyperlink.map(href)
    i = overlap(sites, rr, ["name", "kind", "url"])
    sites["redev_area_name"] = sites.site_id.map(agg(i, "name"))
    sites["redev_area_kind"] = sites.site_id.map(agg(i, "kind"))
    sites["redev_area_url"] = sites.site_id.map(agg(i, "url"))

    zp = layers["zoning_in_progress"].copy()
    zp["name"] = zp.Rehab_Area.map(clean_str)
    zp["url"] = zp.Hyperlink2.map(href)
    i = overlap(sites, zp, ["name", "url"])
    sites["zoning_in_progress_name"] = sites.site_id.map(agg(i, "name"))
    sites["zoning_in_progress_url"] = sites.site_id.map(agg(i, "url"))

    ra = layers["redev_agreement"].copy()
    ra["name"] = ra.PrjctName.map(clean_str)
    ra["url"] = ra.Agreement.map(href)
    i = overlap(sites, ra, ["name", "url"])
    sites["redev_agreement_name"] = sites.site_id.map(agg(i, "name"))
    sites["redev_agreement_url"] = sites.site_id.map(agg(i, "url"))

    hd = layers["historic"].copy()
    hd["code"] = hd.Historic_D.map(clean_str)
    i = overlap(sites, hd, ["code"])
    sites["historic_code"] = sites.site_id.map(agg(i, "code"))

    fl = layers["flood"].copy()
    fl["zone_code"] = fl.ZONE.map(clean_str)
    # Advisory base flood elevation (1% annual chance), ft. 0 / negative = not provided ("Shaded X").
    fl["abfe"] = fl.ABFE_1Pct.where(fl.ABFE_1Pct > 0)
    i = overlap(sites, fl, ["zone_code", "abfe"])
    hit = i[i.share >= MIN_OVERLAP_SHARE]
    sites["flood_zone_codes"] = sites.site_id.map(agg(i, "zone_code"))
    sites["flood_abfe_ft"] = sites.site_id.map(hit.groupby("site_id").abfe.max())

    sites["in_redev_area"] = sites.redev_area_name.notna() | (sites.zone == "RPA")
    sites["in_zoning_in_progress"] = sites.zoning_in_progress_name.notna()
    sites["has_redev_agreement"] = sites.redev_agreement_name.notna()
    sites["in_historic_district"] = sites.historic_code.notna()
    # A and V zones are flood hazard areas; "Shaded X" (0.2% chance) is reported but not flagged.
    sites["in_flood_hazard_area"] = sites.flood_zone_codes.fillna("").str.contains(r"(?:^|; )[AV]", regex=True)
    return sites


# ------------------------------------------------------------------ report
def top(counter: Counter, n: int = 30) -> str:
    return "\n".join(f"| `{k}` | {v} |" for k, v in counter.most_common(n)) or "| (none) | |"


def write_report(rec: pd.DataFrame, sites: gpd.GeoDataFrame, merge_stats: dict, raw_dir: str) -> str:
    nc_rec = rec[~rec.is_condo_record]
    nc = sites[~sites.is_condo_building]
    pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "n/a"
    bstat = nc.parse_status.value_counts()
    lstat = nc.lot_parse_status.value_counts()
    unparsed_b = Counter(nc_rec.loc[nc_rec.b_parse_status == "unparsed", "bldg_desc"].fillna("(blank)"))
    unparsed_l = Counter(nc_rec.loc[nc_rec.l_parse_status == "unparsed", "lot_desc"].fillna("(blank)"))
    zm = nc[nc.zone_mismatch]
    zm_pairs = Counter(f"{a} (tax) vs {b} (map)" for a, b in zip(zm.tax_zone, zm.zone))
    zone_counts = sites.groupby("zone_key", dropna=False).agg(
        sites=("site_id", "size"), non_condo=("is_condo_building", lambda s: int((~s).sum())))
    flags = ["in_historic_district", "in_flood_hazard_area", "in_redev_area", "has_redev_agreement",
             "in_zoning_in_progress", "is_exempt", "is_vacant_land", "lot_irregular", "area_mismatch",
             "zone_split", "zone_mismatch", "additional_lots_unresolved"]

    md = f"""# Data quality report

Generated {date.today().isoformat()} from `{raw_dir}`.

## Records → sites
| | count |
|---|---|
| Tax records (incl. condo units) | {len(rec)} |
| Condo-unit records (qualifier C*, bedroom-style or condo-style lot desc, COMMON ELEMENT) | {int(rec.is_condo_record.sum())} |
| Sites (block + lead lot) | {len(sites)} |
| Condo buildings (excluded from ranking by default) | {int(sites.is_condo_building.sum())} |
| Non-condo sites | {len(nc)} |
| Lots folded into a lead lot via M4_Additional_Lots | {merge_stats.get('lots_merged', 0)} |
| Lots folded into a lead lot because their tax record is an identical copy | {merge_stats.get("lots_merged_duplicate_records", 0)} |
| Additional-lot lists not resolvable (other blocks / free text) | {merge_stats.get('unresolved_lists', 0)} |
| Sites with no zoning polygon | {int(sites.zone.isna().sum())} |

## Parse success (non-condo sites)
| Building description | sites | share |
|---|---|---|
""" + "\n".join(f"| {k} | {v} | {pct(v, len(nc))} |" for k, v in bstat.items()) + f"""

Sites with both stories and units parsed: **{int((nc.existing_stories.notna() & nc.existing_units.notna()).sum())}** of {len(nc)}.

| Lot description | sites | share |
|---|---|---|
""" + "\n".join(f"| {k} | {v} | {pct(v, len(nc))} |" for k, v in lstat.items()) + f"""

Material codes seen (only F = Frame and B = Brick are confirmed; others are kept raw):
{', '.join(f'`{k}` {v}' for k, v in nc.material_code.value_counts().items())}

Building tags seen (only G = Garage, GUTTED, WIP have confirmed meanings):
{', '.join(f'`{k}` {v}' for k, v in Counter(t for ts in nc.bldg_tags for t in ts).most_common(25))}

## 30 most common unparsed building descriptions (non-condo records)
| value | records |
|---|---|
{top(unparsed_b)}

## Most common unparsed lot descriptions (non-condo records)
| value | records |
|---|---|
{top(unparsed_l, 15)}

## Sites per zone
| zone | sites | non-condo |
|---|---|---|
""" + "\n".join(f"| {k} | {r.sites} | {r.non_condo} |" for k, r in zone_counts.iterrows()) + f"""

## Zone mismatches: tax record M4_Zone vs zoning map polygon (non-condo sites)
{len(zm)} of {len(nc)} sites ({pct(len(zm), len(nc))}). The map polygon is used; the tax zone is kept for reference.

| pair | sites |
|---|---|
{top(zm_pairs, 15)}

## Lot area: tax description vs polygon
Ratio outside {AREA_RATIO_OK[0]}–{AREA_RATIO_OK[1]}: **{int(nc.area_mismatch.sum())}** of {int(nc.lot_area_sqft.notna().sum())} non-condo sites with a parsed area.
Median ratio: {nc.lot_area_ratio.median():.3f}.

## Flags (non-condo sites)
| flag | sites |
|---|---|
""" + "\n".join(f"| {f} | {int(nc[f].sum())} |" for f in flags) + f"""

Constraint overlap threshold: a layer polygon must cover ≥ {int(MIN_OVERLAP_SHARE * 100)}% of a site.
"""
    return md


def main() -> None:
    raw_path = find_cached("parcels.geojson")
    print("Loading layers…")
    parcels = load_layer("parcels")
    zoning = load_layer("zoning")
    layers = {l["key"]: load_layer(l["key"]) for l in config.CONSTRAINT_LAYERS}

    print("Parsing records…")
    rec = parse_records(parcels)
    rec, merge_stats = assign_additional_lots(rec)

    print("Building sites…")
    sites = build_sites(rec)
    print("Spatial joins…")
    sites = join_zoning(sites, zoning)
    sites = join_constraints(sites, layers)

    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(config.PROCESSED / "sites.parquet")
    rec.drop(columns="geometry").to_parquet(config.PROCESSED / "records.parquet")
    report = write_report(rec, sites, merge_stats, str(raw_path.parent.relative_to(config.ROOT)))
    (config.PROCESSED / "data_quality.md").write_text(report)
    print(f"Wrote {len(sites)} sites → data/processed/sites.parquet")
    print("Report → data/processed/data_quality.md")


if __name__ == "__main__":
    main()
