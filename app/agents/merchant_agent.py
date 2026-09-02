from app.db import get_conn
from app.agents.growth_engine import propose_bundle

def search_and_rank(intent: dict, top_n: int = 3):
    conn = get_conn()
    keyword = (intent.get("product") or "").strip().lower()
    keyword_singular = keyword[:-1] if keyword.endswith("s") else keyword

    query = "SELECT * FROM products WHERE agent_enabled = 1 AND stock > 0"
    params = []
    if keyword:
        query += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)"
        params += [f"%{keyword_singular}%", f"%{keyword_singular}%"]
    if intent.get("budget"):
        query += " AND price <= ?"
        params.append(intent["budget"])
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        return [], None

    scored = []
    for r in rows:
        budget = intent.get("budget")
        
        if budget:
            budget_score = 1 - abs(r["price"] - (budget * 0.7)) / budget
            budget_score = max(budget_score, 0)
        else:
            budget_score = 0.5
        rating = r["rating"] or 0
        reviews = r["reviews"] or 0
        
        score = 0.4 * budget_score + 0.3 * (rating / 5) + 0.3 * min(reviews / 5000, 1)
        scored.append((score, dict(r)))

    scored.sort(key=lambda x: -x[0])
    top = [p for _, p in scored[:top_n]]

    offer = propose_bundle(top[0], intent) if top else None
    return top, offer