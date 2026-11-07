from copy import deepcopy

import pytest

from app.rules import evaluate
from fixtures.scenarios import scenario


def inputs():
    capture, message, label = scenario()
    return {**capture, "ai_analysis": message["ai_analysis"], "label": {k: v for k, v in label.items() if k != "order_id"}}


@pytest.mark.parametrize("field,value,expected,match", [
    (None, None, "PROTECTED", "MATCH"),
    ("line1", "123 Main St", "PROTECTED", "NEAR_MATCH"),
    ("line2", "#4", "PROTECTED", "NEAR_MATCH"),
    ("line1", "987 Main Street", "BLOCKED", "MISMATCH"),
    ("line2", "Apt 9", "BLOCKED", "MISMATCH"),
    ("postal_code", "90210", "BLOCKED", "MISMATCH"),
    ("city", "Houston", "BLOCKED", "MISMATCH"),
    ("state", "CA", "BLOCKED", "MISMATCH"),
    ("line1", "123 Mane Street", "REVIEW", "MISMATCH"),
    ("line1", "", "REVIEW", None),
    ("line1", "PO Box 123", "REVIEW", None),
])
def test_addresses(field, value, expected, match):
    data = inputs()
    if field:
        data["label"]["address"][field] = value
    result = evaluate(data)
    assert result["verdict"] == expected
    assert result["comparison"]["match"] == match
    assert result["comparison"]["reasons"]


@pytest.mark.parametrize("change", ["low_label", "missing_confidence", "low_intent", "ambiguous", "ineligible", "unknown"])
def test_uncertainty_takes_precedence(change):
    data = inputs()
    data["label"]["address"]["postal_code"] = "90210"
    if change == "low_label":
        data["label"]["confidence"] = 0.89
    elif change == "missing_confidence":
        data["label"]["confidence"] = None
    elif change == "low_intent":
        data["ai_analysis"]["confidence"] = 0.89
    elif change == "ambiguous":
        data["ai_analysis"]["intent"] = "AMBIGUOUS"
    else:
        data["seller_protection"] = "UNKNOWN" if change == "unknown" else "NOT_ELIGIBLE"
    result = evaluate(data)
    assert result["verdict"] == "REVIEW"
    assert result["comparison"]["match"] == "MISMATCH"


def test_label_only_and_threshold():
    data = inputs()
    data["ai_analysis"] = None
    data["label"]["confidence"] = 0.90
    original = deepcopy(data)
    assert evaluate(data)["verdict"] == "PROTECTED"
    assert original == data
