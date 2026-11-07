"""Synthetic US fixtures. Never represent these as PayPal API responses."""
from copy import deepcopy


ADDRESS = {"line1": "123 Main Street", "line2": "Apt 4", "city": "Austin", "state": "TX", "postal_code": "78701", "country": "US"}


def scenario(name="clean"):
    capture = {"order_id": f"DEMO-{name.upper()}", "paypal_order_id": f"FIXTURE-ORDER-{name}", "capture_id": f"FIXTURE-CAPTURE-{name}", "amount": {"value": "149.99", "currency": "USD"}, "paypal_address": deepcopy(ADDRESS), "seller_protection": "ELIGIBLE", "source": "fixture"}
    message = {"order_id": capture["order_id"], "id": f"MSG-{name}", "text": "Please ship to my office instead", "ai_analysis": {"intent": "ADDRESS_CHANGE_REQUEST", "confidence": 0.98, "quote": "ship to my office instead", "proposed_address": None}}
    label = {"order_id": capture["order_id"], "address": deepcopy(ADDRESS), "tracking_number": "SIMULATED-TRACKING", "carrier": "SIMULATED", "confidence": 0.98}
    if name == "mismatch":
        label["address"]["line1"] = "987 Main Street"
    elif name == "uncertain":
        label["confidence"] = 0.65
    elif name != "clean":
        raise ValueError("Unknown scenario")
    return capture, message, label
