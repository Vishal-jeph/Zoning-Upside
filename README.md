# Zoning Upside — Hoboken

Finds Hoboken, NJ properties where zoning appears to allow a bigger building (more floors and/or
units) than what stands there today. **Estimates based on public zoning text; verify with the
Hoboken Zoning Office.**

> Work in progress, built phase by phase. Full architecture, deploy and limitations docs arrive in Phase 6.

## Phase 1: data download and cleaning

```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -r pipeline/requirements.txt
.venv/bin/python -m pipeline            # fetch (cached) + clean
.venv/bin/python -m pipeline --refresh  # re-download all source layers into data/raw/<today>/
.venv/bin/python -m pytest pipeline/tests
```

Outputs:
- `data/processed/sites.parquet`: one row per development site (EPSG:3424, US feet)
- `data/processed/data_quality.md`: parse rates, mismatches, top unparsed patterns

### Privacy
The parcel service also carries owner names and mailing addresses. They are never requested:
`pipeline/config.py` allow-lists the fields, and `fetch.py` rejects any response that contains them.

### Politeness
At most one request per second. Every response is cached under `data/raw/YYYY-MM-DD/`
and is not downloaded again unless `--refresh` is passed.

### How tax records become sites
- **Condo units** (qualifier `C…`, bedroom-style building descriptions, share-style lot
  descriptions, `COMMON ELEMENT`) are grouped into one *condo building* site. These sites are
  excluded from ranking by default, because one unit owner cannot redevelop the building.
- **Combined lots:** a property spanning several lots repeats the same tax record on each lot,
  sometimes listed in `M4_Additional_Lots` and sometimes not. Those lots are merged into one
  site so the land is counted once.
- **Zone** comes from the zoning map polygon covering most of the site. The tax record's
  `M4_Zone` is kept and any disagreement is flagged.

## Phase 2: zone rules extraction and human review

```bash
.venv/bin/python -m pipeline.rules_fetch      # build source list, fetch Zoning Guide pages, write the checklist
.venv/bin/python -m pipeline.rules_extract    # LLM extraction (Groq) for zones that have sources
cd web && npm install && npm run dev          # then open http://localhost:3000/rules/review
```

**Sources.** Each zone draws on up to three documents: the ordinance section (ecode360), the
redevelopment plan PDF, and the City's Zoning Guide page.
- The Guide pages are fetched automatically through the public ArcGIS item API.
- ecode360 sits behind a Cloudflare bot challenge, and the plan-PDF host's robots.txt disallows
  crawlers, so you save those files yourself. `data/sources/SOURCES.md` lists every URL and the
  file name to save it under.

**Extraction.** The extractor uses `openai/gpt-oss-120b` on the Groq free tier, which allows
8k tokens per minute; the code throttles itself to stay under that. The model must return
`null` for anything the text doesn't state, and a verbatim quote for every value. The code then
checks that each quote occurs in the source and that each number appears in its quote. Failures
are flagged on the review page, never silently accepted. Every LLM reply is cached in
`data/rules/llm_cache/`.

**Review.** `/rules/review` works only under `npm run dev`; its API returns 403 in a production
build. It shows a zones × fields grid. For each zone you see:
- every value with its quote and source link
- values from other sources that disagree
- a comparison with the seed values from the brief (R-1, C-1)

Approving a zone writes it to `data/rules/hoboken_rules.json` with `approved_by: "manual"` and
the date. If you change a value, the page records it as `confirmed_on_review` and requires a
note saying where you confirmed it. Only approved zones are used in calculations.

**Demo scope.** The demo uses the 7 zones approved from the Zoning Guide (R-1, R-2, R-3, R-CP,
C-1, C-2, C-3). They cover 2,559 of the 2,835 non-condo sites (90%). Sites in other zones stay
in the data as `rules_not_loaded` and are not scored.

## Phase 3: potential and scoring

```bash
.venv/bin/python -m pipeline.potential   # or: python -m pipeline  (runs phases 1 + 3)
```

For each non-condo site in an approved zone:

- **Allowed stories.** The lower of the story limit and `floor(max height ÷ floor-to-floor)`.
  Floor-to-floor is the zone's stated minimum, or 10 ft when the zone states none. A building
  must meet every stated limit, so the lower one binds.
- **Allowed units.** Lot area ÷ sq ft per unit, rounded as the rule says. When the rule doesn't
  say how to round, the result is rounded down. Zones without a numeric density rule (C-1) and
  formula rules (C-2 Court Street) stay empty, with a note explaining why.
- **Unused space and nonconforming sites.** Unused = allowed − existing, never below 0. If the
  existing building is already over a limit, the site is flagged nonconforming and is not
  treated as an opportunity.
- **Flags.** Each flag comes with a plain-English sentence. The flags cover: historic district,
  flood zone, redevelopment area, redevelopment agreement, zoning in progress, irregular lot,
  lot below the minimum size, tax-exempt, area mismatch, zone split or mismatch, sub-district,
  and nonconforming.
- **Score (0–100).** Weights live in `SCORE_WEIGHTS` in `pipeline/potential.py`:
  - unused units 35, unused stories 20, lot area 10
  - land-driven value 15, old building 5, vacant land 10
  - penalties: historic −10, redevelopment agreement −25, nonconforming −10, irregular lot −5,
    tax-exempt −10

  Each scored site comes with reasons, such as "Zone allows 4 units; currently 2".

Outputs:
- `web/public/data/sites.geojson`: simplified shapes and safe fields only.
- `web/public/data/rules.json`: the approved rules, assumptions and weights.
- `data/processed/potential_report.md`: coverage, flags, and the top 25 sites.

## Phase 4: web app

```bash
cd web && npm install && npm run dev     # http://localhost:3000
```

- **Map (`/`)**:
  - The map colours each property by upside score. Condo buildings and zones without loaded
    rules show in grey and purple.
  - Layers you can toggle: zoning, historic, flood (A/V) and redevelopment areas.
  - Filters: zone, property class, minimum unused units and floors, minimum lot size, maximum
    building ÷ land value, score range, address or block/lot search. You can exclude historic,
    redevelopment and nonconforming sites, and include condo buildings and unscored zones.
  - The site count updates live as you filter. The table sorts by any column, and the filtered
    rows export to CSV with the disclaimer on the first line.
  - Clicking a property, on the map or in the table, opens a detail panel. It shows:
    - existing vs. allowed floors, units and coverage
    - the exact formulas
    - why the property got its score, with points for each part
    - warning flags in plain English
    - every rule used, with its quote and source link
    - tax-record facts
    - the block/lot, with a copy button for Deal Finder
- **Zone rules (`/zones`)**: the approved rules, with each value's quote, source and approval date.
- **About (`/about`)**: method, data sources, privacy, coverage, limitations, roadmap.

All the data is static, in `web/public/data/`, and `python -m pipeline.potential` writes it. The
basemap is OpenFreeMap, which is free and needs no key.
