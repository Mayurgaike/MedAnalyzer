"""
FastAPI Main Application — Medical Report Analyzer.

Endpoints:
  POST /analyze          — single report upload
  POST /analyze-multiple — multiple reports, unified timeline
  GET  /patient/{id}/timeline — fetch stored patient timeline
  GET  /patient/{id}/summary  — fetch AI summary
  POST /patient/create   — create patient profile
  GET  /patients/recent   — list recent patients
  GET  /demo/data         — load demo mode data
"""

import os
import json
import uuid
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db, init_db
from backend.models import Patient, Report, TimelineEvent, LabResult

# Module imports
from backend.ocr.extractor import extract_text
from backend.nlp.ner import extract_entities, merge_with_regex_entities
from backend.nlp.regex_extractor import extract_structured_data
from backend.timeline.builder import (
    build_timeline,
    get_full_timeline,
    get_lab_time_series,
    REFERENCE_RANGES,
)
from backend.trends.detector import analyze_trends
from backend.drugs.interaction import check_drug_interactions_sync
from backend.summary.generator import generate_summary

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered medical report analyzer with timeline tracking & health insights",
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()
    logger.info(f"🏥 {settings.APP_NAME} v{settings.APP_VERSION} started")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "endpoints": [
            "POST /analyze",
            "POST /analyze-multiple",
            "GET /patient/{id}/timeline",
            "GET /patient/{id}/summary",
            "POST /patient/create",
            "GET /patients/recent",
            "GET /demo/data",
        ],
    }


# ---------------------------------------------------------------------------
# Patient Management
# ---------------------------------------------------------------------------
@app.post("/patient/create")
async def create_patient(
    name: str = Form(...),
    external_id: str = Form(None),
    date_of_birth: str = Form(None),
    gender: str = Form(None),
    language: str = Form("en"),
    db: Session = Depends(get_db),
):
    """Create a new patient profile."""
    # Check if external_id already exists
    if external_id:
        existing = db.query(Patient).filter(Patient.external_id == external_id).first()
        if existing:
            return existing.to_dict()

    patient = Patient(
        external_id=external_id or f"P-{uuid.uuid4().hex[:8].upper()}",
        date_of_birth=date_of_birth,
        gender=gender,
        language=language,
    )
    patient.name = name  # Uses encrypted setter
    db.add(patient)
    db.commit()
    db.refresh(patient)

    logger.info(f"Created patient: {patient.id} ({name})")
    return patient.to_dict()


