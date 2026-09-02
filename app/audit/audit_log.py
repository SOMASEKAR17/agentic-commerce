import hashlib, json, time, uuid
from app.db import get_conn

def _hash_entry(entry: dict) -> str:
    payload = json.dumps(entry, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def log_event(actor: str, action: str, amount: int | None,
              decision_reason: str, agent_explanation: str) -> dict:
    conn = get_conn()
    last = conn.execute(
        "SELECT hash FROM audit_log ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    previous_hash = last["hash"] if last else "GENESIS"

    entry = {
        "event_id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor,
        "action": action,
        "amount": amount,
        "decision_reason": decision_reason,
        "agent_explanation": agent_explanation,
        "previous_hash": previous_hash,
    }
    entry["hash"] = _hash_entry(entry)

    conn.execute(
        "INSERT INTO audit_log (event_id, timestamp, actor, action, amount, "
        "decision_reason, agent_explanation, previous_hash, hash) VALUES (?,?,?,?,?,?,?,?,?)",
        tuple(entry.values()),
    )
    conn.commit()
    conn.close()
    return entry

def get_timeline():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY timestamp ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def verify_chain() -> bool:
    """Recompute each entry's hash from its own fields and confirm the chain links."""
    timeline = get_timeline()
    expected_prev = "GENESIS"
    for entry in timeline:
        check = {k: v for k, v in entry.items() if k != "hash"}
        if _hash_entry(check) != entry["hash"]:
            return False
        if entry["previous_hash"] != expected_prev:
            return False
        expected_prev = entry["hash"]
    return True