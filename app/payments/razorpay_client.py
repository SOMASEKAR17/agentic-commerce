import os
import razorpay
import random

def simulate_capture_with_timeout(order_id: str, amount_rupees: int, attempt: int = 1, max_attempts: int = 3):
    """
    Demo-only: simulates a network timeout on the first attempt, then checks
    order status before retrying — never blindly retries a payment call.
    """
    if attempt == 1:
        # simulate the timeout
        status = fetch_order_status(order_id)
        if status["status"] == "paid":
            return {"outcome": "ALREADY_PROCESSED_NO_RETRY", "order": status}
        # not processed — safe to proceed
        if attempt < max_attempts:
            return simulate_capture_with_timeout(order_id, amount_rupees, attempt + 1, max_attempts)
    return {"outcome": "CAPTURED_ON_RETRY", "attempt": attempt}

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