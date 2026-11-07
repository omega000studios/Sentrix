import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow():
    return datetime.now(timezone.utc)


def make_engine(url):
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    capture_id: Mapped[str] = mapped_column(String(128), unique=True)
    paypal_order_id: Mapped[str] = mapped_column(String(128))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    paypal_address: Mapped[dict] = mapped_column(JSON)
    seller_protection: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(32), default="CAPTURED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("order_id", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    external_id: Mapped[str] = mapped_column(String(128))
    text: Mapped[str] = mapped_column(String(10000))
    analysis: Mapped[dict | None] = mapped_column(JSON)


class Label(Base):
    __tablename__ = "labels"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    data: Mapped[dict] = mapped_column(JSON)


class Verdict(Base):
    __tablename__ = "verdicts"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rule_version: Mapped[str] = mapped_column(String(32))
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


def session_factory():
    return sessionmaker(make_engine(os.environ["DATABASE_URL"]), expire_on_commit=False)
