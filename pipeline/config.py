"""Central configuration: service URLs, allowed fields, paths, CRS."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
SOURCES = DATA / "sources"
RULES = DATA / "rules"

# NJ State Plane, US survey feet — used for every area/length calculation.
CRS_FEET = "EPSG:3424"
CRS_WGS84 = "EPSG:4326"

# Politeness: these services power the City's public map.
MIN_SECONDS_BETWEEN_REQUESTS = 1.05
USER_AGENT = "ZoningUpside-research/0.1 (proof of concept; low-rate cached requests)"

ARCGIS = "https://services8.arcgis.com/LDmC4ZVHdfKcEzxl/arcgis/rest/services"

ZONING_LAYER = {"key": "zoning", "url": f"{ARCGIS}/20200817_Hoboken_Zoning_Project/FeatureServer/6"}

# Constraint layers become boolean flags (plus a few attribute columns) on each site.
CONSTRAINT_LAYERS = [
    {"key": "rehab_redev", "url": f"{ARCGIS}/20200824_Hoboken_Zoning_RehabRedev_Project/FeatureServer/10"},
    {"key": "zoning_in_progress", "url": f"{ARCGIS}/20200824_Hoboken_Zoning_InProgress/FeatureServer/3"},
    {"key": "redev_agreement", "url": f"{ARCGIS}/20260130_RedevAgreements/FeatureServer/2"},
    {"key": "historic", "url": f"{ARCGIS}/20200817_HD_Merge_Project/FeatureServer/0"},
    {"key": "flood", "url": f"{ARCGIS}/20200904_Adv_Hu_FloodZones_Boundary_Intersect/FeatureServer/0"},
]

PARCELS_URL = "https://ags.civilsolutions.biz/server/rest/services/myiDV/Hoboken_Parcels/FeatureServer/0"
PARCEL_PAGE_SIZE = 1000  # service maxRecordCount

# PRIVACY: the only parcel fields we ever request. Owner name/street/city-state-zip
# and Parcel_OTHER1 are deliberately absent and must never be added.
PARCEL_FIELDS = [
    "OBJECTID", "Parcel_BLOCK", "Parcel_LOT", "Parcel_QUAL", "M4_PAMSPIN",
    "M4_Location", "M4_Class", "M4_Bldg_Desc", "M4_Lot_Desc", "M4_Additional_Lots",
    "M4_Zone", "M4_Year_Built", "M4_Sf_Area", "M4_Land_Value", "M4_Impr_Value",
    "M4_Net_Value", "M4_Sale_Date", "M4_Sale_Price",
]
FORBIDDEN_FIELDS = {"M4_Owner_Name", "M4_Owner_Street", "M4_Owner_Csz", "Parcel_OTHER1"}
assert not FORBIDDEN_FIELDS & set(PARCEL_FIELDS)
