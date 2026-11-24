"""Allowed stories / units and the upside score, using the approved rule shapes."""
from pipeline.potential import (SCORE_WEIGHTS, allowed_stories, allowed_units, source_conflicts,
                                under_construction, upside_score)


def F(**kw):
    return {k: {"value": v} for k, v in kw.items()}


def test_story_limit_binds_r1():
    r = allowed_stories(F(max_height_ft=40, max_stories=3, min_floor_to_floor_ft=10))
    assert r["value"] == 3 and "story limit binds" in r["formula"]


def test_height_limit_binds_c1():
    # 60 ft ÷ 10 ft = 6, but the stated limit is 5 stories
    assert allowed_stories(F(max_height_ft=60, max_stories=5, min_floor_to_floor_ft=10))["value"] == 5


def test_height_only_uses_realistic_floor_height():
    # R-2 / R-3: 40 ft, no story limit → about 3 realistic floors (11 ft), 4 theoretical (10 ft minimum)
    r = allowed_stories(F(max_height_ft=40, min_floor_to_floor_ft=10))
    assert r["value"] == 3 and r["max_value"] == 4 and "theoretical" in r["formula"].lower()


def test_height_only_without_min_floor_height():
    r = allowed_stories(F(max_height_ft=52))
    assert r["value"] == 4 and r["max_value"] == 5 and "assumed minimum" in r["formula"]


def test_stated_story_limit_is_trusted():
    # C-3: "four residential floors over one commercial floor ... not exceed 52 feet"
    r = allowed_stories(F(max_height_ft=52, max_stories=5, min_floor_to_floor_ft=10))
    assert r["value"] == r["max_value"] == 5


def test_half_story_kept():
    assert allowed_stories(F(max_height_ft=40, max_stories=3.5))["value"] == 3.5


def test_no_limits():
    assert allowed_stories(F())["value"] is None


def test_units_nearest_rounding():
    d = {"type": "site_area_per_unit", "site_area_per_unit_sqft": 660, "rounding": "nearest"}
    assert allowed_units(d, 2500)["value"] == 4     # 3.79 → 4
    assert allowed_units(d, 1875)["value"] == 3     # 2.84 → 3
    assert allowed_units(d, 1980)["value"] == 3     # exactly 3.0


def test_units_rounding_not_stated_rounds_down():
    d = {"type": "site_area_per_unit", "site_area_per_unit_sqft": 330, "rounding": "not_stated"}
    r = allowed_units(d, 2500)                      # 7.58 → 7
    assert r["value"] == 7 and "does not say how to round" in r["formula"]


def test_units_none_density_stays_missing():
    r = allowed_units({"type": "none"}, 5000)
    assert r["value"] is None and r["note"]


def test_units_formula_type_not_guessed():
    assert allowed_units({"type": "formula"}, 5000)["value"] is None


def test_units_unknown_lot_area():
    assert allowed_units({"type": "site_area_per_unit", "site_area_per_unit_sqft": 660}, None)["value"] is None


def test_score_vacant_lot_high_with_reasons():
    score, reasons, parts = upside_score({
        "unused_units": 10, "allowed_units": 10, "existing_units": 0,
        "unused_stories": 4, "allowed_stories": 4, "existing_stories": 0,
        "lot_area": 6000, "building_value_share": 0.0, "vacant": True})
    assert score == 90
    assert "Zone allows 10 units; currently 0" in reasons and "Vacant land" in reasons


def test_score_penalties_and_clip():
    score, reasons, parts = upside_score({"lot_area": 1000, "historic": True, "redev_agreement": True,
                                          "nonconforming": True})
    assert score == 0 and parts["redev_agreement"] == SCORE_WEIGHTS["redev_agreement"]


def test_under_construction_detection():
    for d in ["VACANT LAND WIP", "3B-2U-B (WIP)", "FENCED LOT-WIP", "WIP-VACANT LAND", "GUTTED"]:
        assert under_construction(d), d
    for d in ["3F-2U", "VACANT LAND", None, "WIPER ST"]:
        assert not under_construction(d), d


def test_exempt_and_wip_penalties():
    base = {"unused_units": 10, "allowed_units": 10, "existing_units": 0, "lot_area": 6000,
            "building_value_share": 0.0, "vacant": True}
    s0, _, _ = upside_score(base)
    s1, reasons, _ = upside_score({**base, "under_construction": True, "exempt": True})
    assert s1 == s0 + SCORE_WEIGHTS["under_construction"] + SCORE_WEIGHTS["exempt"]
    assert any("under construction" in r for r in reasons)


