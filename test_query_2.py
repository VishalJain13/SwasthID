from app.database.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("--- Raw SQL Test ---")
try:
    result = db.execute(text("SELECT id, created_at, synced FROM visits LIMIT 5"))
    rows = result.fetchall()
    print(f"Raw SQL fetched {len(rows)} rows.")
    for row in rows:
        print(f"Row: {row}")
except Exception as e:
    print(f"Raw SQL Failed: {e}")

print("\n--- ORM Test (No Order) ---")
from app.models.visit import Visit
try:
    visits = db.query(Visit).limit(5).all()
    print(f"ORM fetched {len(visits)} visits.")
except Exception as e:
    print(f"ORM Failed: {e}")
