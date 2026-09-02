import uuid
from app.db import get_conn, init_db

PRODUCTS = [
    ("Sony WH-CH520 Wireless Headphones", "Wireless, noise isolation, 50h battery", 4500, 4.5, 3200),
    ("boAt Rockerz 450", "Wireless, bass boost, 15h battery", 1800, 4.2, 9800),
    ("JBL Tune 510BT", "Wireless, lightweight, 40h battery", 2200, 4.4, 5600),
    ("Sennheiser HD 350BT", "Wireless, ANC, 30h battery", 4900, 4.6, 1200),
    ("Protective Headphone Case", "Hard shell carrying case", 400, 4.1, 500),
    ("Boult Audio ProBass Curve", "Wireless neckband, ANC", 1500, 4.0, 4400),
]

def seed():
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM products")
    for name, desc, price, rating, reviews in PRODUCTS:
        conn.execute(
            "INSERT INTO products (id, name, description, price, rating, reviews, stock, agent_enabled) VALUES (?,?,?,?,?,?,?,1)",
            (str(uuid.uuid4())[:8], name, desc, price, rating, reviews, 50),
        )
    conn.commit()
    conn.close()
    print("Catalog seeded.")

if __name__ == "__main__":
    seed()