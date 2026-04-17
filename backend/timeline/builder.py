"""
Timeline Builder — constructs chronological patient health timeline from multiple reports.

Accepts entities from N reports, normalizes dates, groups events,
flags first occurrences, and stores as structured JSON.
"""

import logging
from datetime import datetime
from collections import defaultdict

from sqlalchemy.orm import Session

from backend.models import Patient, Report, TimelineEvent, LabResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference ranges for lab values (used for critical flagging)
# ---------------------------------------------------------------------------
REFERENCE_RANGES = {
    "HbA1c": {"min": 4.0, "max": 5.6, "critical_high": 6.5, "unit": "%"},
    "Blood Sugar": {"min": 70, "max": 100, "critical_high": 126, "unit": "mg/dL"},
    "Hemoglobin": {"min": 12.0, "max": 17.5, "critical_low": 10.0, "unit": "g/dL"},
    "BP Systolic": {"min": 90, "max": 120, "critical_high": 140, "unit": "mmHg"},
    "BP Diastolic": {"min": 60, "max": 80, "critical_high": 90, "unit": "mmHg"},
    "Creatinine": {"min": 0.6, "max": 1.2, "critical_high": 2.0, "unit": "mg/dL"},
    "Cholesterol": {"min": 0, "max": 200, "critical_high": 240, "unit": "mg/dL"},
    "HDL Cholesterol": {"min": 40, "max": 60, "critical_low": 35, "unit": "mg/dL"},
    "LDL Cholesterol": {"min": 0, "max": 100, "critical_high": 160, "unit": "mg/dL"},
    "Triglycerides": {"min": 0, "max": 150, "critical_high": 200, "unit": "mg/dL"},
    "BMI": {"min": 18.5, "max": 24.9, "critical_high": 30.0, "unit": "kg/m²"},
    "WBC": {"min": 4.0, "max": 11.0, "critical_high": 15.0, "unit": "×10³/μL"},
    "RBC": {"min": 4.0, "max": 5.5, "critical_low": 3.5, "unit": "×10⁶/μL"},
    "Platelets": {"min": 150, "max": 400, "critical_low": 100, "unit": "×10³/μL"},
    "TSH": {"min": 0.4, "max": 4.0, "critical_high": 10.0, "unit": "mIU/L"},
    "Vitamin D": {"min": 30, "max": 100, "critical_low": 20, "unit": "ng/mL"},
    "SGPT/ALT": {"min": 7, "max": 56, "critical_high": 100, "unit": "U/L"},
    "SGOT/AST": {"min": 10, "max": 40, "critical_high": 100, "unit": "U/L"},
    "ESR": {"min": 0, "max": 20, "critical_high": 40, "unit": "mm/hr"},
    "Uric Acid": {"min": 3.0, "max": 7.0, "critical_high": 9.0, "unit": "mg/dL"},
}


