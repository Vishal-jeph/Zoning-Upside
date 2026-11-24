"""Extract per-zone rules from cached source documents with an LLM (Groq free tier).

Usage:
    python -m pipeline.rules_extract                 # every zone with at least one source
    python -m pipeline.rules_extract --zone R-1 C-1  # selected zones
    python -m pipeline.rules_extract --no-llm        # re-run post-processing from cached LLM replies only

Every value must carry a verbatim quote. After the LLM answers we check, in code, that
(1) the quote really occurs in the source text and (2) the number appears in the quote.
Failures are flagged for the review page, never silently accepted.
Output: data/rules/extracted_rules.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .rules_schema import ALL_FIELDS, NUMERIC_FIELDS, SEEDS, llm_json_schema

CACHE_DIR = config.RULES / "llm_cache"
OUT = config.RULES / "extracted_rules.json"

# Groq free tier for gpt-oss-120b: 8,000 tokens/minute (prompt + output + reasoning).
TOKENS_PER_MINUTE = 7_500          # stay a little under the published limit
CHUNK_CHARS = 14_000               # ≈ 3,500 tokens of source text per request
MAX_CHUNKS_PER_ZONE = 6            # long plans: only the most rule-dense passages
MAX_OUTPUT_TOKENS = 3_000
SOURCE_PRIORITY = {"ordinance": 3, "plan": 3, "guide": 1}  # the law outranks the plain-language guide

# Words that mark bulk/density passages, used to pick passages from long documents.
KEYWORDS = re.compile(
    r"height|stor(?:y|ies)|feet|ft\.|density|dwelling units?|units per|lot coverage|building coverage|"
    r"lot area|lot width|lot depth|floor area ratio|\bFAR\b|floor-to-floor|flood elevation|step-?back|"
    r"bulk|permitted uses?|residential", re.I)

WORDS_TO_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20}


# ------------------------------------------------------------------ documents → text
def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(errors="ignore")
    if suffix in (".html", ".htm"):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(path.read_text(errors="ignore"), "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()
        main = soup.select_one("#codeContent, #mainContent, main, article") or soup
        return re.sub(r"\n\s*\n+", "\n\n", main.get_text("\n")).strip()
    if suffix == ".pdf":
        import fitz  # PyMuPDF
        with fitz.open(path) as doc:
            return "\n".join(f"[page {i + 1}]\n{p.get_text()}" for i, p in enumerate(doc))
    raise ValueError(f"unsupported source type: {path}")


def chunk_text(text: str) -> list[str]:
    """Split into ~CHUNK_CHARS pieces on paragraph boundaries; keep the most rule-dense ones."""
    paras = re.split(r"\n\s*\n|(?=\[page \d+\])", text)
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > CHUNK_CHARS and cur:
            chunks.append(cur)
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        chunks.append(cur)
    if len(chunks) <= MAX_CHUNKS_PER_ZONE:
        return chunks
    scored = sorted(range(len(chunks)), key=lambda i: -len(KEYWORDS.findall(chunks[i])))
    keep = sorted(scored[:MAX_CHUNKS_PER_ZONE])  # original order
    return [chunks[i] for i in keep]


# ------------------------------------------------------------------ LLM
_window: deque[tuple[float, int]] = deque()


def _throttle(tokens: int) -> None:
    """Simple sliding-window limiter for the per-minute token budget."""
    while True:
        now = time.monotonic()
        while _window and now - _window[0][0] > 60:
            _window.popleft()
        if sum(t for _, t in _window) + tokens <= TOKENS_PER_MINUTE or not _window:
            _window.append((now, tokens))
            return
        time.sleep(max(1.0, 60 - (now - _window[0][0]) + 0.5))


SYSTEM = """You extract zoning rules for ONE zoning district (or redevelopment plan) in Hoboken, NJ.
Rules:
- Use ONLY the supplied source text. Never use outside knowledge. If a value is not stated, return null.
- Every non-null value needs a short VERBATIM quote (copied character for character, at most 40 words)
  and the source_id (S1, S2, ...) it came from.
