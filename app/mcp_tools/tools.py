import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP
from app.db import get_conn
from app.policy.policy_engine import authorize
from mcp.server.fastmcp import FastMCP
from app.db import get_conn
from app.policy.policy_engine import authorize

mcp = FastMCP("razorpay-commerce-agent")

def _catalog_lookup(product_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

@mcp.tool()
def search_agent_catalog(keyword: str = "", max_price: int | None = None) -> list[dict]:
    """Search the merchant's agent-enabled product catalog by keyword and max price."""
    conn = get_conn()
    query = "SELECT * FROM products WHERE agent_enabled = 1 AND stock > 0"
    params = []
    if keyword:
        query += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)"
        params += [f"%{keyword.lower()}%", f"%{keyword.lower()}%"]
    if max_price:
        query += " AND price <= ?"
        params.append(max_price)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@mcp.tool()
def get_product_details(product_id: str) -> dict | None:
    """Fetch full details for one product by id."""
    return _catalog_lookup(product_id)

@mcp.tool()
def create_order(session_id: str, offer: dict, merchant_id: str = "merchant_demo") -> dict:
    """Authorize and create an order for an accepted offer. Refuses if policy fails."""
    decision = authorize(offer, session_id, merchant_id, catalog_lookup=_catalog_lookup)
    if decision["status"] != "APPROVED":
        return {"status": decision["status"], "reason": decision["agent_explanation"]}
    return {"status": "ORDER_CREATED", "amount": offer["final_amount"]}
    # create_payment / get_payment_status are added Day 3 once Razorpay is wired in

if __name__ == "__main__":
    mcp.run()