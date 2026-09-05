from app.db import get_conn

MAX_DISCOUNT_PCT = 10

ACCESSORY_PAIRINGS = [
    ("Protective Headphone Case", ["headphone", "earbuds", "buds"]),
    ("Spigen Ultra Hybrid Phone Case", ["galaxy", "oneplus", "smartphone"]),
    ("Spigen Rugged Armor Case for Apple Watch", ["apple watch"]),
    ("Xbox Series X/S Play and Charge Kit", ["xbox"]),
    ("Sony PS5 DualSense Charging Station", ["dualsense", "playstation 5", "ps5"]),
]

def _find_accessory(main_product: dict, conn):
    haystack = f"{main_product['name']} {main_product.get('description') or ''}".lower()
    for accessory_name, keywords in ACCESSORY_PAIRINGS:
        if main_product["name"] == accessory_name:
            continue
        if any(k in haystack for k in keywords):
            row = conn.execute(
                "SELECT * FROM products WHERE name = ? AND agent_enabled=1",
                (accessory_name,)
            ).fetchone()
            if row:
                return row
    return None

def propose_bundle(main_product: dict, budget: int | None, allow_bundle: bool = True) -> dict:
    """Pure function: given a chosen product, return a fresh offer dict.
    Never touches the database for anything but the accessory lookup, and
    never mutates any object passed in — the caller is responsible for
    persisting the result as a new offer version."""
    if not allow_bundle:
        return {
            "type": "SINGLE",
            "items": [{"product_id": main_product["id"], "name": main_product["name"], "price": main_product["price"]}],
            "original_total": main_product["price"],
            "final_amount": main_product["price"],
        }

    remaining_budget = (budget or 0) - main_product["price"]
    conn = get_conn()
    accessory = _find_accessory(main_product, conn)
    conn.close()

    if accessory and accessory["price"] <= remaining_budget + 200:
        original_total = main_product["price"] + accessory["price"]
        bundle_price = int(original_total * 0.96)
        return {
            "type": "BUNDLE",
            "items": [
                {"product_id": main_product["id"], "name": main_product["name"], "price": main_product["price"]},
                {"product_id": accessory["id"], "name": accessory["name"], "price": accessory["price"]},
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

def apply_discount_request(offer: dict, requested_discount: int) -> dict:
    """Returns a NEW offer dict — never mutates the one passed in, so the
    caller can persist it as a new, separate offer version."""
    requested_discount = max(int(requested_discount), 0)  # re-validated here too, not just at the HTTP boundary
    max_allowed = int(offer["original_total"] * MAX_DISCOUNT_PCT / 100)
    granted = min(requested_discount, max_allowed)
    return {
        "type": offer["type"],
        "items": offer["items"],
        "original_total": offer["original_total"],
        "final_amount": offer["original_total"] - granted,
        "discount_applied": granted,
        "discount_capped": granted < requested_discount,
    }
