"""Allowed stories / units and the upside score, using the approved rule shapes."""
from pipeline.potential import SCORE_WEIGHTS, allowed_stories, allowed_units, upside_score


def F(**kw):
    return {k: {"value": v} for k, v in kw.items()}


def test_story_limit_binds_r1():
    r = allowed_stories(F(max_height_ft=40, max_stories=3, min_floor_to_floor_ft=10))
    assert r["value"] == 3 and "story limit binds" in r["formula"]


def test_height_limit_binds_c1():
    # 60 ft ÷ 10 ft = 6, but the stated limit is 5 stories
    assert allowed_stories(F(max_height_ft=60, max_stories=5, min_floor_to_floor_ft=10))["value"] == 5


def test_height_only_uses_default_floor_to_floor():
    r = allowed_stories(F(max_height_ft=52))
    assert r["value"] == 5 and "assumed typical" in r["formula"]


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
    assert r["value"] == 7 and "rounding not stated" in r["formula"]


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
