"""Collect the source documents behind every Hoboken zone and redevelopment plan.

Usage:
    python -m pipeline.rules_fetch [--refresh]

Automatic: City Zoning Guide pages. Their text is read from the public ArcGIS item-data
API (the Hub page itself is a JavaScript shell); raw JSON is cached in data/raw/<date>/.

Manual: these sources cannot be fetched politely by a script, so you save them yourself:
  * ecode360.com ordinance sections: Cloudflare bot challenge (HTTP 403 "Just a moment...")
  * hostedfiles.civilsolutions.biz plan PDFs: robots.txt says "Disallow: /"
Save them where data/sources/SOURCES.md says; this script detects them on the next run.

Outputs: data/sources/manifest.json, data/sources/SOURCES.md, data/sources/guide/<slug>.txt
"""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

from . import config
from .clean import clean_str, href, load_layer
from .http_client import get_json_cached

GUIDE_DIR = config.SOURCES / "guide"
ORD_DIR = config.SOURCES / "ordinance"
PLAN_DIR = config.SOURCES / "plans"
MANUAL_EXTS = (".html", ".htm", ".pdf", ".txt")

# Hosts verified (2026-11-23) as not politely fetchable by a script, and why.
MANUAL_HOSTS = {
    "ecode360.com": "Cloudflare bot challenge (HTTP 403)",
    "hostedfiles.civilsolutions.biz": "robots.txt disallows all crawlers",
}

_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


def robots_allows(url: str) -> bool:
    host = urlparse(url).netloc
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None  # unreachable robots.txt: treat as no restrictions
        _robots[host] = rp
    rp = _robots[host]
    return rp is None or rp.can_fetch(config.USER_AGENT, url)


def ecode_id(url: str | None) -> str | None:
    m = re.search(r"ecode360\.com/(\d+)", url or "")
    return m.group(1) if m else None


# ------------------------------------------------------------------ zone list
def build_zone_list() -> list[dict]:
    """One entry per rule set: base districts, RPA plan areas, and other redevelopment/rehab plans."""
    zoning = load_layer("zoning")
    rr = load_layer("rehab_redev")
    zones: dict[str, dict] = {}
    for r in zoning.itertuples():
        zone = clean_str(r.Zone_)
        name = clean_str(r.CommZone) or zone
        if zone == "RPA":
            plan = re.sub(r"\s*-\s*RPA$", "", name)
            key, kind = f"RPA:{plan}", "redevelopment_plan"
        else:
            key, kind = zone, "base_district"
        z = zones.setdefault(key, {"zone_key": key, "label": name, "kind": kind, "sources": []})
        for typ, url in (("ordinance", href(r.Hyperlink)), ("plan", href(r.Hyperlink2)), ("guide", href(r.Guide))):
            if url and url not in [s["url"] for s in z["sources"]]:
                z["sources"].append({"type": typ, "url": url, "via": "zoning layer"})

    # Redevelopment / rehabilitation layer: newer plan links for RPAs, and plan areas
    # (e.g. Neumann Leathers, Southwest, Post Office) that are not zoning-layer polygons.
    for r in rr.itertuples():
        name = clean_str(r.Rehab_Area) or clean_str(r.CommZone)
        url = href(r.Hyperlink)
        kind_txt = f"{clean_str(r.RehabRedev)} ({clean_str(r.OverlaySup)})"
        rpa_key = f"RPA:{clean_str(r.CommZone)}"
        key = rpa_key if rpa_key in zones else f"PLAN:{name}"
        z = zones.setdefault(key, {"zone_key": key, "label": name, "kind": "redevelopment_plan", "sources": []})
        z["plan_type"] = kind_txt
        if url and url.lower() not in [s["url"].lower() for s in z["sources"]]:
            z["sources"].append({"type": "plan", "url": url, "via": "redevelopment layer"})
    return sorted(zones.values(), key=lambda z: (z["kind"] != "base_district", z["zone_key"]))


