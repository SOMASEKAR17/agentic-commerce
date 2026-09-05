from dotenv import load_dotenv
load_dotenv()
import json, uuid
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.models import NegotiateIn, AcceptIn, ApprovalIn
from app.agents.buyer_agent import extract_intent
from app.agents import a2a_client
from app.audit.audit_log import get_timeline, verify_chain
from app.db import init_db

MAX_CLARIFICATIONS = 3
REQUIRED_MERCHANT_SKILLS = {"product_discovery", "negotiate", "create_order"}

app = FastAPI(title="Buyer / Shopping Agent")
init_db()

SESSIONS: dict[str, dict] = {}
_merchant_verified = False  # set True once discovery succeeds; checked before every task submission

@app.on_event("startup")
def startup_discovery():
    """Agent discovery is validated, not decorative: if the Merchant Agent's
    card doesn't advertise the skills this buyer needs, tasks are refused
    up front instead of failing confusingly mid-conversation."""
    global _merchant_verified
    card = a2a_client.discover_merchant_agent()
    if card:
        advertised = {s["id"] for s in card.get("skills", [])}
        _merchant_verified = REQUIRED_MERCHANT_SKILLS.issubset(advertised)

@app.get("/")
def home():
    return FileResponse("app/static/chat.html")

class ChatIn(BaseModel):
    session_id: str
    message: str

def _get_session(session_id: str) -> dict:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "convo": [], "current_offer": None, "clarification_count": 0,
            "trace_id": str(uuid.uuid4())[:8], "buyer_id": session_id,
        }
    return SESSIONS[session_id]

def _merchant_unreachable_reply():
    global _merchant_verified
    card = a2a_client.discover_merchant_agent()
    if not card:
        return {"reply": "Merchant Agent unreachable — is merchant_service running on port 8001?", "done": False}
    advertised = {s["id"] for s in card.get("skills", [])}
    if not REQUIRED_MERCHANT_SKILLS.issubset(advertised):
        return {"reply": "Merchant Agent is reachable but doesn't advertise the skills this app needs.", "done": False}
    _merchant_verified = True
    return None

@app.post("/chat")
def chat(payload: ChatIn):
    if not _merchant_verified:
        blocked = _merchant_unreachable_reply()
        if blocked:
            return blocked

    session = _get_session(payload.session_id)
    convo = session["convo"]
    convo.append({"role": "user", "content": payload.message})

    intent = extract_intent(convo)
    convo.append({"role": "assistant", "content": json.dumps(intent)})

    # Deterministic clarification cap — enforced in code, not just requested of the LLM.
    if not intent.get("complete") and session["clarification_count"] < MAX_CLARIFICATIONS:
        session["clarification_count"] += 1
        return {"reply": intent.get("clarifying_question", "Tell me more?"), "done": False}
    if not intent.get("complete"):
        intent["complete"] = True  # force forward after the cap regardless of what the LLM wants

    result = a2a_client.request_task("PRODUCT_DISCOVERY", payload.session_id, session["buyer_id"], session["trace_id"], {
        "product": intent.get("product"), "budget": intent.get("budget"),
        "wireless": intent.get("wireless"), "noise_cancellation": intent.get("noise_cancellation"),
        "allow_bundle": intent.get("allow_bundle", True),
    })
    if result.get("status") != "COMPLETED":
        return {"reply": f"Merchant Agent error: {result.get('error', 'unknown error')}", "done": False}

    output = result["output"]
    top, offer = output.get("products"), output.get("offer")
    if not top:
        return {"reply": f"I couldn't find any {intent.get('product','matching products')} "
                          f"under ₹{intent.get('budget')}. Want to raise your budget?",
                "done": True, "products": [], "offer": None}

    session["current_offer"] = offer
    return {"reply": "Here's what I found within your budget.", "done": True, "products": top, "offer": offer}

@app.post("/negotiate")
def negotiate(payload: NegotiateIn):
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("NEGOTIATE", payload.session_id, session["buyer_id"], session["trace_id"], {
        "offer_id": payload.offer_id, "requested_discount": payload.requested_discount,
    })
    if result.get("status") != "COMPLETED":
        return {"reply": f"Merchant Agent error: {result.get('error', 'unknown error')}"}

    updated = result["output"]["offer"]
    session["current_offer"] = updated
    if "error" in updated:
        return {"reply": updated.get("message", updated["error"])}

    if updated.get("discount_capped"):
        msg = (f"I can't go that low, but I can offer ₹{updated['final_amount']} "
               f"(₹{updated['discount_applied']} off) — that's my maximum discount.")
    else:
        msg = f"Done — ₹{updated['final_amount']} works."
    return {"reply": msg, "offer": updated}

@app.post("/accept")
def accept(payload: AcceptIn):
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("CREATE_ORDER", payload.session_id, session["buyer_id"], session["trace_id"], {
        "offer_id": payload.offer_id,
    })
    if result.get("status") != "COMPLETED":
        return {"error": f"Merchant Agent error: {result.get('error', 'unknown error')}"}
    return result["output"]

@app.post("/approve")
def approve(payload: ApprovalIn):
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("APPROVE_PENDING", payload.session_id, session["buyer_id"], session["trace_id"], {
        "agreement_id": payload.agreement_id,
    })
    return result.get("output", result)

@app.post("/reject")
def reject(payload: ApprovalIn):
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("REJECT_PENDING", payload.session_id, session["buyer_id"], session["trace_id"], {
        "agreement_id": payload.agreement_id,
    })
    return result.get("output", result)

class AgreementIn(BaseModel):
    session_id: str
    agreement_id: str

@app.post("/payment-status")
def payment_status(payload: AgreementIn):
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("GET_PAYMENT_STATUS", payload.session_id, session["buyer_id"], session["trace_id"], {
        "agreement_id": payload.agreement_id,
    })
    return result.get("output", result)

@app.post("/create-payment")
def create_payment_endpoint(payload: AgreementIn):
    """Direct retry for an AUTHORIZED agreement whose first payment attempt
    failed at the provider (network/API error) — distinct from /retry-payment,
    which is specifically for a link that Razorpay itself confirmed expired."""
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("CREATE_PAYMENT", payload.session_id, session["buyer_id"], session["trace_id"], {
        "agreement_id": payload.agreement_id,
    })
    return result.get("output", result)

@app.post("/retry-payment")
def retry_payment(payload: AgreementIn):
    session = _get_session(payload.session_id)
    result = a2a_client.request_task("RETRY_PAYMENT", payload.session_id, session["buyer_id"], session["trace_id"], {
        "agreement_id": payload.agreement_id,
    })
    return result.get("output", result)

@app.get("/audit")
def audit():
    return {"timeline": get_timeline(), "chain_verified": verify_chain()}

@app.get("/agent-card")
def merchant_agent_card():
    card = a2a_client.discover_merchant_agent()
    return card or {"error": "Merchant Agent service not reachable on port 8001."}
