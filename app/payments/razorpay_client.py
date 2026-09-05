import os
import razorpay

_client = None

def get_client():
    """Lazy-initialized so importing this module never crashes just because
    env vars aren't loaded yet — the error now surfaces at first real use,
    with a clear message, not as a bare KeyError during app startup."""
    global _client
    if _client is None:
        key_id = os.environ.get("RAZORPAY_KEY_ID")
        key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
        if not key_id or not key_secret:
            raise RuntimeError(
                "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set. "
                "Add them to your .env before creating any payment link."
            )
        _client = razorpay.Client(auth=(key_id, key_secret))
    return _client

def create_payment_link(amount_rupees: int, description: str, reference_id: str):
    return get_client().payment_link.create({
        "amount": amount_rupees * 100,
        "currency": "INR",
        "description": description,
        "reference_id": reference_id,
        "notify": {"sms": False, "email": False},
    })

def fetch_payment_link_status(link_id: str):
    return get_client().payment_link.fetch(link_id)

def check_and_recover_payment(link_id: str) -> dict:
    """
    The REAL version of the old timeout/retry demo. This makes an actual
    Razorpay API call to fetch the payment link's current state and decides
    what to do from real provider state — never assumes success or failure.

    Razorpay payment_link statuses: 'created', 'paid', 'partially_paid',
    'expired', 'cancelled'.
    """
    status = fetch_payment_link_status(link_id)
    state = status.get("status")

    if state == "paid":
        return {"outcome": "ALREADY_PAID", "recommend_retry": False, "provider_status": status}
    if state in ("expired", "cancelled"):
        return {"outcome": "LINK_DEAD_NEEDS_NEW_LINK", "recommend_retry": True, "provider_status": status}
    return {"outcome": "STILL_PENDING", "recommend_retry": False, "provider_status": status}
