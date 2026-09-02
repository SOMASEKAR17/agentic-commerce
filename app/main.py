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

    decision = authorize(offer, payload.session_id, "merchant_demo", catalog_lookup)

    return {
        "agreement_id": agreement_id,
        "final_amount": offer["final_amount"],
        "policy_decision": decision,
    }