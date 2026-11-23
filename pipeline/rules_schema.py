"""Rule fields, the JSON schema the LLM must follow, and seed values for testing extraction."""
from __future__ import annotations

NUMERIC_FIELDS = [
    "max_height_ft", "max_stories", "min_lot_area_sqft", "min_lot_width_ft", "min_lot_depth_ft",
    "max_lot_coverage_pct", "max_far", "min_floor_to_floor_ft",
]
TEXT_FIELDS = ["height_rule_text", "density_rule_text"]
ENUM_FIELDS = {
    "residential_permitted": ["yes", "no", "conditional"],
    "height_measured_from": ["grade", "design_flood_elevation", "other"],
    # How a story limit and a feet limit combine ("40 feet or three stories, whichever is less").
    "height_limits_combine": ["whichever_is_less", "both_apply", "not_stated"],
}
ALL_FIELDS = ["residential_permitted", *NUMERIC_FIELDS[:2], "height_measured_from", "height_limits_combine",
              "height_rule_text", *NUMERIC_FIELDS[2:], "density_rule_text"]
DENSITY_TYPES = ["site_area_per_unit", "units_per_acre", "max_units", "formula", "none"]
CONDITION_CATEGORIES = ["neighbor_height", "step_back", "flood", "historic", "use", "bonus", "other"]


def _field(value_schema: dict) -> dict:
    """A value with its evidence. Everything nullable: null means 'not stated in this text'."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["value", "quote", "source_id", "confidence"],
        "properties": {
            "value": value_schema,
            "quote": {"type": ["string", "null"], "description": "verbatim, at most 40 words"},
            "source_id": {"type": ["string", "null"], "description": "e.g. S1"},
            "confidence": {"type": ["string", "null"], "enum": ["high", "medium", "low", None]},
        },
    }


def llm_json_schema() -> dict:
    props: dict = {"name": {"type": ["string", "null"],
                            "description": "sub-district name as written in a redevelopment plan; null for a base zone"}}
    for f in NUMERIC_FIELDS:
        props[f] = _field({"type": ["number", "null"]})
    for f in TEXT_FIELDS:
        props[f] = _field({"type": ["string", "null"]})
    for f, opts in ENUM_FIELDS.items():
        props[f] = _field({"type": ["string", "null"], "enum": [*opts, None]})
    props["density_structured"] = {
        "type": "object", "additionalProperties": False,
        "required": ["type", "site_area_per_unit_sqft", "units_per_acre", "max_units", "rounding",
                     "quote", "source_id", "confidence"],
        "properties": {
            "type": {"type": ["string", "null"], "enum": [*DENSITY_TYPES, None]},
            "site_area_per_unit_sqft": {"type": ["number", "null"]},
            "units_per_acre": {"type": ["number", "null"]},
            "max_units": {"type": ["number", "null"]},
            "rounding": {"type": ["string", "null"], "enum": ["nearest", "down", "up", "not_stated", None]},
            "quote": {"type": ["string", "null"]},
            "source_id": {"type": ["string", "null"]},
            "confidence": {"type": ["string", "null"], "enum": ["high", "medium", "low", None]},
        },
    }
    props["special_conditions"] = {
        "type": "array",
        "items": {
            "type": "object", "additionalProperties": False,
            "required": ["category", "text", "quote", "source_id"],
            "properties": {
                "category": {"type": "string", "enum": CONDITION_CATEGORIES},
                "text": {"type": "string", "description": "one-sentence plain-English summary"},
                "quote": {"type": ["string", "null"]},
                "source_id": {"type": ["string", "null"]},
            },
        },
    }
    district = {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
    return {
        "type": "object", "additionalProperties": False, "required": ["districts"],
        "properties": {"districts": {"type": "array", "items": district}},
    }


# Known values from the project brief, used to test extraction. They are NOT used in
# calculations; the review page shows them next to the extracted values.
SEEDS = {
    "R-1": {
        "source": "project brief (principal structures)",
        "text": "40 feet or three stories, whichever is less, above design flood elevation",
        "values": {"max_height_ft": 40, "max_stories": 3, "height_measured_from": "design_flood_elevation",
                   "height_limits_combine": "whichever_is_less"},
    },
    "C-1": {
        "source": "project brief",
        "text": "five stories, not to exceed 52 feet above average grade",
        "values": {"max_height_ft": 52, "max_stories": 5, "height_measured_from": "grade"},
    },
}
