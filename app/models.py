from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class OfferItem(BaseModel):
    product_id: str
    name: str
    price: int

class AcceptedOffer(BaseModel):
    """The canonical, validated execution contract. Instantiating this class
    IS the boundary the review asked for — if an offer can't validate into
    this shape, it never becomes an agreement, and nothing downstream
    (policy, payment) ever sees a raw dict again."""
    agreement_id: str
    offer_id: str
    buyer_id: str
    merchant_id: str
    items: List[OfferItem]
    final_amount: int = Field(gt=0)
    currency: str = "INR"
    status: str = "ACCEPTED"

    @field_validator("items")
    @classmethod
    def must_have_items(cls, v):
        if not v:
            raise ValueError("An accepted offer must contain at least one item.")
        return v

class NegotiateIn(BaseModel):
    session_id: str
    offer_id: str
    requested_discount: int = Field(ge=0, description="Negative discounts are rejected at the schema level.")

class AcceptIn(BaseModel):
    session_id: str
    offer_id: str

class ApprovalIn(BaseModel):
    session_id: str
    agreement_id: str
    # deliberately NO amount/items fields — approval can only act on the
    # exact persisted agreement, never on client-supplied numbers.
