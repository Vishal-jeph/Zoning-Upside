# Data quality report

Generated 2026-11-24 from `data/raw/2026-11-23`.

## Records → sites
| | count |
|---|---|
| Tax records (incl. condo units) | 19527 |
| Condo-unit records (qualifier C*, bedroom-style or condo-style lot desc, COMMON ELEMENT) | 15929 |
| Sites (block + lead lot) | 4001 |
| Condo buildings (excluded from ranking by default) | 1166 |
| Non-condo sites | 2835 |
| Lots folded into a lead lot via M4_Additional_Lots | 35 |
| Lots folded into a lead lot because their tax record is an identical copy | 517 |
| Additional-lot lists not resolvable (other blocks / free text) | 150 |
| Sites with no zoning polygon | 0 |

## Parse success (non-condo sites)
| Building description | sites | share |
|---|---|---|
| ok | 2296 | 81.0% |
| non_residential | 368 | 13.0% |
| unparsed | 171 | 6.0% |

Sites with both stories and units parsed: **2417** of 2835.

| Lot description | sites | share |
|---|---|---|
| ok | 2798 | 98.7% |
| unparsed | 37 | 1.3% |

Material codes seen (only F = Frame and B = Brick are confirmed; others are kept raw):
`B` 2162, `F` 176, `S` 49, `CB` 35, `B&S` 29, `MIXED` 17, `B&F` 7, `CBL` 4, `SB` 4, `FR` 1, `BF` 1, `ST&CB` 1, `B&C` 1, `CB&B` 1, `CB&S` 1, `CI` 1, `ST` 1, `BLDGS` 1

Building tags seen (only G = Garage, GUTTED, WIP have confirmed meanings):
`H` 1701, `BA` 1471, `X` 415, `G` 221, `B` 88, `LAND` 58, `C` 53, `DECK` 48, `BX` 35, `FX` 27, `DK` 23, `MAIN STEM CL 1` 21, `VACANT LAND` 14, `PARKING LOT` 13, `PAVED LOT` 11, `1FX` 11, `2BX` 11, `COM` 10, `1BX` 10, `(LE)` 10, `WIP` 9, `I` 9, `CHURCH` 9, `2X` 9, `1B` 8

## 30 most common unparsed building descriptions (non-condo records)
| value | records |
|---|---|
| `(blank)` | 246 |
| `3B TEMPLE/CNTR` | 6 |
| `1C B I` | 5 |
| `3,4,&5B-3C-WH B` | 3 |
| `PAVED LOT/1B` | 2 |
| `PATIO-BAR` | 2 |
| `2-10B 208U` | 2 |
| `PARKING LOT 8PS` | 2 |
| `COMMUNITY CENTR` | 2 |
| `WIP 6S-10COM` | 2 |
| `5B&5B 16U&4C-BA` | 2 |
| `21/2STY.BR` | 2 |
| `LAND/RIVER` | 2 |
| `ROAD` | 2 |
| `WALKWAY` | 2 |
| `CLASS RR` | 1 |
| `T-MOBILE ANTENN` | 1 |
| `STRIP-CLASS 3` | 1 |
| `PIER 1-CLASS 3` | 1 |
| `15U-1C` | 1 |
| `4B CITY HALL` | 1 |
| `5B+5B-OFF.BLDGS` | 1 |
| `PARKINGLOT 15PS` | 1 |
| `JACKSON ST PARK` | 1 |
| `MULTI CENTER` | 1 |
| `3B-4U-2C/2C-G` | 1 |
| `REC CENTER` | 1 |
| `PARKING 6PS-DR` | 1 |
| `PARKING 8PS-DR` | 1 |
| `5B-4U-1C/3B1U-G` | 1 |

## Most common unparsed lot descriptions (non-condo records)
| value | records |
|---|---|
| `(blank)` | 240 |
| `88 AVG.X25 COR.` | 1 |
| `55 IRR X33 AVG` | 1 |

## Sites per zone
| zone | sites | non-condo |
|---|---|---|
| C-1 | 57 | 53 |
| C-2 | 185 | 161 |
| C-3 | 276 | 164 |
| C-4 | 1 | 1 |
| I-1 | 27 | 26 |
| I-1 (W) | 35 | 23 |
| I-2 | 61 | 54 |
| R-1 | 1972 | 1577 |
| R-2 | 630 | 347 |
| R-3 | 495 | 193 |
| R-CP | 69 | 64 |
| RPA:DPW | 2 | 2 |
| RPA:Fabian Arts District | 3 | 3 |
| RPA:Garage B | 1 | 1 |
| RPA:HHA | 16 | 16 |
| RPA:Hoboken Yard | 9 | 9 |
| RPA:North End | 74 | 71 |
| RPA:Northwest | 47 | 30 |
| RPA:Observer Highway | 2 | 2 |
| RPA:South Waterfront | 13 | 12 |
| RPA:Western Edge | 10 | 10 |
| UD | 12 | 12 |
| W (N) | 4 | 4 |

## Zone mismatches: tax record M4_Zone vs zoning map polygon (non-condo sites)
17 of 2835 sites (0.6%). The map polygon is used; the tax zone is kept for reference.

| pair | sites |
|---|---|
| `R-1 (tax) vs C-2 (map)` | 4 |
| `R-3 (tax) vs RPA (map)` | 3 |
| `R-1 (tax) vs C-3 (map)` | 2 |
| `R1OH (tax) vs RPA (map)` | 1 |
| `R1C3 (tax) vs R-1 (map)` | 1 |
| `R1C2 (tax) vs C-2 (map)` | 1 |
| `C-3 (tax) vs R-1 (map)` | 1 |
| `C-1 (tax) vs RPA (map)` | 1 |
| `UD (tax) vs R-CP (map)` | 1 |
| `RCPU (tax) vs UD (map)` | 1 |
| `SZP (tax) vs W (N) (map)` | 1 |

## Lot area: tax description vs polygon
Ratio outside 0.67–1.5: **34** of 2798 non-condo sites with a parsed area.
Median ratio: 1.000.

## Flags (non-condo sites)
| flag | sites |
|---|---|
| in_historic_district | 521 |
| in_flood_hazard_area | 1650 |
| in_redev_area | 212 |
| has_redev_agreement | 40 |
| in_zoning_in_progress | 26 |
| is_exempt | 207 |
| is_vacant_land | 166 |
| lot_irregular | 147 |
| area_mismatch | 34 |
| zone_split | 12 |
| zone_mismatch | 17 |
| additional_lots_unresolved | 148 |

Constraint overlap threshold: a layer polygon must cover ≥ 10% of a site.
