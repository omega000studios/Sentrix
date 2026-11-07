import re

import usaddress
from rapidfuzz.fuzz import ratio

from app.schemas import Address


RULE_VERSION = "address-v1"
SUFFIXES = {"street": "st", "avenue": "ave", "road": "rd", "boulevard": "blvd", "drive": "dr", "lane": "ln", "court": "ct", "place": "pl", "highway": "hwy", "parkway": "pkwy", "terrace": "ter", "circle": "cir"}
DIRECTIONS = {"north": "n", "south": "s", "east": "e", "west": "w", "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw"}
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY AS GU MP PR VI".split())


def clean(value):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value.lower()).split())


def normalize(address):
    a = Address.model_validate(address)
    if not all(v.strip() for v in (a.line1, a.city, a.state, a.postal_code)):
        return None
    if a.state.strip().upper() not in US_STATES or not re.fullmatch(r"\d{5}(-\d{4})?", a.postal_code.strip()):
        return None
    try:
        parts, kind = usaddress.tag(f"{a.line1}, {a.line2}".strip(", "))
    except usaddress.RepeatedLabelError:
        return None
    allowed = {"AddressNumber", "StreetName", "StreetNamePreDirectional", "StreetNamePostDirectional", "StreetNamePreType", "StreetNamePostType", "OccupancyType", "OccupancyIdentifier"}
    if kind != "Street Address" or not parts.get("AddressNumber") or not parts.get("StreetName") or set(parts) - allowed:
        return None
    if parts.get("OccupancyType") and not parts.get("OccupancyIdentifier"):
        return None
    street = []
    for key in ("StreetNamePreDirectional", "StreetNamePreType", "StreetName", "StreetNamePostType", "StreetNamePostDirectional"):
        words = clean(parts.get(key, "")).split()
        street.extend(SUFFIXES.get(w, DIRECTIONS.get(w, w)) for w in words)
    return {"number": clean(parts["AddressNumber"]), "street": " ".join(street), "unit": clean(parts.get("OccupancyIdentifier", "")), "city": clean(a.city), "state": clean(a.state), "postal_code": a.postal_code.strip()}


def evaluate(inputs):
    label = inputs["label"]
    analysis = inputs.get("ai_analysis")
    left, right = normalize(inputs["paypal_address"]), normalize(label["address"])
    reasons = []
    match = None
    uncertain = False
    if left is None or right is None:
        reasons.append("Address is incomplete or could not be parsed unambiguously")
        uncertain = True
    else:
        differences = [key for key in left if left[key] != right[key]]
        if not differences:
            match = "MATCH" if inputs["paypal_address"] == label["address"] else "NEAR_MATCH"
        else:
            match = "MISMATCH"
            reasons.extend(f"Different {key}" for key in differences)
            # shortcut: similar street/city spelling needs a human, add curated aliases only after evaluated fixtures justify them.
            uncertain = any(key in {"street", "city"} and ratio(left[key], right[key]) >= 85 for key in differences)
            if uncertain:
                reasons.append("Similar address text requires human review")
    if label.get("confidence") is None or label["confidence"] < 0.90:
        uncertain = True
        reasons.append("Label confidence is missing or below 0.90")
    if analysis and (analysis["confidence"] < 0.90 or analysis["intent"] == "AMBIGUOUS"):
        uncertain = True
        reasons.append("Message intent is uncertain")
    if inputs["seller_protection"] != "ELIGIBLE":
        uncertain = True
        reasons.append("Seller protection is not confirmed eligible")
    verdict = "REVIEW" if uncertain else "BLOCKED" if match == "MISMATCH" else "PROTECTED"
    if not reasons:
        reasons.append("Label address agrees with the captured PayPal address")
    return {"comparison": {"match": match, "reasons": reasons}, "verdict": verdict, "recommended_action": {"REVIEW": "HUMAN_REVIEW", "BLOCKED": "HOLD_REFUND_REORDER", "PROTECTED": "PRINT_AND_TRACK"}[verdict]}
