# Rule sources

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
| ⬜ | C-1, C-2, C-3, C-4 | ordinance | https://ecode360.com/15237855 | `data/sources/ordinance/ecode_15237855.html` |
| ⬜ | I-1, I-1 (W) | ordinance | https://ecode360.com/15237722 | `data/sources/ordinance/ecode_15237722.html` |
| ⬜ | I-2 | ordinance | https://ecode360.com/15237818 | `data/sources/ordinance/ecode_15237818.html` |
| ⬜ | R-1, R-CP | ordinance | https://ecode360.com/15237440 | `data/sources/ordinance/ecode_15237440.html` |
| ⬜ | R-2 | ordinance | https://ecode360.com/15237601 | `data/sources/ordinance/ecode_15237601.html` |
| ⬜ | R-3 | ordinance | https://ecode360.com/15237682 | `data/sources/ordinance/ecode_15237682.html` |
| ⬜ | UD | ordinance | https://ecode360.com/33634066 | `data/sources/ordinance/ecode_33634066.html` |
| ⬜ | W (N) | ordinance | https://ecode360.com/15237942 | `data/sources/ordinance/ecode_15237942.html` |
| ⬜ | PLAN:Neumann Leathers | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Neumann_Leathers_Redevelopment_Plan_Amended_4.19.2023.pdf | `data/sources/plans/Neumann_Leathers_Redevelopment_Plan_Amended_4.19.2023.pdf` |
| ⬜ | PLAN:Post Office | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Post_Office_Redev_Plan_Amended_6.19.19.pdf | `data/sources/plans/Post_Office_Redev_Plan_Amended_6.19.19.pdf` |
| ⬜ | PLAN:Southwest | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Southwest_Hoboken_RDP_Amend_20260708.pdf | `data/sources/plans/Southwest_Hoboken_RDP_Amend_20260708.pdf` |
| ⬜ | RPA:DPW | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Public_Works_Garage_Redev_Plan_Amended_20210519_CLEAN.pdf | `data/sources/plans/Public_Works_Garage_Redev_Plan_Amended_20210519_CLEAN.pdf` |
| ⬜ | RPA:Fabian Arts District | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Fabian_Arts_District_Redev_Plan_20231220.pdf | `data/sources/plans/Fabian_Arts_District_Redev_Plan_20231220.pdf` |
| ⬜ | RPA:Garage B | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/GarageBRedevPlan_20250319_ADOPTEDwExhibits.pdf | `data/sources/plans/GarageBRedevPlan_20250319_ADOPTEDwExhibits.pdf` |
| ⬜ | RPA:HHA | plan | https://hostedfiles.civilsolutions.biz/hudsonco/towns/0905/redevelopment_plans/HHARP_First_Amendment_5-12-25.pdf | `data/sources/plans/HHARP_First_Amendment_5-12-25.pdf` |
| ⬜ | RPA:Hoboken Yard | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Hoboken_Yard_Redev_Plan_Amended_20220504.pdf | `data/sources/plans/Hoboken_Yard_Redev_Plan_Amended_20220504.pdf` |
| ⬜ | RPA:North End | plan | https://hostedfiles.civilsolutions.biz/hudsonco/towns/0905/redevelopment_plans/North_End_Redev_Plan_Incorp_Amendments_to_20251117.pdf | `data/sources/plans/North_End_Redev_Plan_Incorp_Amendments_to_20251117.pdf` |
| ⬜ | RPA:North End | plan | https://hostedfiles.civilsolutions.biz/hudsonco/towns/0905/redevelopment_plans/North_End_Redev_Plan_Incorp_Amendments_to_20260304.pdf | `data/sources/plans/North_End_Redev_Plan_Incorp_Amendments_to_20260304.pdf` |
| ⬜ | RPA:Northwest | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/NWRedevPlan_Amendments_as_of_03-06-2024.pdf | `data/sources/plans/NWRedevPlan_Amendments_as_of_03-06-2024.pdf` |
| ⬜ | RPA:Northwest | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/NW_Redev_Plan_Amendments_as_of_10-07-2026.pdf | `data/sources/plans/NW_Redev_Plan_Amendments_as_of_10-07-2026.pdf` |
| ⬜ | RPA:Observer Highway | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Observer_Highway_Redev_Plan_Adopted_04-06-1988_w_Amendments.pdf | `data/sources/plans/Observer_Highway_Redev_Plan_Adopted_04-06-1988_w_Amendments.pdf` |
| ⬜ | RPA:South Waterfront | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/South_Waterfront_Redevelopment_Plan_Revised_04-21-04.pdf | `data/sources/plans/South_Waterfront_Redevelopment_Plan_Revised_04-21-04.pdf` |
| ⬜ | RPA:Western Edge | plan | https://hostedfiles.civilsolutions.biz/HudsonCo/Towns/0905/Redevelopment_Plans/Western_Edge_Redev_Plan_incorp_Amendments_to_2025-09-03.pdf | `data/sources/plans/Western_Edge_Redev_Plan_incorp_Amendments_to_2025-09-03.pdf` |

## Fetched automatically: City Zoning Guide
| | zone | page |
|---|---|---|
| ✅ | C-1 | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/c-1-district |
| ✅ | C-2 | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/c-2-district |
| ✅ | C-3 | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/c-3-district |
| ✅ | R-1 | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/r-1-district |
| ✅ | R-2 | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/r-2-district |
| ✅ | R-3 | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/r-3-district |
| ✅ | R-CP | https://city-of-hoboken-zoning-guide-cityofhoboken.hub.arcgis.com/pages/r-cp-district |