def test_source_conflict_c1_height():
    approved = {"C-1": {"districts": [{"name": None, "fields": F(max_height_ft=60, max_stories=5,
                                                              min_floor_to_floor_ft=10)}]}}
    c = source_conflicts(approved)["C-1"]
    assert len(c) == 1 and "60" in c[0] and "52" in c[0] and "5 either way" in c[0]


# ---------------------------------------------------------------- review round 2
import geopandas as gpd
from shapely.geometry import box

from pipeline.overture import footprint_stats
from pipeline.potential import building_detected, effective_limits, floors_disagree


def test_tag_detection_all_patterns():
    for d in ["VACANT LAND WIP", "5B-GUTTED-WIP", "NEW CONST", "NEW CONSTRUCTION", "UNDER CONST", "3B U/C",
              "DEMO", "2B-DEMOLISHED", "COMMERCIAL-WIP"]:
        assert under_construction(d), d
    for d in ["1BR-UNRENOVATED", "PARTIAL OUT", "CONSTANT ST", "VACANT LAND", "3B-2U"]:
        assert not under_construction(d), d


def test_realistic_vs_max_uses_larger_of_typical_and_zone_minimum():
    # zone minimum 12 ft > typical 11 ft → realistic uses 12: floor(52/12)=4, max also 4
    r = allowed_stories(F(max_height_ft=52, min_floor_to_floor_ft=12))
    assert r["value"] == 4 and r["max_value"] == 4 and r["realistic_ftf"] == 12
    # R-2: 40 ft, min 10 → realistic 3 at 11 ft, max 4 at 10 ft
    r = allowed_stories(F(max_height_ft=40, min_floor_to_floor_ft=10))
    assert (r["value"], r["max_value"], r["realistic_ftf"], r["min_ftf"]) == (3, 4, 11, 10)


def test_building_type_limits_residential_first():
    f = F(max_height_ft_commercial=60, max_stories_commercial=5, max_height_ft_residential=52, max_stories_residential=5)
    lim = effective_limits(f)
    assert lim["max_height_ft"] == 52 and lim["height_basis"] == "residential/mixed-use" and not lim["commercial_fallback"]
    lim = effective_limits(F(max_height_ft_commercial=60, max_stories_commercial=5))
    assert lim["max_height_ft"] == 60 and lim["commercial_fallback"]
    assert "commercial limits" in allowed_stories(F(max_height_ft_commercial=60, max_stories_commercial=5))["formula"]


def _feet(geoms, **cols):
    return gpd.GeoDataFrame({**cols, "geometry": geoms}, crs="EPSG:3424")


def test_footprint_coverage_synthetic():
    # Two 100x100 ft lots. Lot A: a 50x100 building (50%) plus an overlapping 20x100 part (union stays 50%).
    # Lot B: a neighbour's building pokes 10 ft in (10%), it lies mostly outside → not dominant.
    sites = _feet([box(0, 0, 100, 100), box(100, 0, 200, 100)], site_id=["A", "B"])
    blds = _feet([box(0, 0, 50, 100), box(30, 0, 50, 100), box(190, 0, 290, 100)],
                 id=["b1", "b2", "b3"], height=[12.0, 15.0, 30.0], num_floors=[None, 4, None])
    out = footprint_stats(sites, blds).set_index("site_id")
    assert out.loc["A", "footprint_coverage_pct"] == 50.0
    assert out.loc["A", "overture_num_floors"] == 4
    assert round(out.loc["A", "overture_max_height_ft"]) == 49  # 15 m
    assert out.loc["B", "footprint_coverage_pct"] == 10.0
    assert out.loc["B", "overture_building_count"] == 0


class _S:  # minimal site row
    def __init__(self, **kw):
        self.__dict__.update({"is_vacant_land": False, "existing_stories": None, "bldg_desc": "", **kw})


def test_building_detected_and_floors_disagree():
    fp = {"footprint_coverage_pct": 80.0, "overture_num_floors": None, "overture_max_height_ft": 44.0}
    assert building_detected(_S(is_vacant_land=True, existing_stories=0, bldg_desc="VACANT LAND"), fp)
    assert building_detected(_S(bldg_desc="PARKING LOT"), fp)
    assert not building_detected(_S(existing_stories=6, bldg_desc="6B-99U-PARKING"), fp)  # garage, not a lot
    assert not building_detected(_S(is_vacant_land=True, existing_stories=0), {**fp, "footprint_coverage_pct": 20})
    assert floors_disagree(_S(existing_stories=2), fp) == (2, 4, "44 ft tall ÷ 11 ft")  # 44/11 = 4
    assert floors_disagree(_S(existing_stories=3), fp) is None