- If the text covers several districts, extract only the requested one. For a redevelopment plan with
  sub-districts, return one entry per sub-district (use the plan's own sub-district names).
- For a base district return exactly one entry with name = null.
- Heights: give feet and stories separately; height_rule_text is the rule as written. Use
  height_limits_combine = "whichever_is_less" only if the text says so (or equivalent).
- Building type: if the text states a height/story limit for one building type only, use the typed fields:
  max_height_ft_commercial / max_stories_commercial for commercial buildings, and
  max_height_ft_residential / max_stories_residential for residential or mixed-use buildings (e.g.
  "residential floors over a commercial floor" is mixed-use). Use max_height_ft / max_stories only for a
  limit stated for all principal buildings without naming a type. Never copy a limit into another type.
- min_floor_to_floor_ft: when residential and commercial minimums differ, give the residential one.
- Use principal-building rules, not accessory structures. Lot coverage as a percent number (60, not 0.6).
- density_structured: "site_area_per_unit" when units = lot area / N sq ft; "units_per_acre"; "max_units";
  "formula" for anything else; "none" if residential use is not permitted. Otherwise null.
- special_conditions: neighbour-height matching, step-backs, flood rules, historic review, use limits, bonuses.
- confidence: high = explicit number in the text; medium = needs light interpretation; low = uncertain."""


def call_llm(zone: dict, sources: list[dict], chunk: str, chunk_label: str, model: str, use_llm: bool) -> dict | None:
    src_list = "\n".join(f"{s['sid']}: {s['type']} — {s['url']}" for s in sources)
    user = (f"District: {zone['zone_key']} ({zone['label']})\nSources:\n{src_list}\n\n"
            f"Source text ({chunk_label}):\n<<<\n{chunk}\n>>>")
    key = hashlib.sha256(f"{model}\n{SYSTEM}\n{user}".encode()).hexdigest()[:24]
    cache = CACHE_DIR / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    if not use_llm:
        return None

    from groq import Groq, RateLimitError
    client = Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=0)
    est = (len(SYSTEM) + len(user)) // 3 + MAX_OUTPUT_TOKENS
    for attempt in range(5):
        _throttle(est)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "zone_rules", "strict": True, "schema": llm_json_schema()}},
                temperature=0,
                max_completion_tokens=MAX_OUTPUT_TOKENS,
                reasoning_effort="low",
            )
            data = json.loads(resp.choices[0].message.content)
            data["_meta"] = {"model": model, "usage": resp.usage.model_dump() if resp.usage else None,
                             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data, indent=1))
            return data
        except RateLimitError as e:
            wait = float(e.response.headers.get("retry-after", 30)) + 1
            print(f"    rate limited; waiting {wait:.0f}s")
            time.sleep(wait)
        except Exception as e:  # schema failures etc.: retry, then give up on this chunk
            print(f"    LLM error ({type(e).__name__}: {str(e)[:160]}); attempt {attempt + 1}")
            time.sleep(5)
    return None


# ------------------------------------------------------------------ verification
def _norm(s: str) -> str:
    """Lower-case alphanumerics only: tolerant of whitespace/punctuation/hyphenation noise in sources."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def quote_found(quote: str | None, text: str) -> bool:
    """True if the quote occurs in the text. A quote shortened with '...' passes only if every
    piece occurs, in order."""
    if not quote:
        return False
    hay, pos = _norm(text), 0
    for piece in re.split(r"\.\.\.|…", quote):
        p = _norm(piece)
        if not p:
            continue
        idx = hay.find(p, pos)
        if idx < 0:
            return False
        pos = idx + len(p)
    return pos > 0


def number_in_quote(value, quote: str | None) -> bool:
    if value is None or not quote:
        return False
    q = quote.lower().replace(",", "")
    nums = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", q)}
    nums |= {float(v) for w, v in WORDS_TO_NUM.items() if re.search(rf"\b{w}\b", q)}
    v = float(value)
    return v in nums or (v * 100 in nums) or (v / 100 in nums)  # tolerate 0.6 vs 60%


def verify(entry: dict, field: str, texts: dict[str, str]) -> dict:
    """Attach verification flags; downgrade confidence when evidence doesn't check out."""
    out = dict(entry)
    sid = out.get("source_id")
    text = texts.get(sid, "")
    if out.get("value") is None:
        return out
    issues = []
    if not out.get("quote"):
        issues.append("no quote")
    elif not quote_found(out["quote"], text):
        # The model may have cited the wrong source id: search all sources.
        alt = next((s for s, t in texts.items() if quote_found(out["quote"], t)), None)
        if alt:
            out["source_id"] = alt
        else:
            issues.append("quote not found in source text")
    if field in NUMERIC_FIELDS or field == "density_structured":
        v = out.get("value")
        if isinstance(v, (int, float)) and not number_in_quote(v, out.get("quote")):
            issues.append("number not in quote")
    out["verified"] = not issues
    out["issues"] = issues
    if issues:
        out["confidence"] = "low"
    return out


# ------------------------------------------------------------------ merge
def _rank(c: dict) -> tuple:
    conf = {"high": 3, "medium": 2, "low": 1}.get(c.get("confidence") or "", 0)
    return (c.get("verified", False), c.get("source_priority", 0), conf)


def merge_districts(results: list[tuple[dict, dict]], texts: dict, src_by_id: dict) -> list[dict]:
    """Combine chunk-level answers into one record per (sub-)district, keeping disagreements visible."""
    by_name: dict[str, dict] = {}
    for res, _meta in results:
        for d in res.get("districts", []):
            name = (d.get("name") or "").strip() or None
            key = _norm(name or "") or "_base"
            rec = by_name.setdefault(key, {"name": name, "candidates": {}, "special_conditions": []})
            for f in ALL_FIELDS:
                e = d.get(f) or {}
                if e.get("value") is None:
                    continue
                e = verify(e, f, texts)
                src = src_by_id.get(e.get("source_id"), {})
                e["source_url"], e["source_type"] = src.get("url"), src.get("type")
                e["source_priority"] = SOURCE_PRIORITY.get(src.get("type"), 0)
                rec["candidates"].setdefault(f, []).append(e)
            ds = d.get("density_structured") or {}
            if ds.get("type"):
                v = ds.get("site_area_per_unit_sqft") or ds.get("units_per_acre") or ds.get("max_units")
                e = verify({**ds, "value": v}, "density_structured", texts) if v is not None else \
                    {**ds, "value": None, "verified": quote_found(ds.get("quote"), "\n".join(texts.values()))}
                if "issues" not in e:
                    e["issues"] = [] if e["verified"] else ["quote not found in source text"]
                src = src_by_id.get(e.get("source_id"), {})
                e["source_url"], e["source_type"] = src.get("url"), src.get("type")
                e["source_priority"] = SOURCE_PRIORITY.get(src.get("type"), 0)
                rec["candidates"].setdefault("density_structured", []).append(e)
            for sc in d.get("special_conditions") or []:
                src = src_by_id.get(sc.get("source_id"), {})
                sc = {**sc, "verified": quote_found(sc.get("quote"), "\n".join(texts.values())),
                      "source_url": src.get("url")}
                if _norm(sc["text"]) not in {_norm(x["text"]) for x in rec["special_conditions"]}:
                    rec["special_conditions"].append(sc)

    out = []
    for rec in by_name.values():
        fields, conflicts = {}, []
        for f, cands in rec["candidates"].items():
            cands = sorted(cands, key=_rank, reverse=True)
            best = cands[0]
            distinct = {json.dumps(c.get("value"), sort_keys=True) for c in cands if c.get("verified")}
            alts = [c for c in cands[1:] if json.dumps(c.get("value"), sort_keys=True) != json.dumps(best.get("value"), sort_keys=True)]
            fields[f] = {**best, "alternatives": alts}
            if len(distinct) > 1:
                conflicts.append(f)
        # Consistency: density "none" means residential use is not allowed; it must agree with
        # residential_permitted, otherwise the density value is not trusted.
        ds, rp = fields.get("density_structured"), (fields.get("residential_permitted") or {}).get("value")
        if ds and ds.get("type") == "none" and rp in ("yes", "conditional"):
            ds["verified"] = False
            ds["confidence"] = "low"
            ds["issues"] = [*ds.get("issues", []), f"density type 'none' but residential_permitted = {rp}"]
        dedupe_building_type(fields)
        out.append({"name": rec["name"], "fields": fields, "conflicts": conflicts,
                    "special_conditions": rec["special_conditions"]})
    return out


def dedupe_building_type(fields: dict) -> None:
    """A general height/story limit that just repeats a building-type limit (same value, same quote) was
    stated for that type only, so it is not a limit for all buildings: clear it and say why."""
    for base in ("max_height_ft", "max_stories"):
        g = fields.get(base) or {}
        for suffix in ("_commercial", "_residential"):
            t = fields.get(base + suffix) or {}
            if g.get("value") is not None and t.get("value") == g.get("value") and t.get("quote") == g.get("quote"):
                fields[base] = {"value": None, "quote": None, "source_id": None, "confidence": None,
                                "verified": False, "alternatives": [g],
                                "issues": [f"moved to {base + suffix}: the quote states it for that building type only"]}
                break


# ------------------------------------------------------------------ main
def seed_check(zone_key: str, districts: list[dict]) -> dict | None:
    seed = SEEDS.get(zone_key)
    if not seed or not districts:
        return None
    fields = districts[0]["fields"]
    diffs = {f: {"seed": v, "extracted": (fields.get(f) or {}).get("value")}
             for f, v in seed["values"].items() if (fields.get(f) or {}).get("value") != v}
    return {**seed, "agrees": not diffs, "differences": diffs}


def extract_zone(zone: dict, model: str, use_llm: bool) -> dict:
    sources, texts = [], {}
    for s in zone["sources"]:
        if s.get("status") != "ok":
            continue
        sid = f"S{len(sources) + 1}"
        text = load_text(config.ROOT / s["local_path"])
        if len(text.strip()) < 200:
            print(f"    {sid} {s['local_path']}: almost no text (scanned PDF needs OCR?)")
        sources.append({**s, "sid": sid, "chars": len(text)})
        texts[sid] = text
    base = {"zone_key": zone["zone_key"], "label": zone["label"], "kind": zone["kind"],
            "plan_type": zone.get("plan_type"),
            "sources": [{k: s.get(k) for k in ("sid", "type", "url", "local_path", "chars")} for s in sources],
            "missing_sources": [{"type": s["type"], "url": s["url"], "save_as": s.get("save_as")}
                                for s in zone["sources"] if s.get("status") != "ok"]}
    if not sources:
        return {**base, "status": "no_sources", "districts": []}

    results = []
    for s in sources:
        chunks = chunk_text(texts[s["sid"]])
        for i, ch in enumerate(chunks):
            label = f"{s['sid']} part {i + 1}/{len(chunks)}"
            print(f"    {label} ({len(ch):,} chars)")
            res = call_llm(zone, sources, f"[{s['sid']}]\n{ch}", label, model, use_llm)
            if res is None:
                return {**base, "status": "llm_pending" if not use_llm else "llm_failed", "districts": []}
            results.append((res, {"sid": s["sid"], "chunk": i}))
    districts = merge_districts(results, texts, {s["sid"]: s for s in sources})
    return {**base, "status": "extracted", "districts": districts,
            "seed_check": seed_check(zone["zone_key"], districts)}


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(config.ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", nargs="*", help="zone keys to (re)extract; default: all")
    ap.add_argument("--no-llm", action="store_true", help="use cached LLM replies only")
    args = ap.parse_args()
    model = os.environ.get("GROQ_MODEL") or config.GROQ_DEFAULT_MODEL
    if not args.no_llm and not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY missing: copy .env.example to .env and add your key.")

    manifest = json.loads((config.SOURCES / "manifest.json").read_text())
    previous = json.loads(OUT.read_text())["zones"] if OUT.exists() else {}
    zones_out = dict(previous)
    for zone in manifest:
        if args.zone and zone["zone_key"] not in args.zone:
            continue
        print(f"[{zone['zone_key']}]")
        zones_out[zone["zone_key"]] = extract_zone(zone, model, not args.no_llm)
        r = zones_out[zone["zone_key"]]
        print(f"    → {r['status']}, {len(r['districts'])} district record(s)"
              + (f", seed agrees={r['seed_check']['agrees']}" if r.get("seed_check") else ""))
        OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                   "model": model, "zones": zones_out}, indent=1))
    print(f"Wrote {OUT.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
