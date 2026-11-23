"""Download zoning, constraint and parcel layers as GeoJSON into data/raw/YYYY-MM-DD/.

Usage:
    python -m pipeline.fetch            # use cache where present
    python -m pipeline.fetch --refresh  # re-download everything into today's folder
"""
from __future__ import annotations

import argparse
import json

from . import config
from .http_client import find_cached, get_json_cached, polite_get, today_dir


def layer_metadata(key: str, url: str, refresh: bool) -> dict:
    meta = get_json_cached(f"{key}.meta.json", url, {"f": "json"}, refresh)
    if "error" in meta:
        raise RuntimeError(f"{key}: service error {meta['error']}")
    return meta


def fetch_layer(key: str, url: str, out_fields: list[str] | str = "*",
                page_size: int | None = None, refresh: bool = False,
                postprocess=None) -> dict:
    """Page through a FeatureServer layer and return one merged GeoJSON FeatureCollection.

    Each page is cached as <key>.page_NNNN.geojson in today's folder so an interrupted
    run resumes without re-requesting pages; the merged file is <key>.geojson.
    """
    merged_name = f"{key}.geojson"
    if not refresh and (cached := find_cached(merged_name)):
        print(f"[cache] {key}: {cached}")
        return json.loads(cached.read_text())

    meta = layer_metadata(key, url, refresh)
    oid = meta.get("objectIdField") or "OBJECTID"
    page_size = page_size or meta.get("maxRecordCount") or 1000
    fields = out_fields if isinstance(out_fields, str) else ",".join(out_fields)

    count = polite_get(f"{url}/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"}).json()["count"]
    print(f"[fetch] {key}: {count} features, page size {page_size}")

    out_dir = today_dir()
    features: list[dict] = []
    offset, page = 0, 0
    while True:
        page_file = out_dir / f"{key}.page_{page:04d}.geojson"
        if page_file.exists() and not refresh:
            data = json.loads(page_file.read_text())
        else:
            params = {
                "where": "1=1", "outFields": fields, "returnGeometry": "true",
                "orderByFields": oid,  # stable ordering is required for offset paging
                "resultOffset": offset, "resultRecordCount": page_size,
                "outSR": 4326, "f": "geojson",
            }
            data = polite_get(f"{url}/query", params).json()
            if "error" in data:
                raise RuntimeError(f"{key} page {page}: {data['error']}")
            if postprocess:  # applied before anything touches disk
                data = postprocess(data)
            page_file.write_text(json.dumps(data))
        batch = data.get("features", [])
        features.extend(batch)
        print(f"  page {page}: +{len(batch)} (total {len(features)})")
        # Stop when the server says there is no more, or a short page arrives.
        more = data.get("exceededTransferLimit") or (data.get("properties") or {}).get("exceededTransferLimit")
        if not batch or (not more and len(batch) < page_size) or len(features) >= count:
            break
        offset += len(batch)
        page += 1

    if len(features) != count:
        print(f"  WARNING: {key} expected {count} features, got {len(features)}")
    fc = {"type": "FeatureCollection", "features": features}
    (out_dir / merged_name).write_text(json.dumps(fc))
    for p in out_dir.glob(f"{key}.page_*.geojson"):  # merged file is the cache of record
        p.unlink()
    return fc


def sanitize_parcels(fc: dict) -> dict:
    """Second line of privacy defence: drop any property not on the allow-list."""
    allowed = set(config.PARCEL_FIELDS)
    for f in fc["features"]:
        props = f.get("properties") or {}
        leaked = config.FORBIDDEN_FIELDS & props.keys()
        if leaked:
            raise RuntimeError(f"Forbidden fields returned by server: {leaked}")
        f["properties"] = {k: v for k, v in props.items() if k in allowed}
    return fc


def fetch_all(refresh: bool = False) -> None:
    fetch_layer(config.ZONING_LAYER["key"], config.ZONING_LAYER["url"], refresh=refresh)
    for layer in config.CONSTRAINT_LAYERS:
        fetch_layer(layer["key"], layer["url"], refresh=refresh)
    fetch_layer("parcels", config.PARCELS_URL, config.PARCEL_FIELDS,
                page_size=config.PARCEL_PAGE_SIZE, refresh=refresh, postprocess=sanitize_parcels)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    fetch_all(ap.parse_args().refresh)


if __name__ == "__main__":
    main()
