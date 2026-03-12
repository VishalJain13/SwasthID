import os
import random
import uuid
import re
import cv2
import pytesseract
import qrcode
from dotenv import load_dotenv

# -----------------------
# ENV SETUP (MUST BE FIRST)
# -----------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
print(f"Loading env from: {ENV_PATH}")
load_dotenv(dotenv_path=ENV_PATH)

print("AUTH TOKEN:", os.getenv("MESSAGE_CENTRAL_AUTH_TOKEN"))
print("CUSTOMER ID:", os.getenv("MESSAGE_CENTRAL_CUSTOMER_ID"))

# FastAPI
from fastapi import FastAPI, HTTPException, File, UploadFile, Depends, Form
from fastapi.middleware.cors import CORSMiddleware

# Database
from sqlalchemy.orm import Session
from app.database.db import SessionLocal, engine
from app.database.base import Base

# Models
from app.models.otp import send_otp, verify_otp
from app.models.profile import Profile
from app.models.health_id import HealthID
from app.models.visit import Visit
from app.models.medical_record import MedicalRecord
from app.models.medical_document import MedicalDocument
from app.models.disease_surveillance import DiseaseSurveillance
from app.rag import swasth_ai_answer

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ Gemini API key not found. Disabling AI features.") 

import google.generativeai as genai
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-flash-latest")
    except Exception as e:
        print(f"⚠️ Failed to configure Gemini: {e}")
        GEMINI_API_KEY = None

# -----------------------
# OCR CONFIG
# -----------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# -----------------------
# APP INIT
# -----------------------
app = FastAPI(title="Swasth ID API")

# -----------------------
# CORS CONFIG (CRITICAL FOR WEB)
# -----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (Flutter Web, Mobile, etc)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

# Ensure directories exist
os.makedirs("qr_codes", exist_ok=True)
os.makedirs("prescriptions", exist_ok=True)
os.makedirs("id_proofs", exist_ok=True)
os.makedirs("medical_records", exist_ok=True)

# Mount Static Directories
app.mount("/qr_codes", StaticFiles(directory="qr_codes"), name="qr_codes")
app.mount("/prescriptions", StaticFiles(directory="prescriptions"), name="prescriptions")
app.mount("/id_proofs", StaticFiles(directory="id_proofs"), name="id_proofs")
app.mount("/medical_records", StaticFiles(directory="medical_records"), name="medical_records")

from app.models.chat import ChatSession, ChatMessage

# -----------------------
# CREATE TABLES
# -----------------------
Base.metadata.create_all(bind=engine)

# -----------------------
# DATABASE DEPENDENCY
# -----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------
# HELPER: Verhoeff Validation
# -----------------------
d_table = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0]
]

p_table = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8]
]

def verhoeff_validate(number: str) -> bool:
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = d_table[c][p_table[i % 8][int(digit)]]
    return c == 0

# -----------------------
# KNOWLEDGE BASE
# -----------------------
KEYWORD_MAP = {
    "disease": ["fever", "typhoid", "dengue", "malaria", "covid", "infection", "viral", "bacterial", "illness"],
    "symptom_history": ["history", "previous", "past", "earlier", "symptom", "complaint", "temperature"],
    "prevention": ["precaution", "prevent", "avoid", "safety", "hygiene", "clean", "protection"],
    "home_remedy": ["home remedy", "natural", "diet", "food", "rest", "hydration"],
    "medical_help": ["doctor", "hospital", "clinic", "phc", "emergency"],
    "vaccination": ["vaccine", "vaccination", "immunization"],
    "fever": ["fever", "temperature", "high temperature"],
    "cough": ["cough", "cold", "throat"],
    "pain": ["pain", "headache", "body pain"],
    "stomach": ["stomach", "diarrhea", "vomiting"],
    "infection": ["infection", "typhoid", "malaria", "dengue"],
    "nutrition": ["diet", "food", "nutrition"],
    "pregnancy": ["pregnant", "pregnancy"]
}

@app.post("/auth/send-otp")
def api_send_otp(mobile: str):
    response = send_otp(mobile)

    if not response["success"]:
        raise HTTPException(status_code=400, detail=response.get("message", "OTP send failed"))

    return {
        "message": "OTP sent successfully",
        "verification_id": response["verification_id"]
    }


@app.post("/auth/verify-otp")
def api_verify_otp(
    otp: str,
    verification_id: str,
    mobile: str,  # Added mobile for user lookup
    db: Session = Depends(get_db) # Added DB dependency
):
    mobile = mobile.strip() # Ensure no trailing spaces
    print(f"DEBUG: Verifying user status for mobile: '{mobile}'")
    response = verify_otp("", otp, verification_id)

    if not response.get("success"):
        raise HTTPException(status_code=400, detail=response.get("message"))

    # Smart Login Logic: Check if user exists
    is_existing_user = False
    health_id = None
    
    # Check Profile
    profile = db.query(Profile).filter(Profile.mobile == mobile).first()
    print(f"DEBUG: Profile Check for {mobile}: {'Found' if profile else 'Not Found'}")
    
    # Check Health ID
    hid_record = db.query(HealthID).filter(HealthID.mobile == mobile).first()
    print(f"DEBUG: HealthID Check for {mobile}: {'Found' if hid_record else 'Not Found'}")
    
    if profile and hid_record:
        is_existing_user = True
        health_id = hid_record.health_id
        print(f"DEBUG: User {mobile} is EXISTING (Redirect to Home)")
    else:
        print(f"DEBUG: User {mobile} is NEW (Redirect to Registration)")

    return {
        "message": "OTP verified successfully",
        "status": "verified",
        "is_existing_user": is_existing_user,
        "health_id": health_id
    }