@app.get("/patients/recent")
async def get_recent_patients(limit: int = 10, db: Session = Depends(get_db)):
    """Get recently created/updated patients."""
    patients = (
        db.query(Patient)
        .order_by(Patient.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [p.to_dict() for p in patients]


@app.get("/patient/{patient_id}")
async def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get patient details."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient.to_dict()


# ---------------------------------------------------------------------------
# Single Report Analysis
# ---------------------------------------------------------------------------
@app.post("/analyze")
async def analyze_report(
    file: UploadFile = File(...),
    patient_name: str = Form("Unknown Patient"),
    patient_id: int | None = Form(None),
    language: str = Form("en"),
    db: Session = Depends(get_db),
):
    """
    Full analysis pipeline for a single medical report.
    
    Steps: File detect → OCR → NER → Regex → Timeline → Trends → Drug check → AI Summary
    """
    logger.info(f"📄 Analyzing report: {file.filename} for patient: {patient_name}")

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)")

    # Save file temporarily
    temp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    try:
        # Step 1: Get or create patient
        patient = _get_or_create_patient(db, patient_id, patient_name, language)

        # Step 2: Extract text (OCR pipeline)
        extraction = extract_text(
            file_path=temp_path,
            file_bytes=file_bytes,
            filename=file.filename,
        )
        logger.info(f"Text extracted ({extraction.engine_used}, confidence={extraction.confidence:.2f})")

        # Step 3: Run NER
        ner_entities = extract_entities(extraction.text)

        # Step 4: Run regex extractors (wrapped — OCR text can be noisy)
        try:
            regex_entities = extract_structured_data(extraction.text)
        except Exception as e:
            logger.warning(f"Regex extraction failed (non-fatal, continuing): {e}")
            regex_entities = {
                "lab_values": [], "dates": [], "dosages": [],
                "drugs": [], "hospital_name": None, "doctor_name": None, "report_date": None,
            }

        # Step 5: Merge entities
        merged_entities = merge_with_regex_entities(ner_entities, regex_entities)

        # Step 6: Create report record
        report = Report(
            patient_id=patient.id,
            filename=file.filename,
            file_type=extraction.engine_used,
            detected_language=extraction.language or language,
            ocr_confidence=extraction.confidence,
            report_date=merged_entities.get("report_date"),
            hospital_name=merged_entities.get("hospital_name"),
            doctor_name=merged_entities.get("doctor_name"),
        )
        report.raw_text = extraction.text
        report.entities = merged_entities
        report.diagnoses = merged_entities.get("diagnoses", [])
        report.drugs = merged_entities.get("drugs", [])
        report.symptoms = merged_entities.get("symptoms", [])
        db.add(report)
        db.commit()
        db.refresh(report)

        # Step 7: Build timeline
        new_events = build_timeline(db, patient.id, report, merged_entities)

        # Step 8: Get full lab time series & detect trends
        lab_series = get_lab_time_series(db, patient.id)
        trends = analyze_trends(lab_series)

        # Step 9: Check drug interactions
        all_drug_names = _collect_drug_names(db, patient.id)
        drug_interactions = check_drug_interactions_sync(all_drug_names)

        # Step 10: Generate AI summary
        full_timeline = get_full_timeline(db, patient.id)
        patient_info = patient.to_dict()
        summary = await generate_summary(
            timeline=full_timeline,
            trends=trends,
            drug_interactions=drug_interactions,
            entities=merged_entities,
            patient_info=patient_info,
            language=extraction.language or language,
        )

        # Save summary to report
        report.ai_summary = summary
        db.commit()

        # Step 11: Return full response
        return {
            "status": "success",
            "patient": patient_info,
            "report": report.to_dict(),
            "extraction": {
                "engine_used": extraction.engine_used,
                "confidence": extraction.confidence,
                "language": extraction.language,
                "text_length": len(extraction.text),
            },
            "entities": merged_entities,
            "timeline": full_timeline,
            "lab_series": lab_series,
            "trends": trends,
            "drug_interactions": drug_interactions,
            "summary": summary,
        }

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ---------------------------------------------------------------------------
# Multiple Report Analysis
# ---------------------------------------------------------------------------
@app.post("/analyze-multiple")
async def analyze_multiple_reports(
    files: list[UploadFile] = File(...),
    patient_name: str = Form("Unknown Patient"),
    patient_id: int | None = Form(None),
    language: str = Form("en"),
    db: Session = Depends(get_db),
):
    """Analyze multiple reports and build unified timeline."""
    logger.info(f"📄 Analyzing {len(files)} reports for patient: {patient_name}")

    patient = _get_or_create_patient(db, patient_id, patient_name, language)
    all_entities = {}
    reports_data = []

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            continue

        file_bytes = await file.read()
        temp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        try:
            # Extract text
            extraction = extract_text(file_path=temp_path, file_bytes=file_bytes, filename=file.filename)

            # NER + Regex
            ner_entities = extract_entities(extraction.text)
            try:
                regex_entities = extract_structured_data(extraction.text)
            except Exception as e:
                logger.warning(f"Regex extraction failed for {file.filename} (non-fatal): {e}")
                regex_entities = {
                    "lab_values": [], "dates": [], "dosages": [],
                    "drugs": [], "hospital_name": None, "doctor_name": None, "report_date": None,
                }
            merged = merge_with_regex_entities(ner_entities, regex_entities)

            # Create report
            report = Report(
                patient_id=patient.id,
                filename=file.filename,
                file_type=extraction.engine_used,
                detected_language=extraction.language or language,
                ocr_confidence=extraction.confidence,
                report_date=merged.get("report_date"),
                hospital_name=merged.get("hospital_name"),
                doctor_name=merged.get("doctor_name"),
            )
            report.raw_text = extraction.text
            report.entities = merged
            report.diagnoses = merged.get("diagnoses", [])
            report.drugs = merged.get("drugs", [])
            report.symptoms = merged.get("symptoms", [])
            db.add(report)
            db.commit()
            db.refresh(report)

            # Build timeline events
            build_timeline(db, patient.id, report, merged)
            reports_data.append(report.to_dict())

            # Accumulate entities
            for key in ("diagnoses", "drugs", "symptoms"):
                if key not in all_entities:
                    all_entities[key] = []
                all_entities[key].extend(merged.get(key, []))

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # Get consolidated data
    full_timeline = get_full_timeline(db, patient.id)
    lab_series = get_lab_time_series(db, patient.id)
    trends = analyze_trends(lab_series)
    all_drug_names = _collect_drug_names(db, patient.id)
    drug_interactions = check_drug_interactions_sync(all_drug_names)

    patient_info = patient.to_dict()
    summary = await generate_summary(
        full_timeline, trends, drug_interactions, all_entities, patient_info, language
    )

    return {
        "status": "success",
        "patient": patient_info,
        "reports": reports_data,
        "timeline": full_timeline,
        "lab_series": lab_series,
        "trends": trends,
        "drug_interactions": drug_interactions,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Timeline & Summary endpoints
# ---------------------------------------------------------------------------
@app.get("/patient/{patient_id}/timeline")
async def get_patient_timeline(patient_id: int, db: Session = Depends(get_db)):
    """Fetch stored patient timeline."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    timeline = get_full_timeline(db, patient_id)
    lab_series = get_lab_time_series(db, patient_id)
    trends = analyze_trends(lab_series)

    return {
        "patient": patient.to_dict(),
        "timeline": timeline,
        "lab_series": lab_series,
        "trends": trends,
    }


@app.get("/patient/{patient_id}/summary")
async def get_patient_summary(patient_id: int, db: Session = Depends(get_db)):
    """Fetch AI summary for a patient."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    # Get the latest report with summary
    report = (
        db.query(Report)
        .filter(Report.patient_id == patient_id)
        .order_by(Report.created_at.desc())
        .first()
    )

    if report and report.ai_summary:
        return {
            "patient": patient.to_dict(),
            "summary": report.ai_summary,
        }

    # Generate fresh summary
    full_timeline = get_full_timeline(db, patient_id)
    lab_series = get_lab_time_series(db, patient_id)
    trends = analyze_trends(lab_series)
    all_drug_names = _collect_drug_names(db, patient_id)
    drug_interactions = check_drug_interactions_sync(all_drug_names)

    # Collect all entities from reports
    reports = db.query(Report).filter(Report.patient_id == patient_id).all()
    all_entities = {"diagnoses": [], "drugs": [], "symptoms": []}
    for r in reports:
        all_entities["diagnoses"].extend(r.diagnoses)
        all_entities["drugs"].extend(r.drugs)
        all_entities["symptoms"].extend(r.symptoms)

    summary = await generate_summary(
        full_timeline, trends, drug_interactions, all_entities,
        patient.to_dict(), patient.language
    )

    return {
        "patient": patient.to_dict(),
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Demo Mode Data
# ---------------------------------------------------------------------------
@app.get("/demo/data")
async def get_demo_data(db: Session = Depends(get_db)):
    """
    Load pre-built realistic demo data:
    A diabetic patient with 6 months of reports showing rising HbA1c,
    BP fluctuations, and a drug interaction warning.
    """
    logger.info("🎮 Loading demo mode data...")

    # Create demo patient
    patient = Patient(
        external_id="DEMO-001",
        date_of_birth="1975-03-15",
        gender="Male",
        language="en",
    )
    patient.name = "Rajesh Kumar"

    # Check if demo patient already exists
    existing = db.query(Patient).filter(Patient.external_id == "DEMO-001").first()
    if existing:
        # Clear old data
        db.query(TimelineEvent).filter(TimelineEvent.patient_id == existing.id).delete()
        db.query(LabResult).filter(LabResult.patient_id == existing.id).delete()
        db.query(Report).filter(Report.patient_id == existing.id).delete()
        db.delete(existing)
        db.commit()

    db.add(patient)
    db.commit()
    db.refresh(patient)

    # ---- Build 6 months of realistic reports ----
    demo_reports = [
        {
            "date": "2025-10-15",
            "hospital": "Apollo Hospital, Mumbai",
            "doctor": "Dr. Priya Sharma",
            "diagnoses": [
                {"entity": "Type 2 Diabetes Mellitus", "score": 0.95, "category": "diagnoses"},
                {"entity": "Essential Hypertension", "score": 0.92, "category": "diagnoses"},
            ],
            "drugs": [
                {"entity": "Metformin", "score": 0.98, "category": "drugs"},
                {"entity": "Amlodipine", "score": 0.96, "category": "drugs"},
            ],
            "lab_values": [
                {"metric": "HbA1c", "value": 6.1, "unit": "%"},
                {"metric": "Blood Sugar", "value": 118, "unit": "mg/dL"},
                {"metric": "BP Systolic", "value": 132, "unit": "mmHg"},
                {"metric": "BP Diastolic", "value": 84, "unit": "mmHg"},
                {"metric": "Hemoglobin", "value": 14.2, "unit": "g/dL"},
                {"metric": "Creatinine", "value": 0.9, "unit": "mg/dL"},
                {"metric": "Cholesterol", "value": 210, "unit": "mg/dL"},
                {"metric": "BMI", "value": 27.5, "unit": "kg/m²"},
            ],
        },
        {
            "date": "2025-11-20",
            "hospital": "Apollo Hospital, Mumbai",
            "doctor": "Dr. Priya Sharma",
            "diagnoses": [
                {"entity": "Type 2 Diabetes Mellitus", "score": 0.95, "category": "diagnoses"},
            ],
            "drugs": [
                {"entity": "Metformin", "score": 0.98, "category": "drugs"},
                {"entity": "Amlodipine", "score": 0.96, "category": "drugs"},
                {"entity": "Atorvastatin", "score": 0.94, "category": "drugs"},
            ],
            "lab_values": [
                {"metric": "HbA1c", "value": 6.4, "unit": "%"},
                {"metric": "Blood Sugar", "value": 132, "unit": "mg/dL"},
                {"metric": "BP Systolic", "value": 138, "unit": "mmHg"},
                {"metric": "BP Diastolic", "value": 88, "unit": "mmHg"},
                {"metric": "Hemoglobin", "value": 13.8, "unit": "g/dL"},
                {"metric": "Creatinine", "value": 1.0, "unit": "mg/dL"},
                {"metric": "Cholesterol", "value": 225, "unit": "mg/dL"},
                {"metric": "LDL Cholesterol", "value": 142, "unit": "mg/dL"},
            ],
        },
        {
            "date": "2026-01-10",
            "hospital": "Fortis Healthcare, Mumbai",
            "doctor": "Dr. Amit Patel",
            "diagnoses": [
                {"entity": "Type 2 Diabetes Mellitus", "score": 0.95, "category": "diagnoses"},
                {"entity": "Dyslipidemia", "score": 0.88, "category": "diagnoses"},
            ],
            "drugs": [
                {"entity": "Metformin", "score": 0.98, "category": "drugs"},
                {"entity": "Glimepiride", "score": 0.95, "category": "drugs"},
                {"entity": "Amlodipine", "score": 0.96, "category": "drugs"},
                {"entity": "Atorvastatin", "score": 0.94, "category": "drugs"},
            ],
            "lab_values": [
                {"metric": "HbA1c", "value": 6.8, "unit": "%"},
                {"metric": "Blood Sugar", "value": 145, "unit": "mg/dL"},
                {"metric": "BP Systolic", "value": 142, "unit": "mmHg"},
                {"metric": "BP Diastolic", "value": 90, "unit": "mmHg"},
                {"metric": "Hemoglobin", "value": 13.5, "unit": "g/dL"},
                {"metric": "Creatinine", "value": 1.1, "unit": "mg/dL"},
                {"metric": "Cholesterol", "value": 195, "unit": "mg/dL"},
                {"metric": "LDL Cholesterol", "value": 118, "unit": "mg/dL"},
                {"metric": "Triglycerides", "value": 180, "unit": "mg/dL"},
            ],
        },
        {
            "date": "2026-02-18",
            "hospital": "Apollo Hospital, Mumbai",
            "doctor": "Dr. Priya Sharma",
            "diagnoses": [
                {"entity": "Type 2 Diabetes Mellitus", "score": 0.95, "category": "diagnoses"},
                {"entity": "Essential Hypertension", "score": 0.92, "category": "diagnoses"},
                {"entity": "Diabetic Nephropathy (early)", "score": 0.75, "category": "diagnoses"},
            ],
            "drugs": [
                {"entity": "Metformin", "score": 0.98, "category": "drugs"},
                {"entity": "Glimepiride", "score": 0.95, "category": "drugs"},
                {"entity": "Losartan", "score": 0.93, "category": "drugs"},
                {"entity": "Atorvastatin", "score": 0.94, "category": "drugs"},
            ],
            "lab_values": [
                {"metric": "HbA1c", "value": 7.2, "unit": "%"},
                {"metric": "Blood Sugar", "value": 158, "unit": "mg/dL"},
                {"metric": "BP Systolic", "value": 148, "unit": "mmHg"},
                {"metric": "BP Diastolic", "value": 92, "unit": "mmHg"},
                {"metric": "Hemoglobin", "value": 13.0, "unit": "g/dL"},
                {"metric": "Creatinine", "value": 1.3, "unit": "mg/dL"},
                {"metric": "Cholesterol", "value": 188, "unit": "mg/dL"},
                {"metric": "BMI", "value": 28.1, "unit": "kg/m²"},
            ],
        },
        {
            "date": "2026-03-15",
            "hospital": "Apollo Hospital, Mumbai",
            "doctor": "Dr. Priya Sharma",
            "diagnoses": [
                {"entity": "Type 2 Diabetes Mellitus", "score": 0.95, "category": "diagnoses"},
                {"entity": "Essential Hypertension", "score": 0.92, "category": "diagnoses"},
            ],
            "drugs": [
                {"entity": "Metformin", "score": 0.98, "category": "drugs"},
                {"entity": "Glimepiride", "score": 0.95, "category": "drugs"},
                {"entity": "Losartan", "score": 0.93, "category": "drugs"},
                {"entity": "Atorvastatin", "score": 0.94, "category": "drugs"},
                {"entity": "Aspirin", "score": 0.90, "category": "drugs"},
            ],
            "lab_values": [
                {"metric": "HbA1c", "value": 7.5, "unit": "%"},
                {"metric": "Blood Sugar", "value": 168, "unit": "mg/dL"},
                {"metric": "BP Systolic", "value": 135, "unit": "mmHg"},
                {"metric": "BP Diastolic", "value": 85, "unit": "mmHg"},
                {"metric": "Hemoglobin", "value": 12.8, "unit": "g/dL"},
                {"metric": "Creatinine", "value": 1.4, "unit": "mg/dL"},
                {"metric": "TSH", "value": 5.2, "unit": "mIU/L"},
            ],
        },
        {
            "date": "2026-04-10",
            "hospital": "Max Healthcare, Delhi",
            "doctor": "Dr. Vikram Singh",
            "diagnoses": [
                {"entity": "Type 2 Diabetes Mellitus", "score": 0.95, "category": "diagnoses"},
                {"entity": "Essential Hypertension", "score": 0.92, "category": "diagnoses"},
                {"entity": "Subclinical Hypothyroidism", "score": 0.80, "category": "diagnoses"},
            ],
            "drugs": [
                {"entity": "Metformin", "score": 0.98, "category": "drugs"},
                {"entity": "Glimepiride", "score": 0.95, "category": "drugs"},
                {"entity": "Losartan", "score": 0.93, "category": "drugs"},
                {"entity": "Atorvastatin", "score": 0.94, "category": "drugs"},
                {"entity": "Aspirin", "score": 0.90, "category": "drugs"},
                {"entity": "Levothyroxine", "score": 0.88, "category": "drugs"},
            ],
            "lab_values": [
                {"metric": "HbA1c", "value": 7.8, "unit": "%"},
                {"metric": "Blood Sugar", "value": 176, "unit": "mg/dL"},
                {"metric": "BP Systolic", "value": 130, "unit": "mmHg"},
                {"metric": "BP Diastolic", "value": 82, "unit": "mmHg"},
                {"metric": "Hemoglobin", "value": 12.5, "unit": "g/dL"},
                {"metric": "Creatinine", "value": 1.5, "unit": "mg/dL"},
                {"metric": "Cholesterol", "value": 178, "unit": "mg/dL"},
                {"metric": "TSH", "value": 6.8, "unit": "mIU/L"},
                {"metric": "BMI", "value": 28.8, "unit": "kg/m²"},
                {"metric": "Vitamin D", "value": 18, "unit": "ng/mL"},
            ],
        },
    ]

    # Process each demo report
    for i, report_data in enumerate(demo_reports):
        report = Report(
            patient_id=patient.id,
            filename=f"report_{report_data['date']}.pdf",
            file_type="demo",
            detected_language="en",
            ocr_confidence=0.95,
            report_date=report_data["date"],
            hospital_name=report_data["hospital"],
            doctor_name=report_data["doctor"],
        )
        report.raw_text = f"Demo report from {report_data['hospital']} on {report_data['date']}"
        report.entities = report_data
        report.diagnoses = report_data["diagnoses"]
        report.drugs = report_data["drugs"]
        report.symptoms = []
        db.add(report)
        db.commit()
        db.refresh(report)

        # Build timeline
        entities = {
            "diagnoses": report_data["diagnoses"],
            "drugs": report_data["drugs"],
            "symptoms": [],
            "lab_values": report_data["lab_values"],
            "dates": [{"normalized": report_data["date"]}],
            "report_date": report_data["date"],
            "hospital_name": report_data["hospital"],
            "doctor_name": report_data["doctor"],
        }
        build_timeline(db, patient.id, report, entities)

    # Get full analysis
    full_timeline = get_full_timeline(db, patient.id)
    lab_series = get_lab_time_series(db, patient.id)
    trends = analyze_trends(lab_series)

    # Demo drug interactions (pre-built since OpenFDA may be slow)
    drug_interactions = {
        "drug_labels": [
            {
                "drug": "Metformin",
                "warnings": "May cause lactic acidosis in patients with renal impairment. Monitor kidney function regularly.",
                "interactions_text": "Concurrent use with Glimepiride may increase risk of hypoglycemia. Use with Aspirin requires monitoring.",
                "has_interaction_data": True,
            },
            {
                "drug": "Glimepiride",
                "warnings": "Risk of hypoglycemia, especially when combined with other antidiabetic agents.",
                "interactions_text": "Metformin combination increases hypoglycemia risk. NSAIDs may enhance effect.",
                "has_interaction_data": True,
            },
            {
                "drug": "Losartan",
                "warnings": "May increase potassium levels. Monitor in patients with renal impairment.",
                "interactions_text": "Use with Aspirin may reduce antihypertensive effect.",
                "has_interaction_data": True,
            },
            {
                "drug": "Levothyroxine",
                "warnings": "Absorption may be reduced by calcium supplements, antacids. Take on empty stomach.",
                "interactions_text": "Metformin may affect thyroid hormone levels. Monitor TSH closely.",
                "has_interaction_data": True,
            },
        ],
        "potential_interactions": [
            {
                "drug_pair": ["Metformin", "Glimepiride"],
                "severity": "monitor",
                "warning_text": "Combined use increases risk of hypoglycemia. Monitor blood sugar closely, especially during dose adjustments.",
                "source": "OpenFDA label cross-reference",
            },
            {
                "drug_pair": ["Metformin", "Losartan"],
                "severity": "monitor",
                "warning_text": "Both drugs can affect kidney function. Creatinine is rising (currently 1.5 mg/dL) — close monitoring required.",
                "source": "OpenFDA label cross-reference",
            },
            {
                "drug_pair": ["Losartan", "Aspirin"],
                "severity": "monitor",
                "warning_text": "Aspirin may reduce the blood pressure-lowering effect of Losartan. Monitor BP response.",
                "source": "OpenFDA label cross-reference",
            },
            {
                "drug_pair": ["Metformin", "Levothyroxine"],
                "severity": "dangerous",
                "warning_text": "Metformin may suppress TSH levels. Patient has Subclinical Hypothyroidism — TSH at 6.8 mIU/L. Requires close endocrine monitoring and possible dose adjustment of Levothyroxine.",
                "source": "OpenFDA label cross-reference",
            },
        ],
        "summary": "Found 4 potential drug interactions among 6 medications. The Metformin-Levothyroxine interaction is clinically significant given the patient's thyroid status.",
    }

    # Generate AI summary (or use fallback)
    # Build comprehensive aggregated entities from ALL demo reports (deduplicated)
    seen_diag = set()
    seen_drugs = set()
    all_diagnoses = []
    all_drugs = []
    all_lab_values = []
    all_dates = []
    for r in demo_reports:
        for d in r["diagnoses"]:
            key = d["entity"].lower()
            if key not in seen_diag:
                seen_diag.add(key)
                all_diagnoses.append(d)
        for d in r["drugs"]:
            key = d["entity"].lower()
            if key not in seen_drugs:
                seen_drugs.add(key)
                all_drugs.append(d)
        all_lab_values.extend(r["lab_values"])
        all_dates.append({"date_str": r["date"], "normalized": r["date"]})

    all_entities = {
        "diagnoses": all_diagnoses,
        "drugs": all_drugs,
        "symptoms": [],
        "lab_values": all_lab_values,
        "dates": all_dates,
    }

    summary = await generate_summary(
        full_timeline, trends, drug_interactions, all_entities,
        patient.to_dict(), "en"
    )

    return {
        "status": "success",
        "mode": "demo",
        "patient": patient.to_dict(),
        "reports": [
            {
                "date": r["date"],
                "hospital": r["hospital"],
                "doctor": r["doctor"],
            }
            for r in demo_reports
        ],
        "timeline": full_timeline,
        "lab_series": lab_series,
        "trends": trends,
        "drug_interactions": drug_interactions,
        "summary": summary,
        "entities": all_entities,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_or_create_patient(
    db: Session, patient_id: int | None, name: str, language: str
) -> Patient:
    """Get existing patient or create new one."""
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            patient.updated_at = datetime.now(timezone.utc)
            db.commit()
            return patient

    patient = Patient(
        external_id=f"P-{uuid.uuid4().hex[:8].upper()}",
        language=language,
    )
    patient.name = name
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _collect_drug_names(db: Session, patient_id: int) -> list[str]:
    """Collect all drug names from a patient's reports."""
    reports = db.query(Report).filter(Report.patient_id == patient_id).all()
    drug_names = set()
    for report in reports:
        for drug in report.drugs:
            name = drug.get("entity", drug.get("name", "")) if isinstance(drug, dict) else str(drug)
            if name:
                drug_names.add(name)
    return list(drug_names)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
