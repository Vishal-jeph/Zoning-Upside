"""Building footprint cross-check (Overture Maps, free open data).

    python -m pipeline.overture [--refresh]

Tax records lag behind reality: a lot described as vacant may already have a new building, and
parsed floors can be outdated. Overture building footprints (mostly OpenStreetMap + ML-derived
footprints) give an independent view.

Cache: data/raw/overture/<release>/buildings.parquet — downloaded once per release, only for the
Hoboken bounding box. Fields kept: id, geometry, height (m), num_floors, sources.
"""
from __future__ import annotations

import argparse
import json

import geopandas as gpd
import pandas as pd

from . import config

FT_PER_M = 3.28084
OVERTURE_DIR = config.RAW / "overture"
# A building counts toward a site's height/floors when at least this share of the building lies
# inside the site, or it covers at least this share of the site (large footprints spanning lots).
DOMINANT_SHARE = 0.5


def cached_release() -> str | None:
    """Newest cached release folder that holds buildings.parquet."""
    if not OVERTURE_DIR.exists():
        return None
    rels = sorted(p.name for p in OVERTURE_DIR.iterdir() if (p / "buildings.parquet").exists())
    return rels[-1] if rels else None


def fetch(bbox: tuple[float, float, float, float], refresh: bool = False) -> str:
    """Download buildings for bbox (W, S, E, N in WGS84) unless a cached release exists."""
    have = cached_release()
    if have and not refresh:
        return have
    from overturemaps import core  # imported lazily: only needed when downloading

    release = core.get_latest_release()
    out = OVERTURE_DIR / release / "buildings.parquet"
    if out.exists():
        return release
    print(f"Downloading Overture buildings, release {release}, bbox {bbox} …")
    gdf = core.geodataframe("building", bbox=bbox, release=release)
    keep = gdf[["id", "geometry", "height", "num_floors", "sources"]].copy()
    # sources is a list of structs; keep just the dataset names as text.
    keep["sources"] = keep["sources"].map(
        lambda v: ",".join(sorted({str(s.get("dataset")) for s in v})) if v is not None else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    keep.set_crs(config.CRS_WGS84, allow_override=True).to_parquet(out)
    (out.parent / "meta.json").write_text(json.dumps(
        {"release": release, "bbox": [float(x) for x in bbox], "rows": len(keep), "downloaded_at": pd.Timestamp.now().isoformat()}))
    print(f"  {len(keep)} buildings → {out.relative_to(config.ROOT)}")
    return release


def load(release: str) -> gpd.GeoDataFrame:
    return gpd.read_parquet(OVERTURE_DIR / release / "buildings.parquet").to_crs(config.CRS_FEET)


def footprint_stats(sites: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame) -> pd.DataFrame:
    """Per site (both in a feet CRS): footprint_coverage_pct, overture_max_height_ft, overture_num_floors,
    overture_building_count. Coverage uses the union of footprints so overlapping parts aren't double-counted."""
    s = sites[["site_id", "geometry"]].copy()
    s["site_area"] = s.area
    b = buildings[["id", "geometry", "height", "num_floors"]].copy()
    b["bldg_area"] = b.area
    inter = gpd.overlay(s, b, how="intersection", keep_geom_type=True)
    if inter.empty:
        return pd.DataFrame({"site_id": s.site_id, "footprint_coverage_pct": 0.0, "overture_max_height_ft": None,
                             "overture_num_floors": None, "overture_building_count": 0})
    inter["ia"] = inter.area
    cover = inter.dissolve(by="site_id")[["geometry"]]
    cover["covered"] = cover.area
    dom = inter[(inter.ia >= DOMINANT_SHARE * inter.bldg_area) | (inter.ia >= DOMINANT_SHARE * inter.site_area)]
    agg = dom.groupby("site_id").agg(overture_max_height_m=("height", "max"), overture_num_floors=("num_floors", "max"),
                                     overture_building_count=("id", "nunique"))
    out = s[["site_id", "site_area"]].merge(cover[["covered"]], left_on="site_id", right_index=True, how="left") \
        .merge(agg, left_on="site_id", right_index=True, how="left")
    out["footprint_coverage_pct"] = (out.covered.fillna(0) / out.site_area * 100).clip(0, 100).round(1)
    out["overture_max_height_ft"] = (out.overture_max_height_m * FT_PER_M).round(1)
    out["overture_building_count"] = out.overture_building_count.fillna(0).astype(int)
    return out[["site_id", "footprint_coverage_pct", "overture_max_height_ft", "overture_num_floors",
                "overture_building_count"]]


def hoboken_bbox(sites: gpd.GeoDataFrame, pad: float = 0.002) -> tuple[float, float, float, float]:
    w, s, e, n = sites.to_crs(config.CRS_WGS84).total_bounds
    return (round(w - pad, 5), round(s - pad, 5), round(e + pad, 5), round(n + pad, 5))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="download the latest release even if one is cached")
    args = ap.parse_args()
    sites = gpd.read_parquet(config.PROCESSED / "sites.parquet")
    print("Release:", fetch(hoboken_bbox(sites), refresh=args.refresh))
