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
