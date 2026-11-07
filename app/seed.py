"""python -m app.seed: insert synthetic scenarios without overwriting existing orders."""
from app.db import Label, Message, Order, session_factory
from app.schemas import Capture, LabelInput, MessageInput
from app.service import ingest_capture, recompute
from fixtures.scenarios import scenario


def seed(factory):
    with factory.begin() as db:
        for name in ("clean", "mismatch", "uncertain"):
            capture, message, label = scenario(name)
            if db.get(Order, capture["order_id"]):
                continue
            order = ingest_capture(db, Capture.model_validate(capture))
            message = MessageInput.model_validate(message)
            label = LabelInput.model_validate(label)
            db.add(Message(order_id=order.id, external_id=message.id, text=message.text, analysis=message.ai_analysis.model_dump()))
            db.add(Label(order_id=order.id, data=label.model_dump(exclude={"order_id"})))
            db.flush()
            recompute(db, order)


if __name__ == "__main__":
    seed(session_factory())
    print("Synthetic fixtures seeded (existing orders left intact).")
