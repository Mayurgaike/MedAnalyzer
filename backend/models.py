"""
SQLAlchemy ORM models for the Medical Report Analyzer.
Sensitive fields (patient name, raw text) are stored encrypted.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship

from backend.database import Base, encrypt_field, decrypt_field


class Patient(Base):
    """Patient profile with encrypted PII."""

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_encrypted = Column(String(512), nullable=False)
    external_id = Column(String(128), unique=True, index=True, nullable=True)
    date_of_birth = Column(String(64), nullable=True)
    gender = Column(String(16), nullable=True)
    language = Column(String(16), default="en")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    reports = relationship("Report", back_populates="patient", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="patient", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")

    @property
    def name(self) -> str:
        return decrypt_field(self.name_encrypted)

    @name.setter
    def name(self, value: str):
        self.name_encrypted = encrypt_field(value)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "external_id": self.external_id,
            "date_of_birth": self.date_of_birth,
            "gender": self.gender,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "report_count": len(self.reports) if self.reports else 0,
        }


class Report(Base):
    """Individual medical report with extracted data."""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    file_type = Column(String(32), nullable=False)  # "digital_pdf", "scanned_pdf", "image"
    raw_text_encrypted = Column(Text, nullable=True)
    detected_language = Column(String(16), default="en")
    ocr_confidence = Column(Float, nullable=True)
    report_date = Column(String(64), nullable=True)  # Extracted date from the report
    hospital_name = Column(String(256), nullable=True)
    doctor_name = Column(String(256), nullable=True)

    # Extracted entities stored as JSON strings
    entities_json = Column(Text, default="{}")
    diagnoses_json = Column(Text, default="[]")
    drugs_json = Column(Text, default="[]")
    symptoms_json = Column(Text, default="[]")

    # AI summary
    ai_summary_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    patient = relationship("Patient", back_populates="reports")

    @property
    def raw_text(self) -> str:
        return decrypt_field(self.raw_text_encrypted) if self.raw_text_encrypted else ""

    @raw_text.setter
    def raw_text(self, value: str):
        self.raw_text_encrypted = encrypt_field(value) if value else None

    @property
    def entities(self) -> dict:
        try:
            return json.loads(self.entities_json) if self.entities_json else {}
        except json.JSONDecodeError:
            return {}

    @entities.setter
    def entities(self, value: dict):
        self.entities_json = json.dumps(value, ensure_ascii=False)

    @property
    def diagnoses(self) -> list:
        try:
            return json.loads(self.diagnoses_json) if self.diagnoses_json else []
        except json.JSONDecodeError:
            return []

    @diagnoses.setter
    def diagnoses(self, value: list):
        self.diagnoses_json = json.dumps(value, ensure_ascii=False)

    @property
    def drugs(self) -> list:
        try:
            return json.loads(self.drugs_json) if self.drugs_json else []
        except json.JSONDecodeError:
            return []

    @drugs.setter
    def drugs(self, value: list):
        self.drugs_json = json.dumps(value, ensure_ascii=False)

    @property
    def symptoms(self) -> list:
        try:
            return json.loads(self.symptoms_json) if self.symptoms_json else []
        except json.JSONDecodeError:
            return []

    @symptoms.setter
    def symptoms(self, value: list):
        self.symptoms_json = json.dumps(value, ensure_ascii=False)

    @property
    def ai_summary(self) -> dict | None:
        try:
            return json.loads(self.ai_summary_json) if self.ai_summary_json else None
        except json.JSONDecodeError:
            return None

    @ai_summary.setter
    def ai_summary(self, value: dict):
        self.ai_summary_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "detected_language": self.detected_language,
            "ocr_confidence": self.ocr_confidence,
            "report_date": self.report_date,
            "hospital_name": self.hospital_name,
            "doctor_name": self.doctor_name,
            "entities": self.entities,
            "diagnoses": self.diagnoses,
            "drugs": self.drugs,
            "symptoms": self.symptoms,
            "ai_summary": self.ai_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TimelineEvent(Base):
    """Chronological patient event for timeline visualization."""

    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    event_date = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)  # "hospital_visit", "new_medication", "lab_test", "anomaly", "diagnosis"
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(32), default="info")  # "info", "warning", "critical"
    metadata_json = Column(Text, default="{}")
    is_first_occurrence = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    patient = relationship("Patient", back_populates="timeline_events")

    @property
    def event_metadata(self) -> dict:
        try:
            return json.loads(self.metadata_json) if self.metadata_json else {}
        except json.JSONDecodeError:
            return {}

    @event_metadata.setter
    def event_metadata(self, value: dict):
        self.metadata_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "report_id": self.report_id,
            "event_date": self.event_date,
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "metadata": self.event_metadata,
            "is_first_occurrence": self.is_first_occurrence,
        }


class LabResult(Base):
    """Individual lab test result for trend tracking."""

    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    metric_name = Column(String(128), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=True)
    test_date = Column(String(64), nullable=False)
    reference_min = Column(Float, nullable=True)
    reference_max = Column(Float, nullable=True)
    is_critical = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    patient = relationship("Patient", back_populates="lab_results")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "report_id": self.report_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "test_date": self.test_date,
            "reference_min": self.reference_min,
            "reference_max": self.reference_max,
            "is_critical": self.is_critical,
        }
