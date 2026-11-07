from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Address(Contract):
    line1: str = Field(default="", max_length=256)
    line2: str = Field(default="", max_length=256)
    city: str = Field(default="", max_length=128)
    state: str = Field(default="", max_length=32)
    postal_code: str = Field(default="", max_length=16)
    country: Literal["US"] = "US"


class Amount(Contract):
    value: str = Field(pattern=r"^\d{1,10}\.\d{2}$")
    currency: Literal["USD"] = "USD"

    @field_validator("value")
    @classmethod
    def positive(cls, value):
        if Decimal(value) <= 0:
            raise ValueError("amount must be positive")
        return f"{Decimal(value):.2f}"


class Capture(Contract):
    order_id: Identifier
    paypal_order_id: Identifier
    capture_id: Identifier
    amount: Amount
    paypal_address: Address
    seller_protection: Literal["ELIGIBLE", "PARTIALLY_ELIGIBLE", "NOT_ELIGIBLE", "UNKNOWN"]
    source: Literal["sandbox", "fixture"]


class Analysis(Contract):
    intent: Literal["ADDRESS_CHANGE_REQUEST", "DELIVERY_QUESTION", "THANKS", "OTHER", "AMBIGUOUS"]
    confidence: Confidence
    quote: str = Field(min_length=1, max_length=10000)
    proposed_address: Address | None = None


class MessageInput(Contract):
    order_id: Identifier
    id: Identifier
    text: str = Field(min_length=1, max_length=10000)
    ai_analysis: Analysis | None = None


class LabelData(Contract):
    address: Address
    tracking_number: str = Field(default="", max_length=128)
    carrier: str = Field(default="", max_length=128)
    confidence: Confidence | None = None


class LabelInput(LabelData):
    order_id: Identifier


class Comparison(Contract):
    match: Literal["MATCH", "NEAR_MATCH", "MISMATCH"] | None = None
    reasons: list[str] = Field(default_factory=list)


class OrderView(Capture):
    state: Literal["CAPTURED", "MESSAGE_FLAGGED", "PROTECTED", "REVIEW", "BLOCKED"]
    created_at: str
    updated_at: str
    message: dict | None = None
    ai_analysis: Analysis | None = None
    label: LabelData | None = None
    comparison: Comparison
    verdict: Literal["PROTECTED", "REVIEW", "BLOCKED"] | None = None
    recommended_action: Literal["PRINT_AND_TRACK", "HUMAN_REVIEW", "HOLD_REFUND_REORDER"] | None = None