# -------------------------------
# PAGE 1 – PERSONAL DETAILS
# -------------------------------

@app.post("/personal-details")
def personal_details(
    mobile: str,
    name: str,
    age: int,
    gender: str,
    address: str,
    city: str,
    state: str,
    pincode: str,
    db: Session = Depends(get_db)
):


    profile = Profile(
        mobile=mobile,
        name=name,
        age=age,
        gender=gender,
        address=address,
        city=city,
        state=state,
        pincode=pincode
    )

    # UPSERT LOGIC
    existing = db.query(Profile).filter(Profile.mobile == mobile).first()
    if existing:
        existing.name = name
        existing.age = age
        existing.gender = gender
        existing.address = address
        existing.city = city
        existing.state = state
        existing.pincode = pincode
    else:
        db.add(profile)

    db.commit()

    return {"message": "Personal details saved. Go to Medical Details"}

# -------------------------------
# PAGE 2 – MEDICAL DETAILS
# -------------------------------

@app.post("/medical-details")
def medical_details(
    mobile: str,
    height_cm: float,
    weight_kg: float,
    blood_group: str,
    vaccination_status: str,
    allergies: str,
    db: Session = Depends(get_db)
):

    profile = db.query(Profile).filter(Profile.mobile == mobile).first()

    if not profile:
        return {"error": "Personal details not found"}

    bmi = round(weight_kg / ((height_cm / 100) ** 2), 2)

    profile.height_cm = height_cm
    profile.weight_kg = weight_kg
    profile.bmi = bmi
    profile.blood_group = blood_group
    profile.vaccination_status = vaccination_status
    profile.allergies = allergies

    db.commit()

    return {"message": "Medical details saved. Go to ID Verification", "bmi": bmi}

# -------------------------------
# PAGE 3 – ID VERIFICATION + QR
# -------------------------------

@app.post("/id-verification")
def id_verification(
    mobile: str,
    id_type: str,
    id_number: str,
    db: Session = Depends(get_db)
):


    # Step 1: check profile completed
    profile = db.query(Profile).filter(Profile.mobile == mobile).first()
    if not profile:
        return {"error": "Complete all forms first"}

    # Step 2: check if Health ID already exists
    existing = db.query(HealthID).filter(HealthID.mobile == mobile).first()
    if existing:
        return {
            "message": "Health ID already generated",
            "health_id": existing.health_id,
            "qr_generated": True
        }

    # Step 3: generate new Health ID
    health_uid = str(uuid.uuid4())

    record = HealthID(
        mobile=mobile,
        id_type=id_type,
        id_number=id_number,
        health_id=health_uid
    )

    db.add(record)
    db.commit()

    import os
    os.makedirs("qr_codes", exist_ok=True)

    img = qrcode.make(health_uid)
    img.save(f"qr_codes/{health_uid}.png")

    return {
        "message": "Registration complete",
        "health_id": health_uid,
        "qr_generated": True
    }

@app.get("/view-profile/{health_id}")
def view_profile(health_id: str, db: Session = Depends(get_db)):

    record = db.query(HealthID).filter(
        HealthID.health_id == health_id
    ).first()

    if not record:
        return {"error": "Invalid Health ID"}

    profile = db.query(Profile).filter(
        Profile.mobile == record.mobile
    ).first()

    if not profile:
        return {"error": "Profile not found"}

    return {
        "health_id": health_id,
        "personal_details": {
            "name": profile.name,
            "age": profile.age,
            "gender": profile.gender,
            "address": profile.address,
            "city": profile.city,
            "state": profile.state,
            "pincode": profile.pincode
        },
        "medical_details": {
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "bmi": profile.bmi,
            "blood_group": profile.blood_group,
            "vaccination_status": profile.vaccination_status,
            "allergies": profile.allergies
        }
    }

@app.get("/profile/details")
def get_profile_by_mobile(mobile: str, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.mobile == mobile).first()
    
    if not profile:
        return {"error": "Profile not found"}

    hid_record = db.query(HealthID).filter(HealthID.mobile == mobile).first()
    health_id = hid_record.health_id if hid_record else None

    return {
        "health_id": health_id,
        "personal_details": {
            "name": profile.name,
            "age": profile.age,
            "gender": profile.gender,
            "address": profile.address,
            "city": profile.city,
            "state": profile.state,
            "pincode": profile.pincode,
            "mobile": profile.mobile
        },
        "medical_details": {
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "bmi": profile.bmi,
            "blood_group": profile.blood_group,
            "vaccination_status": profile.vaccination_status,
            "allergies": profile.allergies
        },
        "emergency_contacts": {
            "name": profile.emergency_contact_name,
            "phone": profile.emergency_contact_phone,
            "relation": profile.emergency_contact_relation
        },
        "insurance_details": {
            "provider": profile.insurance_provider,
            "policy_no": profile.insurance_policy_no,
            "valid_till": profile.insurance_valid_till,
            "tpa": profile.insurance_tpa
        }
    }

