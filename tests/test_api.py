import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Label, Order, Verdict
from app.main import create_app
from app.schemas import Capture
from app.seed import seed
from app.service import Conflict, ingest_capture
from fixtures.scenarios import scenario


def client(factory):
    api = TestClient(create_app(factory, "merchant", "test-password"))
    api.auth = ("merchant", "test-password")
    return api


def load(factory, name="mismatch"):
    capture, message, label = scenario(name)
    with factory.begin() as db:
        ingest_capture(db, Capture.model_validate(capture))
    return capture, message, label


def test_dashboard_serves_without_exposing_order_data(factory):
    load(factory)
    with TestClient(create_app(factory, "merchant", "test-password")) as api:
        response = api.get('/')
        assert response.status_code == 200
        assert 'Check before you ship.' in response.text
        assert 'FIXTURE-CAPTURE' not in response.text
        assert api.get('/static/dashboard.js').status_code == 200
        assert api.get('/static/dashboard.css').status_code == 200
        assert api.get('/orders').status_code == 401


def test_vertical_slice_and_restart(factory):
    capture, message, label = load(factory)
    with client(factory) as api:
        assert api.get("/health/ready").status_code == 200
        queue = api.get("/orders").json()
        assert queue[0]["verdict"] is None
        assert queue[0]["source"] == "fixture"
        assert api.post("/messages", json=message).json()["state"] == "MESSAGE_FLAGGED"
        response = api.post("/labels", json=label)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["verdict"] == "BLOCKED"
        assert result["comparison"]["match"] == "MISMATCH"
        assert result["amount"]["value"] == "149.99"
    with client(factory) as restarted:
        assert restarted.get(f"/orders/{capture['order_id']}").json() == result
    with factory() as db:
        audit = db.scalar(select(Verdict))
        assert audit.inputs["message"]["text"] == message["text"]
        assert audit.inputs["label"]["address"] == label["address"]
        assert audit.rule_version == "address-v1"


def test_retry_and_conflicting_captures(factory):
    capture, _, _ = load(factory)
    with factory.begin() as db:
        assert ingest_capture(db, Capture(**capture)).id == capture["order_id"]
    capture["amount"]["value"] = "150.00"
    with pytest.raises(Conflict), factory.begin() as db:
        ingest_capture(db, Capture(**capture))
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1


def test_errors_and_auth(factory):
    _, message, label = load(factory)
    with client(factory) as api:
        assert api.get("/orders", auth=("merchant", "wrong")).status_code == 401
        assert api.get("/orders/unknown").status_code == 404
        label["order_id"] = "unknown"
        assert api.post("/labels", json=label).status_code == 404
        label["confidence"] = 9
        assert api.post("/labels", json=label).status_code == 422
        message["ai_analysis"]["quote"] = "invented quote"
        assert api.post("/messages", json=message).status_code == 422


def test_new_analysis_recomputes_without_changing_history(factory):
    _, message, label = load(factory)
    with client(factory) as api:
        assert api.post("/labels", json=label).json()["verdict"] == "BLOCKED"
        message["ai_analysis"]["confidence"] = 0.5
        assert api.post("/messages", json=message).json()["verdict"] == "REVIEW"
        assert api.post("/messages", json=message).status_code == 200
        message["text"] = "different original message"
        assert api.post("/messages", json=message).status_code == 422
    with factory() as db:
        results = db.scalars(select(Verdict).order_by(Verdict.id)).all()
        assert [v.result["verdict"] for v in results] == ["BLOCKED", "REVIEW"]
        assert results[0].inputs["ai_analysis"] is None


def test_transaction_rolls_back(factory, monkeypatch):
    _, _, label = load(factory)
    def fail(*args):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr("app.main.recompute", fail)
    with client(factory) as api:
        assert api.post("/labels", json=label).status_code == 500
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Label)) == 0
        assert db.scalar(select(Order)).state == "CAPTURED"


def test_seed_is_repeatable(factory):
    seed(factory)
    seed(factory)
    with client(factory) as api:
        queue = api.get("/orders").json()
        assert len(queue) == 3
        assert {o["verdict"] for o in queue} == {"PROTECTED", "BLOCKED", "REVIEW"}


def test_delayed_analysis_and_message_conflict(factory):
    _, message, _ = load(factory)
    analysis = message.pop("ai_analysis")
    with client(factory) as api:
        assert api.post("/messages", json=message).json()["ai_analysis"] is None
        message["ai_analysis"] = analysis
        assert api.post("/messages", json=message).json()["ai_analysis"] == analysis
        message["text"] += "!"
        assert api.post("/messages", json=message).status_code == 409


def test_concurrent_evaluation_serializes_on_postgres(factory):
    from concurrent.futures import ThreadPoolExecutor
    from app.db import Message
    from app.service import recompute
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Row locking requires Postgres")
    capture, message, label = load(factory)

    def write_label():
        with factory.begin() as db:
            order = db.scalar(select(Order).where(Order.id == capture["order_id"]).with_for_update())
            db.add(Label(order_id=order.id, data={k: v for k, v in label.items() if k != "order_id"}))
            db.flush()
            recompute(db, order)

    def write_message():
        with factory.begin() as db:
            order = db.scalar(select(Order).where(Order.id == capture["order_id"]).with_for_update())
            analysis = {**message["ai_analysis"], "confidence": 0.5}
            db.add(Message(order_id=order.id, external_id=message["id"], text=message["text"], analysis=analysis))
            db.flush()
            recompute(db, order)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write_label), executor.submit(write_message)]
        for future in futures:
            future.result(timeout=10)
    with client(factory) as api:
        assert api.get(f"/orders/{capture['order_id']}").json()["verdict"] == "REVIEW"
