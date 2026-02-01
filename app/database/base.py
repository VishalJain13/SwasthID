from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
from app.models.medical_record import MedicalRecord
from app.models.disease_surveillance import DiseaseSurveillance
from app.models.ocr_document import OCRDocument
