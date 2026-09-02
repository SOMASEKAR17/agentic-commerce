import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        agent_enabled INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS agreements (
        agreement_id TEXT PRIMARY KEY,
        buyer_id TEXT,
        merchant_id TEXT,
        items TEXT,
        final_amount INTEGER,
        currency TEXT DEFAULT 'INR',
        status TEXT DEFAULT 'PENDING',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        event_id TEXT PRIMARY KEY,
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
    conn.commit()
    conn.close()