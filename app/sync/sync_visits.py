from app.database.db import SessionLocal
from app.models.visit import Visit
from app.firebase.firebase_client import db as firebase_db


def sync_visits():
    db = SessionLocal()

    unsynced = db.query(Visit).filter(Visit.synced == False).all()

    for visit in unsynced:
        firebase_db.collection("visits").document(visit.visit_id).set({
            "health_id": visit.health_id,
            "facility_name": visit.facility_name,
            "district": visit.district,
            "state": visit.state,
            "visit_type": visit.visit_type,
            "chief_complaint": visit.chief_complaint,
            "created_at": visit.created_at.isoformat()
        })

        visit.synced = True

    db.commit()
    db.close()

    return len(unsynced)
