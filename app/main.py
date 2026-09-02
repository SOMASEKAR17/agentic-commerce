from dotenv import load_dotenv
load_dotenv()
import json, uuid
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.db import init_db, get_conn
from app.models import NegotiateIn, AcceptIn
from app.agents.buyer_agent import extract_intent
from app.agents.merchant_agent import search_and_rank
from app.agents.growth_engine import apply_discount_request
from app.policy.policy_engine import authorize
from pydantic import BaseModel
from app.audit.audit_log import log_event, get_timeline, verify_chain
from app.payments.razorpay_client import (
    create_order as rp_create_order,
    fetch_order_status,
    simulate_capture_with_timeout,
)

app = FastAPI()
init_db()

SESSIONS: dict[str, dict] = {}  # session_id -> {"convo": [...], "current_offer": {...}}

def catalog_lookup(product_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

@app.get("/")
def home():
    return FileResponse("app/static/chat.html")

class ChatIn(BaseModel):
    session_id: str
    message: str

class FailureDemoIn(BaseModel):
    order_id: str
    amount: int

@app.post("/demo/timeout-retry")
def demo_timeout_retry(payload: FailureDemoIn):
    log_event("razorpay", "PAYMENT_TIMEOUT", payload.amount,
              "N/A", "Simulated network timeout during capture.")
    result = simulate_capture_with_timeout(payload.order_id, payload.amount)
    log_event("system", "STATUS_CHECK_BEFORE_RETRY", payload.amount,
              "N/A", "Checked order status before retrying — avoided potential double charge.")
    log_event("razorpay", result["outcome"], payload.amount,
              "N/A", f"Retry resolved with: {result['outcome']}")
    return result

@app.post("/chat")
def chat(payload: ChatIn):
    session = SESSIONS.setdefault(payload.session_id, {"convo": [], "current_offer": None})
    convo = session["convo"]
    convo.append({"role": "user", "content": payload.message})

    intent = extract_intent(convo)
    convo.append({"role": "assistant", "content": json.dumps(intent)})

    if not intent.get("complete"):
        return {"reply": intent.get("clarifying_question", "Tell me more?"), "done": False}

    top, offer = search_and_rank(intent)
    if not top:
        return {"reply": f"I couldn't find any {intent.get('product','matching products')} "
                          f"under ₹{intent.get('budget')}. Want to raise your budget?",
                "done": True, "products": [], "offer": None}

    session["current_offer"] = offer
    return {"reply": "Here's what I found within your budget.", "done": True,
            "products": top, "offer": offer}

@app.post("/negotiate")
def negotiate(payload: NegotiateIn):
    session = SESSIONS.get(payload.session_id)
    if not session or not session.get("current_offer"):
        return {"error": "No active offer to negotiate on."}

    updated = apply_discount_request(session["current_offer"], payload.requested_discount)
    session["current_offer"] = updated

    if updated["discount_capped"]:
        msg = (f"I can't go that low, but I can offer ₹{updated['final_amount']} "
               f"(₹{updated['discount_applied']} off) — that's my maximum discount.")
    else:
        msg = f"Done — ₹{updated['final_amount']} works."
    return {"reply": msg, "offer": updated}

@app.get("/audit")
def audit():
    return {"timeline": get_timeline(), "chain_verified": verify_chain()}

@app.post("/accept")
def accept(payload: AcceptIn):
    session = SESSIONS.get(payload.session_id)
    if not session or not session.get("current_offer"):
        return {"error": "No active offer to accept."}

    offer = session["current_offer"]
    agreement_id = str(uuid.uuid4())[:8]

    conn = get_conn()
    conn.execute(
        "INSERT INTO agreements (agreement_id, buyer_id, merchant_id, items, final_amount, status) "
        "VALUES (?,?,?,?,?,?)",
        (agreement_id, payload.session_id, "merchant_demo",
         json.dumps(offer["items"]), offer["final_amount"], "ACCEPTED"),
    )
    conn.commit()
    conn.close()

    log_event("buyer_agent", "OFFER_ACCEPTED", offer["final_amount"],
              "N/A", f"Buyer accepted offer {agreement_id}.")

    decision = authorize(offer, payload.session_id, "merchant_demo", catalog_lookup)
    log_event("policy_engine", "AUTHORIZATION_CHECK", offer["final_amount"],
              decision["decision_reason"], decision["agent_explanation"])

    if decision["status"] != "APPROVED":
        return {"agreement_id": agreement_id, "policy_decision": decision, "razorpay_order": None}

    rp_order = rp_create_order(offer["final_amount"], receipt=agreement_id)
    log_event("razorpay", "ORDER_CREATED", offer["final_amount"],
              "APPROVED", f"Razorpay order {rp_order['id']} created.")

    return {
        "agreement_id": agreement_id,
        "final_amount": offer["final_amount"],
        "policy_decision": decision,
        "razorpay_order": rp_order,
    }