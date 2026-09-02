from app.db import get_conn

MAX_DISCOUNT_PCT = 10

def propose_bundle(main_product: dict, intent: dict):
    remaining_budget = (intent.get("budget") or 0) - main_product["price"]
    conn = get_conn()
    case = conn.execute(
        "SELECT * FROM products WHERE name LIKE '%Case%' AND agent_enabled=1"
    ).fetchone()
    conn.close()

    if case and case["price"] <= remaining_budget + 200:
        original_total = main_product["price"] + case["price"]
        bundle_price = int(original_total * 0.96)
        return {
            "type": "BUNDLE",
            "items": [
                {"product_id": main_product["id"], "name": main_product["name"], "price": main_product["price"]},
                {"product_id": case["id"], "name": case["name"], "price": case["price"]},
            ],
            "original_total": original_total,
            "final_amount": bundle_price,
        }
    return {
        "type": "SINGLE",
        "items": [{"product_id": main_product["id"], "name": main_product["name"], "price": main_product["price"]}],
        "original_total": main_product["price"],
        "final_amount": main_product["price"],
    }

def apply_discount_request(offer: dict, requested_discount: int):
    max_allowed = int(offer["original_total"] * MAX_DISCOUNT_PCT / 100)
    granted = min(requested_discount, max_allowed)
    offer["final_amount"] = offer["original_total"] - granted
    offer["discount_applied"] = granted
    offer["discount_capped"] = granted < requested_discount
    return offer