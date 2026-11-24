# Potential report — 2026-11-24

Estimate based on public zoning text; verify with the Hoboken Zoning Office.

## Coverage

| status           |   sites |
|:-----------------|--------:|
| scored           |    2559 |
| condo_building   |    1166 |
| rules_not_loaded |     276 |

## Scored sites

- allowed stories known: 2559
- allowed units known: 2506 (C-1 has no numeric density rule)
- unused stories > 0: 673
- unused units > 0: 1095
- nonconforming (already over a limit): 907

## Flags on scored sites

|                       |   sites |
|:----------------------|--------:|
| flood                 |    1388 |
| below_min_lot         |    1270 |
| nonconforming         |     907 |
| historic              |     509 |
| subdistrict           |     161 |
| floors_disagree       |     153 |
| irregular_lot         |     138 |
| exempt                |     114 |
| large_site            |      56 |
| rule_pending          |      53 |
| rule_conflict         |      53 |
| building_detected     |      25 |
| under_construction    |      24 |
| area_mismatch         |      12 |
| zoning_in_progress    |      11 |
| zone_split            |      10 |
| zone_mismatch         |      10 |
| redev_area            |       4 |
| possible_condo_master |       3 |
| redev_agreement       |       1 |

- condo buildings with a land-only master record (excluded): 72
- hidden by default (exempt / possibly under construction / possible condo master): 140 scored sites

## Score distribution

|       |   score |
|:------|--------:|
| count |  2559   |
| mean  |     9.2 |
| std   |    10.7 |
| min   |     0   |
| 25%   |     0   |
| 50%   |     8   |
| 75%   |    13   |
| max   |    90   |

## Top 25
## Top 25 (as shown by default: exempt, under-construction and condo-master sites hidden)
|   score |   block |   lot | location                  | zone_key   | bldg_desc       |   existing_units |   allowed_units |   existing_stories |   allowed_stories |
|--------:|--------:|------:|:--------------------------|:-----------|:----------------|-----------------:|----------------:|-------------------:|------------------:|
|      90 |      82 | 27.01 | 706-14 MADISON ST         | R-3        | PARKING LOT     |                0 |              19 |                  0 |                 3 |
|      82 |      78 | 23    | 620-622 GRAND ST          | R-2        | PAVED LOT       |                0 |               8 |                  0 |                 3 |
|      73 |      41 |  9    | 217 ADAMS ST              | R-2        | 1B              |                0 |              19 |                  1 |                 3 |
|      69 |      79 |  9    | 614-632 CLINTON ST        | R-2        | 1B-ACME-PKG     |                0 |              75 |                  1 |                 3 |
|      68 |      13 | 15    | 651 FIRST ST              | C-3        | LAND            |                0 |               5 |                  0 |                 5 |
|      68 |      47 |  9    | 317 JACKSON ST            | C-3        | LAND            |                0 |               5 |                  0 |                 5 |
|      68 |      66 |  7    | 513 JACKSON ST            | C-3        | LAND            |                0 |               5 |                  0 |                 5 |
|      66 |     201 | 25    | 208-212 WASHINGTON ST     | C-2        | 1B-3C-BA-H      |                0 |              11 |                  1 |                 4 |
|      65 |     214 |  1.01 | 301 WASHINGTON ST         | C-2        | 1ST&CB-BANK     |                0 |              44 |                  1 |                 4 |
|      65 |     152 |  4    | 710 CLINTON ST            | R-2        | 1B-C-G          |                0 |              15 |                  1 |                 3 |
|      64 |      13 | 16    | 90 JACKSON ST             | R-3        | LAND            |                0 |               4 |                  0 |                 3 |
|      64 |      85 | 24    | 702 GRAND ST              | R-2        | LAND            |                0 |               4 |                  0 |                 3 |
|      64 |     117 |  1    | 1301 WILLOW AVE           | R-2        | 1B-1CB GAS STAT |                0 |               8 |                  1 |                 3 |
|      63 |     201 | 26    | 204 WASHINGTON ST         | C-2        | 1B-COM-H        |                0 |              13 |                  1 |                 4 |
|      63 |      60 |  9    | 417 JEFFERSON ST          | R-2        | PARKING LOT     |                0 |               4 |                  0 |                 3 |
|      61 |      19 |  1    | 400 NEWARK ST/73 ADAMS ST | R-3        | 2B-8C/2B-4U     |                4 |              48 |                  2 |                 3 |
|      59 |     212 |  1    | 101-105 WASHINGTON ST     | C-2        | 2B-RETAIL       |                0 |              18 |                  2 |                 4 |
|      59 |      68 |  1.01 | 501 MADISON ST            | R-2        | LAND            |                0 |               3 |                  0 |                 3 |
|      59 |      60 | 17    | 416 ADAMS ST              | R-2        | PARKING LOT     |                0 |               4 |                  0 |                 3 |
|      58 |     166 |  7    | 313 WILLOW AVE            | R-1        | PAVED LOT       |                0 |               4 |                  0 |                 3 |
|      58 |     116 |  1.01 | 1300-14 WILLOW AVE        | R-2        | 1B-RETAIL       |                0 |              61 |                  1 |                 3 |
|      58 |     269 | 10    | 1401 WASHINGTON/60 14TH   | C-3        | 3B-C-BANK       |                0 |              17 |                  3 |                 5 |
|      57 |     202 |  6    | 308 WASHINGTON ST         | C-2        | 1B-2C           |                0 |              22 |                  1 |                 4 |
|      55 |     217 |  5    | 621 WASHINGTON ST         | C-2        | 2B-1C-2BEXT-G   |                0 |              28 |                  2 |                 4 |
|      54 |      46 | 19    | 328 JACKSON ST            | R-3        | LAND            |                0 |               3 |                  0 |                 3 |

### Reasons for the top 5

- **706-14 MADISON ST** (block 82 lot 27.01, score 90.0): Zone allows 19 units; currently 0; Zone allows about 3 floors (up to 4 at the minimum floor height); currently 0; Large lot: 12,500 sq ft; Building value is 1% of total — land-driven value; Vacant land
- **620-622 GRAND ST** (block 78 lot 23, score 82.0): Zone allows 8 units; currently 0; Zone allows about 3 floors (up to 4 at the minimum floor height); currently 0; Large lot: 5,000 sq ft; Building value is 4% of total — land-driven value; Vacant land
- **217 ADAMS ST** (block 41 lot 9, score 73.0): Zone allows 19 units; currently 0; Zone allows about 3 floors (up to 4 at the minimum floor height); currently 1; Large lot: 12,453 sq ft; Building value is 1% of total — land-driven value
- **614-632 CLINTON ST** (block 79 lot 9, score 69.0): Zone allows 75 units; currently 0; Zone allows about 3 floors (up to 4 at the minimum floor height); currently 1; Large lot: 49,792 sq ft; Building value is 13% of total — land-driven value
- **651 FIRST ST** (block 13 lot 15, score 68.0): Zone allows 5 units; currently 0; Zone allows 5 floors; currently 0; Building value is 0% of total — land-driven value; Vacant land
