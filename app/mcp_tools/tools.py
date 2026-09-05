"""
Real MCP tool server for the Merchant Agent. Every catalog, negotiation,
authorization, and payment action lives here as an MCP tool — this is the
actual execution surface, not a parallel copy of logic that main.py or
merchant_service call directly. merchant_service talks to this file ONLY
through a real MCP ClientSession (see app/mcp_tools/mcp_client.py); nothing
else imports these functions directly.
"""
import sys, uuid, json, sqlite3, time, calendar
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP
from app.db import get_conn
from app.agents.merchant_agent import search_and_rank
from app.agents.growth_engine import propose_bundle as _propose_bundle, apply_discount_request
from app.models import AcceptedOffer, OfferItem
from app.policy.policy_engine import authorize, record_tool_call
from app.audit.audit_log import log_event
from app.payments.razorpay_client import create_payment_link, check_and_recover_payment

mcp = FastMCP("razorpay-commerce-agent")

# ---------------- helpers ----------------

def _offer_row_to_dict(row) -> dict:
    return {
        "offer_id": row["offer_id"], "type": "BUNDLE" if len(json.loads(row["items"])) > 1 else "SINGLE",
        "items": json.loads(row["items"]), "original_total": row["original_total"],
        "final_amount": row["final_amount"], "version": row["version"],
    }

def _is_offer_head(offer_id: str, conn) -> bool:
    """An offer is only usable if nothing has superseded it."""
    row = conn.execute("SELECT 1 FROM offers WHERE supersedes = ?", (offer_id,)).fetchone()
    return row is None

# ---------------- 1. search_agent_catalog ----------------

@mcp.tool()
def search_agent_catalog(buyer_id: str, product: str = "", budget: int | None = None,
                          wireless: bool | None = None, noise_cancellation: bool | None = None,
                          top_n: int = 3, trace_id: str | None = None) -> dict:
    """Search the merchant's agent-enabled catalog, ranked against stated buyer preferences."""
    record_tool_call(buyer_id)
    intent = {"product": product, "budget": budget, "wireless": wireless, "noise_cancellation": noise_cancellation}
    top, _ = search_and_rank(intent, top_n)
    log_event("merchant_agent", "CATALOG_SEARCHED", None, "N/A",
              f"Searched for '{product}', {len(top)} results.", trace_id)
    if top:
        log_event("merchant_agent", "PRODUCT_RANKED", None, "N/A",
                  f"Top pick: {top[0]['name']} (₹{top[0]['price']}).", trace_id)
    return {"products": top}

# ---------------- 2. get_product_details ----------------

@mcp.tool()
def get_product_details(buyer_id: str, product_id: str) -> dict | None:
    """Fetch full details for one product by id."""
    record_tool_call(buyer_id)
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ---------------- 3. propose_bundle ----------------

@mcp.tool()
def propose_bundle(buyer_id: str, session_id: str, product_id: str, budget: int | None = None,
                    allow_bundle: bool = True, trace_id: str | None = None) -> dict:
    """Propose an offer (possibly a growth bundle) for a chosen product. Persists offer v1."""
    record_tool_call(buyer_id)
    conn = get_conn()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return {"error": "PRODUCT_NOT_FOUND"}
    product = dict(product)
    offer = _propose_bundle(product, budget, allow_bundle)

    offer_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO offers (offer_id, session_id, merchant_id, items, original_total, final_amount, version, supersedes) "
        "VALUES (?,?,?,?,?,?,1,NULL)",
        (offer_id, session_id, product.get("merchant_id", "merchant_demo"), json.dumps(offer["items"]),
         offer["original_total"], offer["final_amount"]),
    )
    conn.commit()
    conn.close()

    log_event("merchant_agent", "BUNDLE_PROPOSED", offer["final_amount"], "N/A",
              f"Proposed {offer['type']} offer {offer_id} at ₹{offer['final_amount']}.", trace_id)
    return {"offer_id": offer_id, **offer, "version": 1}

# ---------------- 4. negotiate_discount ----------------

