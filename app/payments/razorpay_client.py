import os
import razorpay

client = razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))

def create_order(amount_rupees: int, receipt: str):
    """Amount in paise per Razorpay's API — multiply by 100."""
    order = client.order.create({
        "amount": amount_rupees * 100,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 0,   # explicit capture step — never auto-capture
    })
    return order

def fetch_order_status(order_id: str):
    return client.order.fetch(order_id)

def create_payment_link(amount_rupees: int, description: str, reference_id: str):
    link = client.payment_link.create({
        "amount": amount_rupees * 100,
        "currency": "INR",
        "description": description,
        "reference_id": reference_id,
        "notify": {"sms": False, "email": False},
    })
    return link

def fetch_payment_link_status(link_id: str):
    return client.payment_link.fetch(link_id)