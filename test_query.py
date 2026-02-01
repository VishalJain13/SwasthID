from app.database.db import SessionLocal
from app.models.visit import Visit
from sqlalchemy import text

db = SessionLocal()
health_id = "988a4734-2edc-4ef4-95ae-e7917bc708ab"

try:
    print("Attempting to query Visits...")
    visits = db.query(Visit).filter(Visit.health_id == health_id).order_by(Visit.created_at.desc()).all()
    print(f"Query successful. Found {len(visits)} visits.")
    for v in visits:
        print(f"Visit: {v.visit_id}, Created: {v.created_at}")
except Exception as e:
    print(f"Query FAILED: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
