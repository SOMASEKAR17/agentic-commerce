from app.db import get_conn
from app.agents.growth_engine import propose_bundle

def search_and_rank(intent: dict, top_n: int = 3):
    conn = get_conn()
    query = "SELECT * FROM products WHERE agent_enabled = 1 AND stock > 0"
    params = []
    if intent.get("budget"):
        query += " AND price <= ?"
        params.append(intent["budget"])
    rows = conn.execute(query, params).fetchall()
    conn.close()

    scored = []
    for r in rows:
        budget_score = max(1 - (r["price"] / intent["budget"]), 0) if intent.get("budget") else 0.5
        score = 0.4 * budget_score + 0.3 * (r["rating"] / 5) + 0.3 * min(r["reviews"] / 5000, 1)
        scored.append((score, dict(r)))
    scored.sort(key=lambda x: -x[0])
    top = [p for _, p in scored[:top_n]]

    offer = propose_bundle(top[0], intent) if top else None
    return top, offer