@app.post("/update-emergency-contacts")
def update_emergency_contacts(
    mobile: str,
    name: str,
    phone: str,
    relation: str,
    db: Session = Depends(get_db)
):
    profile = db.query(Profile).filter(Profile.mobile == mobile).first()
    if not profile:
        return {"error": "Profile not found"}

    profile.emergency_contact_name = name
    profile.emergency_contact_phone = phone
    profile.emergency_contact_relation = relation
    db.commit()

    return {"message": "Emergency contacts updated successfully", "success": True}

@app.post("/emergency/trace")
def log_emergency_trace(
    mobile: str,
    action_type: str, # "sos_call" or "nearby_hospitals"
    location_lat: float = None,
    location_lng: float = None,
    db: Session = Depends(get_db)
):
    """
    Logs emergency actions for audit and safety analytics.
    Returns success status.
    """
    print(f"URGENT: Emergency Action '{action_type}' triggered by {mobile} at {location_lat},{location_lng}")
    # In a real system, this would write to an AuditLog table or trigger a notification
    
    return {
        "success": True, 
        "message": f"Emergency action '{action_type}' logged.", 
        "timestamp": date.today()
    }

@app.post("/update-insurance-details")
def update_insurance_details(
    mobile: str,
    provider: str,
    policy_no: str,
    valid_till: str,
    tpa: str,
    db: Session = Depends(get_db)
):
    profile = db.query(Profile).filter(Profile.mobile == mobile).first()
    if not profile:
        return {"error": "Profile not found"}

    profile.insurance_provider = provider
    profile.insurance_policy_no = policy_no
    profile.insurance_valid_till = valid_till
    profile.insurance_tpa = tpa
    db.commit()

    return {"message": "Insurance details updated successfully", "success": True}

@app.post("/upload-id-proof")
def upload_id_proof(
    mobile: str,
    file: UploadFile = File(...)
):
    # create folder if not exists
    os.makedirs("id_proofs", exist_ok=True)

    # generate unique filename
    file_extension = file.filename.split(".")[-1]
    filename = f"{mobile}_{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join("id_proofs", filename)

    # save file
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return {
        "message": "ID proof uploaded successfully",
        "file_path": file_path
    }

@app.post("/ocr-read-id")
def ocr_read_id(file_path: str):
    import os
    import cv2
    import pytesseract

    # CLEAN the file path (remove quotes & spaces)
    file_path = file_path.strip().replace('"', '').replace("'", "")

    # Convert Windows backslashes safely
    file_path = file_path.replace("\\", "/")

    # Check file exists
    if not os.path.exists(file_path):
        return {
            "error": "Image not found",
            "received_path": file_path
        }

    # Read image
    image = cv2.imread(file_path)

    if image is None:
        return {"error": "Unable to read image"}

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # OCR
    extracted_text = pytesseract.image_to_string(gray)

    return {
        "message": "OCR completed",
        "extracted_text": extracted_text
    }

@app.post("/extract-id-number")
def extract_id_number(ocr_text: str):
    # Normalize OCR text
    cleaned_text = ocr_text.replace("\n", " ")
    cleaned_text = re.sub(r"\s+", " ", cleaned_text)

    # Find all 12-digit looking numbers
    candidates = re.findall(r"\b\d{4}\s?\d{4}\s?\d{4}\b", cleaned_text)

    results = []

    for candidate in candidates:
        aadhaar = candidate.replace(" ", "")

        if len(aadhaar) != 12:
            continue

        is_valid = verhoeff_validate(aadhaar)

        results.append({
            "id_number": aadhaar,
            "checksum_valid": is_valid
        })

    if not results:
        return {
            "id_detected": False,
            "message": "No Aadhaar-like numbers found"
        }

    # If any valid Aadhaar found, return it
    for r in results:
        if r["checksum_valid"]:
            return {
                "id_detected": True,
                "id_type": "Aadhaar",
                "id_number": r["id_number"],
                "validation": "Checksum verified"
            }

    # Otherwise return suggestions for manual confirmation
    return {
        "id_detected": False,
        "message": "Aadhaar candidates found but checksum failed",
        "possible_ids": results,
        "note": "OCR noise suspected. Manual confirmation required."
    }

@app.post("/review-ocr")
def review_ocr(file_path: str):
    """
    Runs OCR + Aadhaar extraction and returns suggestions for confirmation
    """
    import os
    import cv2
    import pytesseract

    # clean path
    file_path = file_path.strip().replace('"', '').replace("'", "").replace("\\", "/")

    if not os.path.exists(file_path):
        return {"error": "Image not found"}

    image = cv2.imread(file_path)
    if image is None:
        return {"error": "Unable to read image"}

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ocr_text = pytesseract.image_to_string(gray)

    # reuse existing extraction logic
    cleaned_text = ocr_text.replace("\n", " ")
    cleaned_text = re.sub(r"\s+", " ", cleaned_text)

    candidates = re.findall(r"\b\d{4}\s?\d{4}\s?\d{4}\b", cleaned_text)

    suggestions = []
    for c in candidates:
        num = c.replace(" ", "")
        if len(num) == 12:
            suggestions.append({
                "id_number": num,
                "checksum_valid": verhoeff_validate(num)
            })

    return {
        "ocr_text": ocr_text,
        "aadhaar_suggestions": suggestions,
        "instruction": "Confirm or edit Aadhaar number before final verification"
    }

