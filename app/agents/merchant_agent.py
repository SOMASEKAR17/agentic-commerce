from app.db import get_conn

def search_and_rank(intent: dict, top_n: int = 3):
    """
    Deterministic ranking. Previously only scored budget-fit, rating, and
    review count — stated preferences (wireless, noise_cancellation) were
    extracted by the buyer agent but silently dropped here. Now they're
    real scoring inputs, matched against each product's description text
    since the catalog has no structured attribute columns.
    """
    top_n = max(1, min(int(top_n or 3), 5))  # validated range: 1-5, never trust an unbounded client value

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

    budget = intent.get("budget")
    wants_wireless = intent.get("wireless")
    wants_nc = intent.get("noise_cancellation")

    scored = []
    for r in rows:
        if budget:
            budget_score = max(1 - abs(r["price"] - (budget * 0.7)) / budget, 0)
        else:
            budget_score = 0.5

        rating = r["rating"] or 0
        reviews = r["reviews"] or 0
        text = f"{r['name']} {r['description'] or ''}".lower()

        preference_score = 0.5  # neutral baseline when no preference stated
        preference_signals = 0
        if wants_wireless is not None:
            preference_signals += 1
            matches = "wireless" in text
            preference_score += 0.5 if (matches == bool(wants_wireless)) else -0.3
        if wants_nc is not None:
            preference_signals += 1
            matches = any(k in text for k in ("noise cancel", "anc", "noise isolation"))
            preference_score += 0.5 if (matches == bool(wants_nc)) else -0.3
        if preference_signals:
            preference_score = max(min(preference_score, 1.0), 0.0)
        else:
            preference_score = 0.5

        score = 0.35 * budget_score + 0.2 * (rating / 5) + 0.15 * min(reviews / 5000, 1) + 0.3 * preference_score
        scored.append((score, dict(r)))

    scored.sort(key=lambda x: -x[0])
    top = [p for _, p in scored[:top_n]]
    return top, None  # bundle/offer creation now happens in the MCP propose_bundle tool, not here