@mcp.tool()
def negotiate_discount(buyer_id: str, session_id: str, offer_id: str, requested_discount: int,
                        trace_id: str | None = None) -> dict:
    """Evaluate a counter-offer against merchant discount policy. Never mutates the
    existing offer — always creates a new version pointing back at the old one."""
    record_tool_call(buyer_id)
    requested_discount = max(int(requested_discount), 0)  # re-validated at the tool boundary, not just the API schema

    conn = get_conn()
    row = conn.execute("SELECT * FROM offers WHERE offer_id = ?", (offer_id,)).fetchone()
    if not row:
        conn.close()
        return {"error": "OFFER_NOT_FOUND"}
    if not _is_offer_head(offer_id, conn):
        conn.close()
        return {"error": "STALE_OFFER", "message": "This offer has already been superseded — use the latest offer_id."}

    current = _offer_row_to_dict(row)
    updated = apply_discount_request(current, requested_discount)

    new_offer_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO offers (offer_id, session_id, merchant_id, items, original_total, final_amount, version, supersedes) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (new_offer_id, session_id, row["merchant_id"], json.dumps(updated["items"]),
         updated["original_total"], updated["final_amount"], row["version"] + 1, offer_id),
    )
    conn.commit()
    conn.close()

    log_event("buyer_agent", "COUNTER_OFFER", None, "N/A",
              f"Buyer requested ₹{requested_discount} off offer {offer_id}.", trace_id)
    log_event("merchant_agent", "DISCOUNT_DECISION", updated["final_amount"],
              "CAPPED" if updated["discount_capped"] else "GRANTED",
              f"Granted ₹{updated['discount_applied']} (offer {new_offer_id}, v{row['version']+1}).", trace_id)

    return {"offer_id": new_offer_id, **updated, "version": row["version"] + 1}

# ---------------- 5. create_order (== authorize; no Razorpay call here) ----------------