@app.post("/confirm-id-verification")
def confirm_id_verification(
    mobile: str,
    id_type: str,
    id_number: str,
    db: Session = Depends(get_db)
):


    # basic length check
    if id_type.lower() == "aadhaar" and len(id_number) != 12:
        return {"error": "Invalid Aadhaar length"}

    # optional checksum check (warn, don’t block)
    checksum_ok = verhoeff_validate(id_number) if id_type.lower() == "aadhaar" else True

    # reuse existing ID verification logic
    existing = db.query(HealthID).filter(HealthID.mobile == mobile).first()
    if existing:
        return {
            "message": "Health ID already exists",
            "health_id": existing.health_id
        }

    health_uid = str(uuid.uuid4())
    record = HealthID(
        mobile=mobile,
        id_type=id_type,
        id_number=id_number,
        health_id=health_uid
    )

    db.add(record)
    db.commit()
    
    print(f"DEBUG: Created HealthID for {mobile}: {health_uid}") # LOGGING ADDED

    import os
    os.makedirs("qr_codes", exist_ok=True)
    img = qrcode.make(health_uid)
    img.save(f"qr_codes/{health_uid}.png")

    return {
        "message": "ID verified and registration completed",
        "health_id": health_uid,
        "qr_generated": True,
        "checksum_valid": checksum_ok
    }


@app.post("/visits/create")
def create_visit(
    health_id: str,
    facility_name: str,
    district: str,
    state: str,
    visit_type: str,
    chief_complaint: str,
    symptoms: str,

    temperature_c: float = None,
    bp: str = None,
    spo2: int = None,

    vaccine_given: bool = False,
    vaccine_name: str = None,
    next_dose_due_date: str = None,

    referred: bool = False,
    referred_to: str = None,
    referral_reason: str = None,

    doctor_name: str = None,
    specialization: str = None,
    attachments: str = None, # JSON list of URLs or filenames

    db: Session = Depends(get_db)
):
    visit_uid = str(uuid.uuid4())

    visit = Visit(
        visit_id=visit_uid,
        health_id=health_id,
        facility_name=facility_name,
        district=district,
        state=state,
        visit_type=visit_type,
        chief_complaint=chief_complaint,
        symptoms=symptoms,
        temperature_c=temperature_c,
        bp=bp,
        spo2=spo2,
        vaccine_given=vaccine_given,
        vaccine_name=vaccine_name,
        next_dose_due_date=next_dose_due_date,
        referred=referred,
        referred_to=referred_to,
        referral_reason=referral_reason,
        doctor_name=doctor_name,
        specialization=specialization,
        attachments=attachments,
        synced=False
    )

    db.add(visit)
    db.commit()
    db.refresh(visit)

    return {
        "message": "Visit recorded successfully",
        "visit_id": visit_uid,
        "synced": False
    }


