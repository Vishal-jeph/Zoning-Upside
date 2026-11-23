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