@mcp.tool()
def create_order(buyer_id: str, session_id: str, offer_id: str, merchant_id: str = "merchant_demo",
                  trace_id: str | None = None) -> dict:
    """
    Turn a negotiated offer into the canonical, immutable AcceptedOffer, then
    run deterministic policy against THAT persisted snapshot — never against
    anything the network sent. No Razorpay call happens in this step.
    """
    record_tool_call(buyer_id)
    conn = get_conn()
    row = conn.execute("SELECT * FROM offers WHERE offer_id = ?", (offer_id,)).fetchone()
    if not row:
        conn.close()
        return {"error": "OFFER_NOT_FOUND"}
    if not _is_offer_head(offer_id, conn):
        conn.close()
        return {"error": "STALE_OFFER", "message": "This offer has already been superseded — use the latest offer_id."}

    items = json.loads(row["items"])
    agreement_id = str(uuid.uuid4())[:8]

    try:
        accepted = AcceptedOffer(
            agreement_id=agreement_id, offer_id=offer_id, buyer_id=buyer_id, merchant_id=merchant_id,
            items=[OfferItem(**i) for i in items], final_amount=row["final_amount"],
        )
    except Exception as e:
        conn.close()
        return {"error": "VALIDATION_FAILED", "message": str(e)}

    conn.execute(
        "INSERT INTO agreements (agreement_id, offer_id, buyer_id, merchant_id, items, final_amount, status, trace_id) "
        "VALUES (?,?,?,?,?,?,'ACCEPTED',?)",
        (accepted.agreement_id, accepted.offer_id, accepted.buyer_id, accepted.merchant_id,
         json.dumps([i.model_dump() for i in accepted.items]), accepted.final_amount, trace_id),
    )
    conn.commit()

    offer_age = time.time() - calendar.timegm(time.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S"))
    conn.close()

    log_event("buyer_agent", "OFFER_ACCEPTED", accepted.final_amount, "N/A",
              f"Buyer accepted offer {offer_id} as agreement {agreement_id}.", trace_id, agreement_id)

    decision = authorize(
        {"items": [i.model_dump() for i in accepted.items], "final_amount": accepted.final_amount},
        buyer_id, merchant_id, offer_age_seconds=offer_age,
    )
    log_event("policy_engine", "AUTHORIZATION_CHECK", accepted.final_amount,
              decision["decision_reason"], decision["agent_explanation"], trace_id, agreement_id)

    conn = get_conn()
    new_status = "AUTHORIZED" if decision["status"] == "APPROVED" else (
        "PENDING_HUMAN_APPROVAL" if decision["status"] == "HUMAN_APPROVAL_REQUIRED" else "BLOCKED"
    )
    conn.execute("UPDATE agreements SET status = ? WHERE agreement_id = ?", (new_status, agreement_id))
    conn.commit()
    conn.close()

    return {"agreement_id": agreement_id, "policy_decision": decision, "status": new_status}

# ---------------- 6a. approve_pending (human approval continuation) ----------------

@mcp.tool()
def approve_pending(buyer_id: str, agreement_id: str, trace_id: str | None = None) -> dict:
    """Continue a PENDING_HUMAN_APPROVAL agreement. Takes ONLY agreement_id —
    re-authorizes against the exact persisted snapshot, never a new amount."""
    record_tool_call(buyer_id)
    conn = get_conn()
    row = conn.execute("SELECT * FROM agreements WHERE agreement_id = ?", (agreement_id,)).fetchone()
    if not row:
        conn.close()
        return {"error": "AGREEMENT_NOT_FOUND"}
    if row["status"] != "PENDING_HUMAN_APPROVAL":
        conn.close()
        return {"error": "NOT_PENDING", "message": f"Agreement status is {row['status']}, not PENDING_HUMAN_APPROVAL."}
    conn.close()

    offer = {"items": json.loads(row["items"]), "final_amount": row["final_amount"]}
    decision = authorize(offer, buyer_id, row["merchant_id"], offer_age_seconds=0, human_confirmed=True)
    log_event("human", "HUMAN_APPROVED", row["final_amount"], decision["decision_reason"],
              "Human explicitly confirmed this exact agreement.", trace_id, agreement_id)

    conn = get_conn()
    new_status = "AUTHORIZED" if decision["status"] == "APPROVED" else "BLOCKED"
    conn.execute("UPDATE agreements SET status = ? WHERE agreement_id = ?", (new_status, agreement_id))
    conn.commit()
    conn.close()
    return {"agreement_id": agreement_id, "policy_decision": decision, "status": new_status}

@mcp.tool()
def reject_pending(buyer_id: str, agreement_id: str, trace_id: str | None = None) -> dict:
    """Reject a PENDING_HUMAN_APPROVAL agreement."""
    record_tool_call(buyer_id)
    conn = get_conn()
    conn.execute("UPDATE agreements SET status = 'REJECTED' WHERE agreement_id = ?", (agreement_id,))
    conn.commit()
    conn.close()
    log_event("human", "HUMAN_REJECTED", None, "N/A", f"Human rejected agreement {agreement_id}.", trace_id, agreement_id)
    return {"agreement_id": agreement_id, "status": "REJECTED"}

# ---------------- 6b. create_payment (idempotent, atomic stock, real Razorpay call) ----------------

@mcp.tool()
def create_payment(buyer_id: str, agreement_id: str, retry_after_expiry: bool = False,
                    trace_id: str | None = None) -> dict:
    """
    Creates the actual Razorpay payment link. Atomic idempotency: the
    payment_attempts row is INSERTed before Razorpay is ever called, and the
    UNIQUE constraint on agreement_id means only one process can win that
    insert. Stock is decremented atomically (UPDATE ... WHERE stock > 0,
    checking rowcount) immediately before the Razorpay call, and rolled back
    if any item fails — never after.
    """
    record_tool_call(buyer_id)
    conn = get_conn()
    agreement = conn.execute("SELECT * FROM agreements WHERE agreement_id = ?", (agreement_id,)).fetchone()
    if not agreement:
        conn.close()
        return {"error": "AGREEMENT_NOT_FOUND"}

    need_stock_check = False

    if retry_after_expiry:
        if agreement["status"] not in ("PAYMENT_CREATED", "EXPIRED"):
            conn.close()
            return {"error": "NOT_RETRYABLE", "message": f"Agreement status is {agreement['status']}."}
        # stock was already reserved on the original attempt — never decrement twice
    else:
        if agreement["status"] != "AUTHORIZED":
            conn.close()
            return {"error": "NOT_AUTHORIZED", "message": f"Agreement status is {agreement['status']}."}
        try:
            conn.execute("INSERT INTO payment_attempts (agreement_id, status) VALUES (?, 'CREATING')", (agreement_id,))
            conn.commit()
            need_stock_check = True
        except sqlite3.IntegrityError:
            # A payment_attempts row already exists for this agreement — the
            # right response depends on WHAT state that attempt is in, not
            # just "it exists":
            #   CREATED  -> a real link already exists, replay it (never call Razorpay twice)
            #   CREATING -> another request is actively in flight right now (genuine race)
            #   FAILED   -> the previous attempt never reached Razorpay successfully;
            #               this IS a legitimate retry, not a duplicate charge risk
            existing = conn.execute("SELECT * FROM payment_attempts WHERE agreement_id = ?", (agreement_id,)).fetchone()
            conn.close()
            if existing["status"] == "CREATED":
                return {"agreement_id": agreement_id, "status": "IDEMPOTENT_REPLAY",
                         "payment_link_url": existing["razorpay_payment_link_url"]}
            if existing["status"] == "CREATING":
                return {"agreement_id": agreement_id, "status": "IN_PROGRESS",
                         "message": "A payment attempt for this agreement is already being processed."}
            # status == "FAILED": fall through to retry, stock already reserved from the first attempt
            conn = get_conn()

    if need_stock_check:
        items = json.loads(agreement["items"])
        stock_ok = True
        for item in items:
            cur = conn.execute(
                "UPDATE products SET stock = stock - 1 WHERE id = ? AND merchant_id = ? AND stock > 0",
                (item["product_id"], agreement["merchant_id"]),
            )
            if cur.rowcount != 1:
                stock_ok = False
                break

        if not stock_ok:
            conn.rollback()  # undoes any successful decrements in this same transaction — atomic
            conn = get_conn()
            conn.execute("UPDATE payment_attempts SET status = 'FAILED' WHERE agreement_id = ?", (agreement_id,))
            conn.execute("UPDATE agreements SET status = 'FAILED' WHERE agreement_id = ?", (agreement_id,))
            conn.commit()
            conn.close()
            log_event("policy_engine", "OUT_OF_STOCK", agreement["final_amount"], "OUT_OF_STOCK",
                      "Stock reservation failed atomically — no Razorpay call made.", trace_id, agreement_id)
            return {"error": "OUT_OF_STOCK", "agreement_id": agreement_id}

        conn.commit()  # stock decrement is now durable BEFORE we ever call Razorpay

    conn.close()

    try:
        link = create_payment_link(agreement["final_amount"], f"Order {agreement_id}", agreement_id)
    except Exception as e:
        # Provider is unreachable/erroring — stock stays reserved (we don't
        # know if Razorpay actually received the request), but the attempt
        # is marked FAILED so a later call can legitimately retry instead
        # of being permanently stuck behind the idempotency guard.
        conn = get_conn()
        conn.execute("UPDATE payment_attempts SET status = 'FAILED' WHERE agreement_id = ?", (agreement_id,))
        conn.commit()
        conn.close()
        log_event("razorpay", "PAYMENT_LINK_CREATION_FAILED", agreement["final_amount"],
                  "PROVIDER_ERROR", f"Razorpay call failed: {e}", trace_id, agreement_id)
        return {"error": "PAYMENT_PROVIDER_ERROR", "message": str(e), "agreement_id": agreement_id}

    conn = get_conn()
    conn.execute(
        "UPDATE payment_attempts SET razorpay_payment_link_id = ?, razorpay_payment_link_url = ?, status = 'CREATED' "
        "WHERE agreement_id = ?",
        (link["id"], link["short_url"], agreement_id),
    )
    conn.execute(
        "UPDATE agreements SET razorpay_payment_link_id = ?, razorpay_payment_link_url = ?, status = 'PAYMENT_CREATED' "
        "WHERE agreement_id = ?",
        (link["id"], link["short_url"], agreement_id),
    )
    conn.commit()
    conn.close()

    log_event("razorpay", "PAYMENT_LINK_CREATED", agreement["final_amount"], "APPROVED",
              f"Payment link {link['id']} created for agreement {agreement_id}.", trace_id, agreement_id)

    return {"agreement_id": agreement_id, "status": "PAYMENT_CREATED",
            "payment_link_id": link["id"], "payment_link_url": link["short_url"]}

# ---------------- 6c. get_payment_status ----------------

@mcp.tool()
def get_payment_status(buyer_id: str, agreement_id: str, trace_id: str | None = None) -> dict:
    """Fetch REAL Razorpay payment link status — used before any retry decision."""
    record_tool_call(buyer_id)
    conn = get_conn()
    agreement = conn.execute("SELECT * FROM agreements WHERE agreement_id = ?", (agreement_id,)).fetchone()
    if not agreement or not agreement["razorpay_payment_link_id"]:
        conn.close()
        return {"error": "NO_PAYMENT_LINK_YET"}
    link_id = agreement["razorpay_payment_link_id"]
    conn.close()

    result = check_and_recover_payment(link_id)

    new_status = {"ALREADY_PAID": "PAID", "STILL_PENDING": "PAYMENT_PENDING",
                  "LINK_DEAD_NEEDS_NEW_LINK": "EXPIRED"}[result["outcome"]]
    conn = get_conn()
    conn.execute("UPDATE agreements SET status = ? WHERE agreement_id = ?", (new_status, agreement_id))
    if new_status == "EXPIRED":
        conn.execute("UPDATE payment_attempts SET status = 'EXPIRED' WHERE agreement_id = ?", (agreement_id,))
    conn.commit()
    conn.close()

    log_event("razorpay", "STATUS_CHECK_BEFORE_RETRY", agreement["final_amount"], "N/A",
              f"Real provider status: {result['outcome']}.", trace_id, agreement_id)

    return {"agreement_id": agreement_id, "status": new_status, "recommend_retry": result["recommend_retry"]}

if __name__ == "__main__":
    mcp.run()