@app.post("/visits/update")
def update_visit(
    visit_id: str,
    facility_name: str = None,
    district: str = None,
    state: str = None,
    visit_type: str = None,
    chief_complaint: str = None,
    symptoms: str = None,
    temperature_c: float = None,
    bp: str = None,
    spo2: int = None,
    vaccine_given: bool = None,
    vaccine_name: str = None,
    next_dose_due_date: str = None,
    referred: bool = None,
    referred_to: str = None,
    referral_reason: str = None,
    doctor_name: str = None,
    specialization: str = None,
    db: Session = Depends(get_db)
):
    visit = db.query(Visit).filter(Visit.visit_id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if facility_name: visit.facility_name = facility_name
    if district: visit.district = district
    if state: visit.state = state
    if visit_type: visit.visit_type = visit_type
    if chief_complaint: visit.chief_complaint = chief_complaint
    if symptoms: visit.symptoms = symptoms
    if temperature_c is not None: visit.temperature_c = temperature_c
    if bp: visit.bp = bp
    if spo2 is not None: visit.spo2 = spo2
    if vaccine_given is not None: visit.vaccine_given = vaccine_given
    if vaccine_name: visit.vaccine_name = vaccine_name
    if next_dose_due_date: visit.next_dose_due_date = next_dose_due_date
    if referred is not None: visit.referred = referred
    if referred_to: visit.referred_to = referred_to
    if referral_reason: visit.referral_reason = referral_reason
    if doctor_name: visit.doctor_name = doctor_name
    if specialization: visit.specialization = specialization

    db.commit()
    return {"message": "Visit updated successfully"}


@app.post("/records/create")
def create_medical_record(
    visit_id: str,
    health_id: str,
    symptoms: str,
    diagnosis: str,
    severity: str,
    suspected_disease: str = None,
    is_infectious: bool = False,
    temperature: float = None,
    spo2: int = None,
    notes: str = None,
    db: Session = Depends(get_db)
):
    record_uid = str(uuid.uuid4())

    record = MedicalRecord(
        record_id=record_uid,
        visit_id=visit_id,
        health_id=health_id,
        symptoms=symptoms,
        diagnosis=diagnosis,
        severity=severity,
        suspected_disease=suspected_disease,
        is_infectious=is_infectious,
        temperature=temperature,
        spo2=spo2,
        notes=notes,
        synced=False
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Medical record added successfully",
        "record_id": record_uid,
        "synced": False
    }

from app.models.medical_record import MedicalRecord
from app.models.disease_surveillance import DiseaseSurveillance
from app.models.visit import Visit
from sqlalchemy import func
from datetime import date


@app.post("/surveillance/run")
def run_disease_surveillance(db: Session = Depends(get_db)):
    """
    Aggregates infectious cases and generates surveillance alerts
    """

    # Clear today’s old surveillance data (avoid duplicates)
    db.query(DiseaseSurveillance).filter(
        DiseaseSurveillance.date == date.today()
    ).delete()
    db.commit()

    # Join medical_records with visits
    records = (
        db.query(
            Visit.district,
            Visit.state,
            MedicalRecord.suspected_disease,
            func.count(MedicalRecord.id).label("case_count"),
            func.group_concat(MedicalRecord.severity).label("severities")
        )
        .join(Visit, Visit.visit_id == MedicalRecord.visit_id)
        .filter(MedicalRecord.is_infectious == True)
        .group_by(
            Visit.district,
            Visit.state,
            MedicalRecord.suspected_disease
        )
        .all()
    )

    alerts_created = []

    for r in records:
        # Decide alert level
        if r.case_count >= 8:
            alert = "HIGH"
        elif r.case_count >= 4:
            alert = "MEDIUM"
        else:
            alert = "LOW"

        # Decide severity level
        severities = (r.severities or "").lower()
        if "severe" in r.severities:
            severity = "severe"
        elif "moderate" in r.severities:
            severity = "moderate"
        else:
            severity = "mild"

        alert_row = DiseaseSurveillance(
            district=r.district,
            state=r.state,
            disease_name=r.suspected_disease,
            case_count=r.case_count,
            severity_level=severity,
            alert_level=alert,
            date=date.today()
        )

        db.add(alert_row)

        alerts_created.append({
            "district": r.district,
            "disease": r.suspected_disease,
            "cases": r.case_count,
            "alert": alert
        })

    db.commit()

    return {
        "message": "Disease surveillance run completed",
        "alerts_generated": alerts_created
    }

@app.get("/surveillance/heatmap")
def get_surveillance_heatmap(db: Session = Depends(get_db)):
    """
    Returns district-wise disease data for heatmap visualization
    """

    data = db.query(DiseaseSurveillance).all()

    heatmap = []

    for row in data:
        heatmap.append({
            "district": row.district,
            "state": row.state,
            "disease": row.disease_name,
            "cases": row.case_count,
            "alert_level": row.alert_level,
            "severity": row.severity_level,
            "date": str(row.date)
        })

    return {
        "message": "Heatmap data ready",
        "data": heatmap
    }

from app.models.ocr_document import OCRDocument

@app.post("/ocr/upload")
def upload_ocr_document(
    visit_id: str,
    health_id: str,
    document_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    import os
    import cv2
    import pytesseract

    # Create folder
    os.makedirs("ocr_docs", exist_ok=True)

    # Save file
    ext = file.filename.split(".")[-1]
    doc_uid = str(uuid4())
    file_path = f"ocr_docs/{doc_uid}.{ext}"

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    # OCR
    image = cv2.imread(file_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ocr_text = pytesseract.image_to_string(gray)

    record = OCRDocument(
        document_id=doc_uid,
        visit_id=visit_id,
        health_id=health_id,
        document_type=document_type,
        file_path=file_path,
        ocr_text=ocr_text,
        synced=False
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "OCR document uploaded & processed",
        "document_id": doc_uid,
        "synced": False
    }

from app.sync.sync_visits import sync_visits

@app.post("/sync/visits")
def sync_visits(db: Session = Depends(get_db)):
    unsynced_visits = db.query(Visit).filter(Visit.synced == False).all()

    if not unsynced_visits:
        return {"message": "No offline data to sync"}

    synced_count = 0

    for visit in unsynced_visits:
        firebase_db.collection("visits").document(visit.visit_id).set({
            "visit_id": visit.visit_id,
            "health_id": visit.health_id,
            "facility_name": visit.facility_name,
            "district": visit.district,
            "state": visit.state,
            "visit_type": visit.visit_type,
            "chief_complaint": visit.chief_complaint,
            "symptoms": visit.symptoms,
            "temperature_c": visit.temperature_c,
            "bp": visit.bp,
            "spo2": visit.spo2,
            "vaccine_given": visit.vaccine_given,
            "vaccine_name": visit.vaccine_name,
            "referred": visit.referred,
            "referred_to": visit.referred_to,
            "created_at": str(visit.created_at)
        })

        visit.synced = True
        synced_count += 1

    db.commit()

    return {
        "message": "Sync completed",
        "records_synced": synced_count
    }

@app.get("/explore/disease/{disease_name}")
def explore_disease(disease_name: str):
    disease = DISEASE_DATA.get(disease_name.lower())

    if not disease:
        return {"error": "Disease information not available"}

    return {
        "disease": disease_name,
        "details": disease
    }

@app.get("/chat/sessions")
def get_chat_sessions(health_id: str, db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.health_id == health_id).order_by(ChatSession.created_at.desc()).all()
    return sessions

@app.get("/chat/messages/{session_id}")
def get_chat_messages(session_id: str, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    return messages

@app.post("/chat/session")
def create_chat_session(health_id: str, title: str = "New Chat", db: Session = Depends(get_db)):
    session_uid = str(uuid.uuid4())
    session = ChatSession(id=session_uid, health_id=health_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@app.post("/swasth-ai/ask")
async def swasth_ai(
    question: str = Form(...),
    session_id: str = Form(None),
    health_id: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Detect intents (basic keyword search for now)
    intents = []
    question_lower = question.lower()
    for key, keywords in KEYWORD_MAP.items():
        if any(k in question_lower for k in keywords):
            intents.append(key)
            
    context = ""

    # ----------------------------
    # 1️⃣ DATABASE CONTEXT (Visits)
    # ----------------------------
    if "symptom_history" in intents or "visit_history" in intents:
        visits = (
            db.query(Visit)
            .order_by(Visit.created_at.desc())
            .limit(5)
            .all()
        )

        if visits:
            context += "Recent Visit Records:\n"
            for v in visits:
                context += f"""
Visit Location: {v.facility_name}, {v.district}, {v.state}
Visit Type: {v.visit_type}
Chief Complaint: {v.chief_complaint}
Date: {v.created_at.strftime('%d %b %Y')}
---
"""
    # ----------------------------
    # 2️⃣ GENERAL HEALTH KNOWLEDGE
    # ----------------------------
    # ... (Keep existing context logic) ...
    if any(i in intents for i in ["disease", "prevention", "home_remedy"]):
         context += """
General Health Guidance:
• Maintain hydration
• Eat nutritious food
• Follow hygiene practices
• Avoid self-medication
• Seek medical help if symptoms worsen
---
"""

    # ----------------------------
    # 3️⃣ MEDICAL HELP CONTEXT
    # ----------------------------
    if "medical_help" in intents:
        context += """
Medical Advice:
• Visit nearest Primary Health Centre (PHC)
• Seek emergency care if severe symptoms occur
---
"""
    
    # ----------------------------
    # 4️⃣ IMAGE HANDLING
    # ----------------------------
    image_data = None
    if file:
        image_data = await file.read()
        context += "\n[User has uploaded an image for analysis]\n"

    # ----------------------------
    # 5️⃣ GREETING CHECK
    # ----------------------------
    if question_lower.strip() in ["hi", "hello", "hey", "greetings", "namaste"]:
        answer = "Hello! I am Swasth AI, your personal health assistant. How can I help you today? You can ask me about symptoms, diseases, or upload a medical report for analysis."
        return {
             "assistant": "Swasth AI",
             "answer": answer,
             "session_id": session_id
        }

    # ----------------------------
    # 6️⃣ GEMINI RESPONSE
    # ----------------------------
    # Only call AI if context exists or image is provided (or if we want generic AI response)
    # Improving safety check: Allow general queries but warn if totally unrelated (handled by swasth_ai_answer logic)
    
    answer = swasth_ai_answer(context, question, image_data)

    # ----------------------------
    # 7️⃣ SAVE CHAT HISTORY
    # ----------------------------
    if not session_id and health_id:
        # Create new session if none provided but we have user context
        title = question[:30] + "..." if len(question) > 30 else question
        session_uid = str(uuid.uuid4())
        new_session = ChatSession(id=session_uid, health_id=health_id, title=title)
        db.add(new_session)
        session_id = session_uid
        db.commit()

    if session_id:
        # Save User Message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=question,
            has_image=file is not None
        )
        db.add(user_msg)
        
        # Save AI Response
        ai_msg = ChatMessage(
            session_id=session_id,
            role="ai",
            content=answer
        )
        db.add(ai_msg)
        db.commit()

    return {
        "assistant": "Swasth AI",
        "detected_intents": intents,
        "answer": answer,
        "session_id": session_id
    }


@app.post("/swasth-ai/explain-prescription")
def explain_prescription(
    ocr_text: str,
    db: Session = Depends(get_db)
):
    system_rules = """
You are Swasth AI, a healthcare assistant.

RULES:
1. Explain prescription in SIMPLE language.
2. DO NOT give medicine dosage.
3. DO NOT suggest new medicines.
4. DO NOT make diagnosis.
5. Focus on purpose, general use, and precautions.
6. Encourage consulting doctor if confused.
"""

    context = f"""
Prescription Text:
{ocr_text}

Task:
Explain what this prescription generally means in simple words.
"""

    answer = swasth_ai_answer(system_rules + context, "Explain this prescription")

    return {
        "assistant": "Swasth AI",
        "explanation": answer
    }

from sqlalchemy import func
from app.models.disease_surveillance import DiseaseSurveillance

@app.get("/govt/heatmap/disease")
def disease_heatmap(
    disease_name: str,
    db: Session = Depends(get_db)
):
    """
    Returns district-wise disease case aggregation
    for govt heatmap visualization
    """

    results = (
        db.query(
            DiseaseSurveillance.district,
            func.sum(DiseaseSurveillance.case_count).label("total_cases"),
            DiseaseSurveillance.alert_level
        )
        .filter(DiseaseSurveillance.disease_name.ilike(disease_name))
        .group_by(
            DiseaseSurveillance.district,
            DiseaseSurveillance.alert_level
        )
        .all()
    )

    heatmap_data = []

    for r in results:
        heatmap_data.append({
            "district": r.district,
            "cases": r.total_cases,
            "alert_level": r.alert_level
        })

    return {
        "state": "Kerala",
        "disease": disease_name,
        "heatmap": heatmap_data
    }

from sqlalchemy import func

@app.get("/surveillance/district-summary")
def district_wise_summary(db: Session = Depends(get_db)):
    """
    District-wise aggregation for government dashboard
    """

    results = (
        db.query(
            DiseaseSurveillance.state,
            DiseaseSurveillance.district,
            DiseaseSurveillance.disease_name,
            func.sum(DiseaseSurveillance.case_count).label("total_cases"),
            func.max(DiseaseSurveillance.alert_level).label("alert_level")
        )
        .group_by(
            DiseaseSurveillance.state,
            DiseaseSurveillance.district,
            DiseaseSurveillance.disease_name
        )
        .all()
    )

    summary = []

    for r in results:
        summary.append({
            "state": r.state,
            "district": r.district,
            "disease": r.disease_name,
            "total_cases": r.total_cases,
            "alert_level": r.alert_level
        })

    return {
        "message": "District-wise surveillance summary",
        "data": summary
    }

from datetime import timedelta

@app.get("/surveillance/trends")
def disease_trends(
    disease: str,
    district: str,
    db: Session = Depends(get_db)
):
    """
    Returns last 7 days disease trend for graphs
    """

    start_date = date.today() - timedelta(days=6)

    records = (
        db.query(
            DiseaseSurveillance.date,
            func.sum(DiseaseSurveillance.case_count).label("cases")
        )
        .filter(
            DiseaseSurveillance.disease_name == disease,
            DiseaseSurveillance.district == district,
            DiseaseSurveillance.date >= start_date
        )
        .group_by(DiseaseSurveillance.date)
        .order_by(DiseaseSurveillance.date)
        .all()
    )

    trend = []

    for r in records:
        trend.append({
            "date": str(r.date),
            "cases": r.cases
        })

    return {
        "district": district,
        "disease": disease,
        "trend": trend
    }

@app.get("/surveillance/alerts/summary")
def alert_summary(db: Session = Depends(get_db)):
    """
    High-level alert summary for government dashboard
    """

    today = date.today()

    alerts = (
        db.query(
            DiseaseSurveillance.alert_level,
            func.count(DiseaseSurveillance.id).label("count")
        )
        .filter(DiseaseSurveillance.date == today)
        .group_by(DiseaseSurveillance.alert_level)
        .all()
    )

    summary = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0
    }

    for a in alerts:
        summary[a.alert_level] = a.count

    return {
        "date": str(today),
        "alert_summary": summary
    }

# -----------------------
# ADDED FOR FLUTTER MILESTONE 4
# -----------------------

@app.get('/visits/list')
def get_visits_list(health_id: str, db: Session = Depends(get_db)):
    visits = db.query(Visit).filter(Visit.health_id == health_id).order_by(Visit.created_at.desc()).all()
    
    result = []
    for v in visits:
        result.append({
            'visit_id': v.visit_id,
            'facility_name': v.facility_name,
            'chief_complaint': v.chief_complaint,
            'visit_type': v.visit_type,
            'created_at': str(v.created_at),
            'district': v.district,
            'state': v.state
        })
    return result

@app.post('/upload-prescription')
def upload_prescription(
    visit_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    import os
    os.makedirs('prescriptions', exist_ok=True)
    ext = file.filename.split('.')[-1]
    filename = f'{visit_id}_{uuid.uuid4()}.{ext}'
    file_path = f'prescriptions/{filename}'
    
    with open(file_path, 'wb') as f:
        f.write(file.file.read())
        
    return {
        'message': 'Prescription uploaded',
        'file_path': file_path
    }

@app.post('/ocr-read')
def ocr_read_document(file_path: str):
    import cv2
    import pytesseract
    import os
    
    file_path = file_path.strip().replace('\'', '').replace('\'', '')
    
    if not os.path.exists(file_path):
        return {'error': 'File not found', 'ocr_text': ''}
        
    image = cv2.imread(file_path)
    if image is None:
        return {'error': 'Invalid image', 'ocr_text': ''}
        
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray)
    
    return {
        'message': 'OCR Success',
        'ocr_text': text
    }


@app.get("/health/status/{health_id}")
def get_health_status(health_id: str, db: Session = Depends(get_db)):
    """
    Returns 'SAFE', 'AT_RISK', or 'MODERATE' based on medical history and location.
    """
    # 1. Check for recent infectious diseases (last 14 days)
    recent_infection = db.query(MedicalRecord).filter(
        MedicalRecord.health_id == health_id,
        MedicalRecord.is_infectious == True
    ).order_by(MedicalRecord.created_at.desc()).first()

    if recent_infection:
        # In a real app, check logic for 'created_at' < 14 days
        # For demo, if *any* infectious record exists that isn't 'resolved', flag it
        return {
            "status": "AT_RISK",
            "color": "#FF5252", # Red
            "message": "You have a recent infectious record. Please isolate."
        }
    
    # 2. Check District Risk (via last visit location)
    last_visit = db.query(Visit).filter(Visit.health_id == health_id).order_by(Visit.created_at.desc()).first()
    if last_visit and last_visit.district:
        district_risk = db.query(DiseaseSurveillance).filter(
            DiseaseSurveillance.district == last_visit.district
        ).order_by(DiseaseSurveillance.date.desc()).first()
        
        if district_risk and district_risk.alert_level == "HIGH":
             return {
                "status": "MODERATE",
                "color": "#FFC107", # Amber
                "message": f"High cases in {last_visit.district}. Be cautious."
            }

    # 3. Default Safe
    return {
        "status": "SAFE",
        "color": "#4CAF50", # Green
        "message": "You are safe. Maintain social distancing."
    }

@app.get("/health/vaccine-certificate/{health_id}")
def get_vaccine_certificate(health_id: str, db: Session = Depends(get_db)):
    """
    Returns signed vaccine certificate data (simulated).
    """
    # 1. Get Profile
    hid = db.query(HealthID).filter(HealthID.health_id == health_id).first()
    if not hid:
         raise HTTPException(status_code=404, detail="Health ID not found")
         
    profile = db.query(Profile).filter(Profile.mobile == hid.mobile).first()
    if not profile:
         raise HTTPException(status_code=404, detail="Profile not found")

    is_vaccinated = False
    status = profile.vaccination_status.lower() if profile.vaccination_status else ""
    
    if "cov" in status or "vaccinated" in status or "double" in status or "booster" in status or "yes" in status:
        is_vaccinated = True
    
    if not is_vaccinated:
        return {"is_vaccinated": False, "message": "No vaccination record found."}

    # 2. Generate Certificate Data
    # In real app, this would be a crypto-signed payload
    cert_id = f"VC-{uuid.uuid4().hex[:8].upper()}"
    
    return {
        "is_vaccinated": True,
        "beneficiary": profile.name,
        "vaccine": "Covishield" if "covi" in status else "Covaxin",
        "dose_1_date": "2021-06-15",
        "dose_2_date": "2021-09-20", 
        "certificate_id": cert_id,
        "uhid": health_id,
        "qr_data": f"SWASTH_ID:{health_id}|VAC:YES|ID:{cert_id}"
    }

# -----------------------
# RECORDS TAB ENDPOINTS
# -----------------------

@app.post("/api/records/upload")
def upload_medical_record(
    health_id: str = Form(...),
    visit_id: str = Form(None),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    import os
    import uuid
    from datetime import datetime

    os.makedirs("medical_records", exist_ok=True)
    
    file_extension = file.filename.split(".")[-1]
    doc_uid = str(uuid.uuid4())
    filename = f"{health_id}_{doc_uid}.{file_extension}"
    file_path = os.path.join("medical_records", filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    # Replace windows backslashes for web URL
    file_url = file_path.replace("\\", "/")

    doc = MedicalDocument(
        document_id=doc_uid,
        health_id=health_id,
        visit_id=visit_id,
        document_type=document_type,
        file_url=f"/{file_url}",
        file_name=file.filename
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "message": "Record uploaded successfully",
        "document_id": doc_uid,
        "file_url": doc.file_url
    }

@app.get("/api/patients/{health_id}/records")
def get_patient_records(health_id: str, db: Session = Depends(get_db)):
    visits = db.query(Visit).filter(Visit.health_id == health_id).order_by(Visit.created_at.desc()).all()
    documents = db.query(MedicalDocument).filter(MedicalDocument.health_id == health_id).all()

    # Group documents by visit_id
    doc_map = {}
    for doc in documents:
        v_id = doc.visit_id or "unassigned"
        if v_id not in doc_map:
            doc_map[v_id] = []
        doc_map[v_id].append({
            "id": doc.document_id,
            "title": doc.file_name,
            "type": doc.document_type,
            "uploadDate": doc.created_at.isoformat() if doc.created_at else datetime.now().isoformat(),
            "fileUrl": doc.file_url
        })
    
    visit_groups = []
    for v in visits:
        docs = doc_map.get(v.visit_id, [])
        # We only want to show visits if they have records, or if we want to show all timeline anyway.
        # User requested: "Medical Timeline: Visits displayed chronologically. Attachments: X..."
        # If visit has NO attachments, maybe we still show it so they can add to it. Let's include all.
        visit_groups.append({
            "visitId": v.visit_id,
            "visitDate": v.created_at.isoformat() if v.created_at else datetime.now().isoformat(),
            "diagnosis": v.chief_complaint or "General Checkup",
            "doctorName": v.doctor_name or "-",
            "documents": docs,
            "symptoms": v.symptoms,
            "temperature_c": v.temperature_c,
            "bp": v.bp,
            "spo2": v.spo2,
            "visitType": v.visit_type,
            "facilityName": v.facility_name,
            "specialization": v.specialization,
            "vaccineGiven": v.vaccine_given,
            "vaccineName": v.vaccine_name,
            "nextDoseDate": v.next_dose_due_date,
            "referred": v.referred,
            "referredTo": v.referred_to,
            "referralReason": v.referral_reason,
        })

    # Add unassigned documents as a generic group at the top or bottom
    if "unassigned" in doc_map and doc_map["unassigned"]:
        visit_groups.insert(0, {
            "visitId": "unassigned",
            "visitDate": doc_map["unassigned"][0]["uploadDate"], 
            "diagnosis": "Uploaded Records (No Visit Linked)",
            "doctorName": "-",
            "documents": doc_map["unassigned"]
        })

    return {
        "health_id": health_id,
        "visits": visit_groups
    }