def build_timeline(
    db: Session,
    patient_id: int,
    report: Report,
    entities: dict,
) -> list[dict]:
    """
    Build/update the patient's health timeline from a newly analyzed report.
    
    Creates TimelineEvent and LabResult records in the database.
    Returns the list of new events created.
    """
    new_events = []
    report_date = entities.get("report_date") or _guess_date(entities)

    if not report_date:
        report_date = datetime.now().strftime("%Y-%m-%d")
        logger.warning(f"No date found in report — using today: {report_date}")

    # --- Get existing data for first-occurrence detection ---
    existing_diagnoses = _get_existing_values(db, patient_id, "diagnosis")
    existing_drugs = _get_existing_values(db, patient_id, "new_medication")

    # --- 1. Hospital visit event ---
    hospital_name = entities.get("hospital_name", "Medical Facility")
    doctor_name = entities.get("doctor_name", "")
    visit_desc = f"Visit to {hospital_name}"
    if doctor_name:
        prefix = "" if doctor_name.lower().startswith("dr") else "Dr. "
        visit_desc += f" — {prefix}{doctor_name}"

    visit_event = TimelineEvent(
        patient_id=patient_id,
        report_id=report.id,
        event_date=report_date,
        event_type="hospital_visit",
        title="Hospital Visit",
        description=visit_desc,
        severity="info",
    )
    visit_event.event_metadata = {
        "hospital": hospital_name,
        "doctor": doctor_name,
        "filename": report.filename,
    }
    db.add(visit_event)
    new_events.append(visit_event)

    # --- 2. Diagnoses ---
    for diag in entities.get("diagnoses", []):
        name = diag.get("entity", diag) if isinstance(diag, dict) else str(diag)
        is_first = name.lower() not in existing_diagnoses

        event = TimelineEvent(
            patient_id=patient_id,
            report_id=report.id,
            event_date=report_date,
            event_type="diagnosis",
            title=f"Diagnosis: {name}",
            description=f"{'New diagnosis' if is_first else 'Ongoing'}: {name}",
            severity="warning" if is_first else "info",
            is_first_occurrence=is_first,
        )
        event.event_metadata = {"diagnosis": name, "is_new": is_first}
        db.add(event)
        new_events.append(event)

    # --- 3. Medications ---
    for drug in entities.get("drugs", []):
        name = drug.get("entity", drug.get("name", "")) if isinstance(drug, dict) else str(drug)
        if not name:
            continue
        is_first = name.lower() not in existing_drugs

        event = TimelineEvent(
            patient_id=patient_id,
            report_id=report.id,
            event_date=report_date,
            event_type="new_medication" if is_first else "medication",
            title=f"{'New ' if is_first else ''}Medication: {name}",
            description=f"{'Started' if is_first else 'Continuing'}: {name}",
            severity="warning" if is_first else "info",
            is_first_occurrence=is_first,
        )
        event.event_metadata = {"drug": name, "is_new": is_first}
        db.add(event)
        new_events.append(event)

    # --- 4. Lab results ---
    for lab in entities.get("lab_values", []):
        metric = lab.get("metric", "")
        value = lab.get("value")
        unit = lab.get("unit", "")

        if not metric or value is None:
            continue

        # Check if critical
        is_critical = _is_critical(metric, value)
        ref = REFERENCE_RANGES.get(metric, {})

        # Store lab result
        lab_result = LabResult(
            patient_id=patient_id,
            report_id=report.id,
            metric_name=metric,
            value=value,
            unit=unit or ref.get("unit", ""),
            test_date=report_date,
            reference_min=ref.get("min"),
            reference_max=ref.get("max"),
            is_critical=is_critical,
        )
        db.add(lab_result)

        # Create timeline event for lab test
        severity = "critical" if is_critical else "info"
        status = ""
        if is_critical:
            status = " ⚠️ CRITICAL"
        elif ref:
            if value < ref.get("min", float("-inf")):
                status = " ↓ Low"
                severity = "warning"
            elif value > ref.get("max", float("inf")):
                status = " ↑ High"
                severity = "warning"

        event = TimelineEvent(
            patient_id=patient_id,
            report_id=report.id,
            event_date=report_date,
            event_type="lab_test",
            title=f"Lab: {metric}",
            description=f"{metric}: {value} {unit}{status}",
            severity=severity,
        )
        event.event_metadata = {
            "metric": metric,
            "value": value,
            "unit": unit,
            "is_critical": is_critical,
            "reference_min": ref.get("min"),
            "reference_max": ref.get("max"),
        }
        db.add(event)
        new_events.append(event)

    # --- 5. Anomaly flags ---
    for lab in entities.get("lab_values", []):
        if _is_critical(lab.get("metric", ""), lab.get("value", 0)):
            event = TimelineEvent(
                patient_id=patient_id,
                report_id=report.id,
                event_date=report_date,
                event_type="anomaly",
                title=f"⚠️ Critical: {lab['metric']}",
                description=f"{lab['metric']} = {lab['value']} {lab.get('unit', '')} — exceeds critical threshold",
                severity="critical",
            )
            event.event_metadata = {"metric": lab["metric"], "value": lab["value"]}
            db.add(event)
            new_events.append(event)

    db.commit()
    logger.info(f"Timeline updated: {len(new_events)} new events for patient {patient_id}")
    return [e.to_dict() for e in new_events]


def get_full_timeline(db: Session, patient_id: int) -> list[dict]:
    """Get the complete timeline for a patient, sorted chronologically."""
    events = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.patient_id == patient_id)
        .order_by(TimelineEvent.event_date.desc())
        .all()
    )
    return [e.to_dict() for e in events]


def get_lab_time_series(db: Session, patient_id: int) -> dict[str, list[dict]]:
    """
    Get all lab results grouped by metric as time series.
    Format: {metric_name: [{date, value, unit, report_id}]}
    """
    results = (
        db.query(LabResult)
        .filter(LabResult.patient_id == patient_id)
        .order_by(LabResult.test_date.asc())
        .all()
    )

    series = defaultdict(list)
    for r in results:
        series[r.metric_name].append({
            "date": r.test_date,
            "value": r.value,
            "unit": r.unit,
            "report_id": r.report_id,
            "is_critical": r.is_critical,
            "reference_min": r.reference_min,
            "reference_max": r.reference_max,
        })

    return dict(series)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_critical(metric: str, value: float) -> bool:
    """Check if a lab value crosses critical medical thresholds."""
    ref = REFERENCE_RANGES.get(metric)
    if not ref:
        return False

    if "critical_high" in ref and value >= ref["critical_high"]:
        return True
    if "critical_low" in ref and value <= ref["critical_low"]:
        return True
    return False


def _get_existing_values(db: Session, patient_id: int, event_type: str) -> set[str]:
    """Get existing event titles for deduplication."""
    events = (
        db.query(TimelineEvent)
        .filter(
            TimelineEvent.patient_id == patient_id,
            TimelineEvent.event_type == event_type,
        )
        .all()
    )
    existing = set()
    for e in events:
        meta = e.event_metadata
        if event_type == "diagnosis":
            existing.add(meta.get("diagnosis", "").lower())
        elif event_type == "new_medication":
            existing.add(meta.get("drug", "").lower())
    return existing


def _guess_date(entities: dict) -> str | None:
    """Try to find a date from entities' dates list."""
    dates = entities.get("dates", [])
    if dates:
        return dates[0].get("normalized")
    return None
