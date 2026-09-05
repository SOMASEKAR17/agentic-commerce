import time
from datetime import date
from app.db import get_conn

TOOL_CALL_BUDGET = 10
MAX_TRANSACTION = 5000  # hard merchant-wide ceiling — always BLOCKED above this, no buyer policy can override it
OFFER_TTL_SECONDS = 600
MAX_CUMULATIVE_RISK = 1.5  # a real "budget", not a single-check score

# ---------- persisted buyer policy ----------

def get_buyer_policy(buyer_id: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM buyer_policies WHERE buyer_id = ?", (buyer_id,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO buyer_policies (buyer_id, approval_mode, max_auto_purchase, daily_limit) "
            "VALUES (?, 'ASK_ALWAYS', 500, 8000)", (buyer_id,)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM buyer_policies WHERE buyer_id = ?", (buyer_id,)).fetchone()
    conn.close()
    return dict(row)

# ---------- persisted usage (survives a restart) ----------

def _today() -> str:
    return date.today().isoformat()

def _get_usage(buyer_id: str, conn) -> dict:
    row = conn.execute(
        "SELECT * FROM policy_usage WHERE buyer_id = ? AND usage_date = ?", (buyer_id, _today())
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO policy_usage (buyer_id, usage_date, tool_calls, daily_spend, cumulative_risk) "
            "VALUES (?, ?, 0, 0, 0)", (buyer_id, _today())
        )
        return {"tool_calls": 0, "daily_spend": 0, "cumulative_risk": 0.0}
    return dict(row)

def check_tool_budget(buyer_id: str) -> bool:
    conn = get_conn()
    usage = _get_usage(buyer_id, conn)
    conn.commit()
    conn.close()
    return usage["tool_calls"] < TOOL_CALL_BUDGET

def record_tool_call(buyer_id: str):
    """Called at the ACTUAL MCP tool-invocation boundary — every search,
    lookup, negotiation, and execution call counts, not just approved
    purchases."""
    conn = get_conn()
    _get_usage(buyer_id, conn)
    conn.execute(
        "UPDATE policy_usage SET tool_calls = tool_calls + 1 WHERE buyer_id = ? AND usage_date = ?",
        (buyer_id, _today()),
    )
    conn.commit()
    conn.close()

def check_daily_limit(buyer_id: str, amount: int) -> bool:
    conn = get_conn()
    usage = _get_usage(buyer_id, conn)
    conn.commit()
    conn.close()
    policy = get_buyer_policy(buyer_id)
    return usage["daily_spend"] + amount <= policy["daily_limit"]

def record_daily_spend(buyer_id: str, amount: int):
    conn = get_conn()
    _get_usage(buyer_id, conn)
    conn.execute(
        "UPDATE policy_usage SET daily_spend = daily_spend + ? WHERE buyer_id = ? AND usage_date = ?",
        (amount, buyer_id, _today()),
    )
    conn.commit()
    conn.close()

def record_risk_usage(buyer_id: str, risk: float):
    conn = get_conn()
    _get_usage(buyer_id, conn)
    conn.execute(
        "UPDATE policy_usage SET cumulative_risk = cumulative_risk + ? WHERE buyer_id = ? AND usage_date = ?",
        (risk, buyer_id, _today()),
    )
    conn.commit()
    conn.close()

def get_cumulative_risk(buyer_id: str) -> float:
    conn = get_conn()
    usage = _get_usage(buyer_id, conn)
    conn.commit()
    conn.close()
    return usage["cumulative_risk"]

# ---------- risk scoring, now buyer-specific ----------

_recent_transactions: list[dict] = []  # (buyer_id, amount, ts) — process-local, fine for a single demo run

def compute_risk_score(offer: dict, buyer_id: str) -> float:
    score = 0.0
    amount = offer["final_amount"]
    if amount > 4000:
        score += 0.3
    for tx in _recent_transactions[-10:]:
        if tx["buyer_id"] == buyer_id and tx["amount"] == amount:
            score += 0.3
            break
    listed_total = sum(item["price"] for item in offer["items"])
    if amount > listed_total:
        score += 0.5
    return round(min(score, 1.0), 2)

# ---------- tenant scope + stock, enforced in SQL, not Python ----------

def validate_items_in_sql(offer: dict, merchant_id: str) -> tuple[bool, str | None]:
    """Every item must resolve via a SINGLE query that filters on id,
    merchant_id, agent_enabled, AND stock — not fetch-then-compare in Python."""
    conn = get_conn()
    for item in offer["items"]:
        row = conn.execute(
            "SELECT id FROM products WHERE id = ? AND merchant_id = ? AND agent_enabled = 1 AND stock > 0",
            (item["product_id"], merchant_id),
        ).fetchone()
        if not row:
            conn.close()
            return False, item["product_id"]
    conn.close()
    return True, None

# ---------- main authorization ----------

def _result(status, reason, explanation, risk=0.0):
    return {"status": status, "decision_reason": reason,
            "agent_explanation": explanation, "risk_score": risk}

def authorize(offer: dict, buyer_id: str, merchant_id: str = "merchant_demo",
              offer_age_seconds: float = 0, human_confirmed: bool = False) -> dict:
    amount = offer["final_amount"]
    policy = get_buyer_policy(buyer_id)

    if offer_age_seconds > OFFER_TTL_SECONDS:
        return _result("BLOCKED", "OFFER_EXPIRED",
                        "This offer has expired — please search again for current pricing.")

    if not check_tool_budget(buyer_id):
        return _result("BLOCKED", "TOOL_BUDGET_EXCEEDED",
                        "I've reached the maximum number of actions for this session.")

    if amount > MAX_TRANSACTION:
        return _result("BLOCKED", "MAX_TRANSACTION_LIMIT_EXCEEDED",
                        f"This purchase (₹{amount}) exceeds the merchant's limit of ₹{MAX_TRANSACTION}.")

    if not check_daily_limit(buyer_id, amount):
        return _result("BLOCKED", "DAILY_LIMIT_EXCEEDED",
                        f"This would exceed your daily spending limit of ₹{policy['daily_limit']}.")

    listed_total = sum(item["price"] for item in offer["items"])
    if amount > listed_total:
        return _result("BLOCKED", "PRICE_TAMPER_DETECTED",
                        "The proposed amount doesn't match the catalog price of these items.")

    valid, bad_id = validate_items_in_sql(offer, merchant_id)
    if not valid:
        return _result("BLOCKED", "SCOPE_OR_STOCK_VIOLATION",
                        f"Item {bad_id} isn't available from this merchant right now.")

    risk = compute_risk_score(offer, buyer_id)
    cumulative = get_cumulative_risk(buyer_id) + risk
    if cumulative > MAX_CUMULATIVE_RISK:
        return _result("BLOCKED", "RISK_BUDGET_EXCEEDED",
                        "This session has accumulated too much risk exposure — further purchases need manual review.", risk)

    # This is the ONLY gate deciding auto-approve vs. human approval — driven
    # entirely by the buyer's persisted policy, not a hardcoded global. A
    # buyer with a higher configured max_auto_purchase genuinely gets a
    # smoother experience; there is no competing fixed threshold undermining it.
    needs_human = (not human_confirmed) and (
        amount > policy["max_auto_purchase"] or
        policy["approval_mode"] == "ASK_ALWAYS" or
        risk > 0.6
    )
    if needs_human:
        return _result("HUMAN_APPROVAL_REQUIRED", "ABOVE_AUTO_APPROVE_THRESHOLD",
                        f"This ₹{amount} purchase needs your confirmation before I proceed.", risk)

    record_daily_spend(buyer_id, amount)
    record_risk_usage(buyer_id, risk)
    _recent_transactions.append({"buyer_id": buyer_id, "amount": amount, "ts": time.time()})
    return _result("APPROVED", "WITHIN_LIMITS", "Transaction is within all configured limits.", risk)
