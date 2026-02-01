import requests
import uuid

BASE_URL = "http://127.0.0.1:8000"
HEALTH_ID = "2a696da2-49f9-4da5-9f6d-ee04ef61fc19" # From logs

def simulate():
    print(f"Simulating Infection for ID: {HEALTH_ID}")

    # 1. Create Visit
    print("1. Creating Visit...")
    visit_payload = {
        "health_id": HEALTH_ID,
        "facility_name": "General Hospital Ernakulam",
        "district": "Ernakulam",
        "state": "Kerala",
        "visit_type": "OPD",
        "chief_complaint": "High Fever and Cough",
        "symptoms": "Fever, Cough, Loss of taste",
        "temperature_c": 39.5,
        "bp": "120/80",
        "spo2": 95
    }
    
    try:
        r = requests.post(f"{BASE_URL}/visits/create", params=visit_payload)
        data = r.json()
        visit_id = data.get("visit_id")
        print(f"   Visit Created: {visit_id}")
    except Exception as e:
        print(f"   Failed to create visit: {e}")
        return

    # 2. Add Infectious Record
    print("2. Adding Infectious Medical Record...")
    record_payload = {
        "visit_id": visit_id,
        "health_id": HEALTH_ID,
        "symptoms": "Fever, Cough",
        "diagnosis": "Viral Fever (Suspected Covid)",
        "severity": "MODERATE",
        "suspected_disease": "Covid-19",
        "is_infectious": True, # <--- THIS TRIGGER THE RED SHIELD
        "temperature": 39.5,
        "notes": "Patient advised strict home isolation for 14 days."
    }

    r = requests.post(f"{BASE_URL}/records/create", params=record_payload)
    print(f"   Record Created: {r.json()}")
    print("\nSUCCESS! The backend now marks this user as AT_RISK.")
    print("Please Pull-to-Refresh the Flutter App to see the Red Shield.")

if __name__ == "__main__":
    simulate()
