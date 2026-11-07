from decimal import Decimal
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import Label, Message, Order, Verdict, utcnow
from app.rules import RULE_VERSION, evaluate
from app.schemas import Capture


class Conflict(Exception):
    pass


def capture_data(order):
    return {"order_id": order.id, "paypal_order_id": order.paypal_order_id, "capture_id": order.capture_id, "amount": {"value": f"{order.amount:.2f}", "currency": order.currency}, "paypal_address": order.paypal_address, "seller_protection": order.seller_protection, "source": order.source}


def ingest_capture(session, capture: Capture):
    """Call only after Member 1 verifies a sandbox webhook. Caller commits the transaction."""
    existing = session.scalar(select(Order).where(Order.capture_id == capture.capture_id))
    if existing:
        if capture_data(existing) != capture.model_dump():
            raise Conflict("Capture already exists with different data")
        return existing
    order = Order(id=capture.order_id, paypal_order_id=capture.paypal_order_id, capture_id=capture.capture_id, amount=Decimal(capture.amount.value), currency=capture.amount.currency, paypal_address=capture.paypal_address.model_dump(), seller_protection=capture.seller_protection, source=capture.source)
    try:
        with session.begin_nested():
            session.add(order)
            session.flush()
    except IntegrityError:
        existing = session.scalar(select(Order).where(Order.capture_id == capture.capture_id))
        if existing and capture_data(existing) == capture.model_dump():
            return existing
        raise Conflict("Order or capture identifier already exists") from None
    return order


def latest(session, model, order_id):
    return session.scalar(select(model).where(model.order_id == order_id).order_by(model.id.desc()).limit(1))


def iso_utc(value):
    # SQLite drops timezone information; our naive timestamps were written in UTC.
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()


def view(session, order):
    message = latest(session, Message, order.id)
    label = latest(session, Label, order.id)
    verdict = latest(session, Verdict, order.id)
    return {**capture_data(order), "state": order.state, "created_at": iso_utc(order.created_at), "updated_at": iso_utc(order.updated_at), "message": {"id": message.external_id, "text": message.text} if message else None, "ai_analysis": message.analysis if message else None, "label": label.data if label else None, **(verdict.result if verdict else {"comparison": {"match": None, "reasons": []}, "verdict": None, "recommended_action": None})}


def recompute(session, order):
    order.updated_at = utcnow()
    data = view(session, order)
    if data["label"] is None:
        order.state = "MESSAGE_FLAGGED" if data["ai_analysis"] and data["ai_analysis"]["intent"] == "ADDRESS_CHANGE_REQUEST" else "CAPTURED"
        return
    result = evaluate(data)
    session.add(Verdict(order_id=order.id, rule_version=RULE_VERSION, inputs=data, result=result))
    order.state = result["verdict"]
    session.flush()
