from pydantic import BaseModel
from typing import Optional, List

class OfferItem(BaseModel):
    product_id: str
    name: str
    price: int

class AcceptedOffer(BaseModel):
    agreement_id: str
    buyer_id: str
    merchant_id: str
    items: List[OfferItem]
    final_amount: int
    currency: str = "INR"
    status: str = "ACCEPTED"