# ------------------------------------------------------------------ guide pages (automatic)
def _collect_text(obj, out: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("text", "markdown") and isinstance(v, str):
                out.append(v)
            else:
                _collect_text(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_text(v, out)


def html_to_text(s: str) -> str:
    s = re.sub(r"<(br|/p|/li|/h\d|/tr|/div)[^>]*>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def fetch_guides(zones: list[dict], refresh: bool) -> None:
    site = get_json_cached("guide_site.json", config.ARCGIS_ITEM_DATA.format(id=config.GUIDE_SITE_ITEM), refresh=refresh)
    pages = {p["slug"]: p["id"] for p in site.get("values", {}).get("pages", [])}
    GUIDE_DIR.mkdir(parents=True, exist_ok=True)
    for z in zones:
        for s in z["sources"]:
            if s["type"] != "guide":
                continue
            slug = s["url"].rstrip("/").rsplit("/", 1)[-1]
            page_id = pages.get(slug)
            if not page_id:
                s["status"] = f"missing: no page '{slug}' in the Hub site"
                continue
            api = config.ARCGIS_ITEM_DATA.format(id=page_id)
            if not robots_allows(api):
                s["status"] = "manual: robots.txt disallows"
                continue
            data = get_json_cached(f"guide_{slug}.json", api, refresh=refresh)
            parts: list[str] = []
            _collect_text(data, parts)
            text = html_to_text("\n".join(parts))
            path = GUIDE_DIR / f"{slug}.txt"
            path.write_text(text)
            s.update(status="ok", local_path=str(path.relative_to(config.ROOT)), fetched_via=api)


# ------------------------------------------------------------------ manual sources
def expected_name(s: dict) -> str:
    if s["type"] == "ordinance":
        return f"ecode_{ecode_id(s['url'])}.html"
    return Path(urlparse(s["url"]).path).name  # the browser's default "Save as" name


def locate_manual(s: dict) -> Path | None:
    folder = ORD_DIR if s["type"] == "ordinance" else PLAN_DIR
    if not folder.exists():
        return None
    stem = Path(expected_name(s)).stem.lower()
    for p in folder.iterdir():
        if p.suffix.lower() in MANUAL_EXTS and p.stem.lower() == stem:
            return p
    return None


def resolve_manual(zones: list[dict]) -> None:
    for z in zones:
        for s in z["sources"]:
            if s["type"] == "guide":
                continue
            s["save_as"] = str(((ORD_DIR if s["type"] == "ordinance" else PLAN_DIR) / expected_name(s)).relative_to(config.ROOT))
            if p := locate_manual(s):
                s.update(status="ok", local_path=str(p.relative_to(config.ROOT)))
            else:
                host = urlparse(s["url"]).netloc.lower()
                s["status"] = f"manual: {MANUAL_HOSTS.get(host, 'save manually')}"


def write_checklist(zones: list[dict]) -> None:
    rows, seen = [], set()
    for z in zones:
        for s in z["sources"]:
            if s["type"] == "guide" or s["url"] in seen:
                continue
            seen.add(s["url"])
            users = [x["zone_key"] for x in zones if s["url"] in [y["url"] for y in x["sources"]]]
            done = "✅" if s["status"] == "ok" else "⬜"
            rows.append(f"| {done} | {', '.join(users)} | {s['type']} | {s['url']} | `{s['save_as']}` |")
    guide_rows = [f"| {'✅' if s.get('status') == 'ok' else '❌'} | {z['zone_key']} | {s['url']} |"
                  for z in zones for s in z["sources"] if s["type"] == "guide"]
    md = f"""# Rule sources

Run `python -m pipeline.rules_fetch` after saving files to update this list.

## Manual sources
These cannot be fetched politely by a script:
- **ecode360.com** (ordinance): Cloudflare bot challenge. Open the link in your browser and use
  *File → Save Page As… → Webpage, HTML only* (or print to PDF) with the file name shown.
  `.html`, `.pdf` or `.txt` all work, as long as the name before the extension matches.
- **hostedfiles.civilsolutions.biz** (plan PDFs): robots.txt disallows crawlers. Open the link and
  save the PDF under the name shown (the browser's default name).

| | used by | type | URL | save as |
|---|---|---|---|---|
""" + "\n".join(rows) + """

## Fetched automatically: City Zoning Guide
| | zone | page |
|---|---|---|
""" + "\n".join(guide_rows) + "\n"
    (config.SOURCES / "SOURCES.md").write_text(md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    zones = build_zone_list()
    fetch_guides(zones, args.refresh)
    resolve_manual(zones)
    (config.SOURCES / "manifest.json").write_text(json.dumps(zones, indent=2))
    write_checklist(zones)
    n_ok = sum(s.get("status") == "ok" for z in zones for s in z["sources"])
    n_all = sum(len(z["sources"]) for z in zones)
    print(f"{len(zones)} rule sets, {n_ok}/{n_all} sources available. Checklist: data/sources/SOURCES.md")
    for z in zones:
        have = [s["type"] for s in z["sources"] if s.get("status") == "ok"]
        print(f"  {z['zone_key']:32} available: {', '.join(have) or '— none yet'}")


if __name__ == "__main__":
    main()
