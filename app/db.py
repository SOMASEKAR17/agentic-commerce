import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        rating REAL DEFAULT 4.0,
        reviews INTEGER DEFAULT 0,
        stock INTEGER DEFAULT 100,
        agent_enabled INTEGER DEFAULT 1,
        merchant_id TEXT DEFAULT 'merchant_demo'
    );

    -- Versioned offers: every negotiation round creates a NEW row rather than
    -- mutating an existing one. `supersedes` points at the previous version.
    CREATE TABLE IF NOT EXISTS offers (
        offer_id TEXT PRIMARY KEY,
        session_id TEXT,
        merchant_id TEXT,
        items TEXT NOT NULL,
        original_total INTEGER NOT NULL,
        final_amount INTEGER NOT NULL,
        version INTEGER DEFAULT 1,
        supersedes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    -- The canonical, immutable execution record. Once created, items/amount/
    -- merchant never change — policy and payment always read from here, never
    -- from a network-supplied dict.
    CREATE TABLE IF NOT EXISTS agreements (
        agreement_id TEXT PRIMARY KEY,
        offer_id TEXT,
        buyer_id TEXT,
        merchant_id TEXT,
        items TEXT NOT NULL,
        final_amount INTEGER NOT NULL,
        currency TEXT DEFAULT 'INR',
        status TEXT DEFAULT 'ACCEPTED',
        razorpay_payment_link_id TEXT,
        razorpay_payment_link_url TEXT,
        trace_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    -- Atomic idempotency: the row is INSERTed before any Razorpay call is
    -- made. A UNIQUE constraint on agreement_id means only one process can
    -- ever win the insert; the loser reads back this row instead of calling
    -- Razorpay a second time.
    CREATE TABLE IF NOT EXISTS payment_attempts (
        agreement_id TEXT PRIMARY KEY,
        razorpay_payment_link_id TEXT,
        razorpay_payment_link_url TEXT,
        status TEXT DEFAULT 'CREATING',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS buyer_policies (
        buyer_id TEXT PRIMARY KEY,
        approval_mode TEXT DEFAULT 'ASK_ALWAYS',
        max_auto_purchase INTEGER DEFAULT 500,
        daily_limit INTEGER DEFAULT 8000
    );

    -- Persisted usage counters, keyed per buyer per day, so a restart doesn't
    -- reset spend/tool/risk tracking mid-session.
    CREATE TABLE IF NOT EXISTS policy_usage (
        buyer_id TEXT NOT NULL,
        usage_date TEXT NOT NULL,
        tool_calls INTEGER DEFAULT 0,
        daily_spend INTEGER DEFAULT 0,
        cumulative_risk REAL DEFAULT 0,
        PRIMARY KEY (buyer_id, usage_date)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT,
        trace_id TEXT,
        agreement_id TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        actor TEXT,
        action TEXT,
        amount INTEGER,
        decision_reason TEXT,
        agent_explanation TEXT,
        previous_hash TEXT,
        hash TEXT
    );
    """)
    for stmt in [
        "ALTER TABLE products ADD COLUMN merchant_id TEXT DEFAULT 'merchant_demo'",
    ]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
