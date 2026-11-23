"""The evidence checks that stop invented rules from passing silently."""
from pipeline.rules_extract import number_in_quote, quote_found, verify

SRC = ("The R-1 District permits a maximum residential building height of 40 feet above Design "
       "Flood Elevation (DFE), or 3 stories. T he building must have a 30-foot rear setback. "
       "Lot coverage (max.): 60% Density (max.): Site area divided by 660")


def test_quote_found_tolerates_spacing_and_punctuation():
    assert quote_found("40 feet above Design Flood Elevation (DFE)", SRC)
    assert quote_found("The building must have a 30 foot rear setback", SRC)  # source has "T he", "30-foot"


def test_quote_with_ellipsis_needs_every_piece_in_order():
    assert quote_found("maximum residential building height ... or 3 stories", SRC)
    assert not quote_found("or 3 stories ... maximum residential building height", SRC)


def test_invented_quote_fails():
    assert not quote_found("40 feet or three stories, whichever is less", SRC)
    assert not quote_found(None, SRC)


def test_number_must_appear_in_quote():
    assert number_in_quote(40, "height of 40 feet")
    assert number_in_quote(3, "or three stories")
    assert number_in_quote(60, "Lot coverage (max.): 60%")
    assert number_in_quote(0.6, "Lot coverage (max.): 60%")
    assert not number_in_quote(52, "height of 40 feet")


def test_verify_flags_and_downgrades():
    ok = verify({"value": 40, "quote": "height of 40 feet", "source_id": "S1", "confidence": "high"},
                "max_height_ft", {"S1": SRC})
    assert ok["verified"] and ok["confidence"] == "high"
    bad = verify({"value": 52, "quote": "height of 40 feet", "source_id": "S1", "confidence": "high"},
                 "max_height_ft", {"S1": SRC})
    assert not bad["verified"] and bad["confidence"] == "low" and "number not in quote" in bad["issues"]
    moved = verify({"value": 60, "quote": "Lot coverage (max.): 60%", "source_id": "S2", "confidence": "high"},
                   "max_lot_coverage_pct", {"S1": SRC, "S2": "other text"})
    assert moved["verified"] and moved["source_id"] == "S1"  # wrong source id corrected, not trusted blindly
