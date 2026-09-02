import time

_tool_call_counts: dict[str, int] = {}
_recent_transactions: list[dict] = []

TOOL_CALL_BUDGET = 10
MAX_TRANSACTION = 5000
AUTO_APPROVE_LIMIT = 500
HUMAN_CONFIRM_THRESHOLD = 3000

def check_tool_budget(session_id: str) -> bool:
    return _tool_call_counts.get(session_id, 0) < TOOL_CALL_BUDGET

def increment_tool_call(session_id: str):
    _tool_call_counts[session_id] = _tool_call_counts.get(session_id, 0) + 1

def compute_risk_score(offer: dict, merchant_id: str) -> float:
    score = 0.0
    amount = offer["final_amount"]

    if amount > 4000:
        score += 0.3

    for tx in _recent_transactions[-5:]:
        if tx["merchant_id"] == merchant_id and tx["amount"] == amount:
            score += 0.3
            break

    listed_total = sum(item["price"] for item in offer["items"])
    if amount > listed_total:
        score += 0.5  # discounted amount should never exceed listed total

    return round(min(score, 1.0), 2)

def check_scope(offer: dict, catalog_lookup) -> bool:
    """Every item must genuinely exist in the merchant's own catalog."""
    for item in offer["items"]:
        if catalog_lookup(item["product_id"]) is None:
            return False
    return True

def _result(status, reason, explanation, risk=0.0):
    return {"status": status, "decision_reason": reason,
            "agent_explanation": explanation, "risk_score": risk}

def authorize(offer: dict, session_id: str, merchant_id: str = "merchant_demo",
              catalog_lookup=None) -> dict:
    amount = offer["final_amount"]

    if not check_tool_budget(session_id):
        return _result("BLOCKED", "TOOL_BUDGET_EXCEEDED",
                        "I've reached the maximum number of actions for this session.")

    if amount > MAX_TRANSACTION:
        return _result("BLOCKED", "MAX_TRANSACTION_LIMIT_EXCEEDED",
                        f"This purchase (₹{amount}) exceeds the merchant's limit of ₹{MAX_TRANSACTION}.")

    listed_total = sum(item["price"] for item in offer["items"])
    if amount > listed_total:
        return _result("BLOCKED", "PRICE_TAMPER_DETECTED",
                        "The proposed amount doesn't match the catalog price of these items.")

    if catalog_lookup and not check_scope(offer, catalog_lookup):
        return _result("BLOCKED", "SCOPE_VIOLATION",
                        "One or more items aren't in this merchant's catalog.")

    risk = compute_risk_score(offer, merchant_id)

    if amount > HUMAN_CONFIRM_THRESHOLD or risk > 0.6:
        return _result("HUMAN_APPROVAL_REQUIRED", "ABOVE_AUTO_APPROVE_THRESHOLD",
                        f"This ₹{amount} purchase needs your confirmation before I proceed.", risk)

    increment_tool_call(session_id)
    _recent_transactions.append({"merchant_id": merchant_id, "amount": amount, "ts": time.time()})
    return _result("APPROVED", "WITHIN_LIMITS",
                    "Transaction is within all configured limits.", risk)