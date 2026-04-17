"""
Regex-based extractor for structured medical data.

Extracts: lab values with units, dates, dosages, doctor/hospital names.
This is Layer 2 of the NER pipeline — provides precise structured data
that the HuggingFace model may miss or return unstructured.
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lab value patterns
# ---------------------------------------------------------------------------
LAB_VALUE_PATTERNS = [
    # HbA1c
    (r"(?:HbA1c|A1C|Glycated\s+Hemoglobin|Glycosylated\s+Hb)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(%)?",
     "HbA1c", "%"),
    # Blood Sugar / Glucose
    (r"(?:Blood\s+Sugar|Glucose|FBS|Fasting\s+Blood\s+Sugar|RBS|Random\s+Blood\s+Sugar|PPBS|Post\s+Prandial)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "Blood Sugar", "mg/dL"),
    # Hemoglobin
    (r"(?:Hemoglobin|Haemoglobin|Hb|HGB)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(g/dL|g/L)?",
     "Hemoglobin", "g/dL"),
    # Blood Pressure — special: two numbers
    (r"(?:Blood\s+Pressure|BP)\s*[:\-=]?\s*(\d{2,3})\s*/\s*(\d{2,3})\s*(mmHg)?",
     "Blood Pressure", "mmHg"),
    # Creatinine
    (r"(?:Creatinine|Serum\s+Creatinine)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|μmol/L|umol/L)?",
     "Creatinine", "mg/dL"),
    # Cholesterol
    (r"(?:Total\s+Cholesterol|Cholesterol)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "Cholesterol", "mg/dL"),
    # HDL
    (r"(?:HDL|HDL\s+Cholesterol)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "HDL Cholesterol", "mg/dL"),
    # LDL
    (r"(?:LDL|LDL\s+Cholesterol)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "LDL Cholesterol", "mg/dL"),
    # Triglycerides
    (r"(?:Triglycerides|TG)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "Triglycerides", "mg/dL"),
    # BMI
    (r"(?:BMI|Body\s+Mass\s+Index)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(kg/m2|kg/m²)?",
     "BMI", "kg/m²"),
    # WBC
    (r"(?:WBC|White\s+Blood\s+Cell|Leukocyte)\s*(?:Count\s*)?[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(?:×?\s*10[³3²]?/[μu]?L|cells/[μu]L|/cumm|thou/uL)?",
     "WBC", "×10³/μL"),
    # RBC
    (r"(?:RBC|Red\s+Blood\s+Cell|Erythrocyte)\s*(?:Count\s*)?[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(?:×?\s*10[⁶6]/[μu]?L|mill/uL|million/cumm)?",
     "RBC", "×10⁶/μL"),
    # Platelets
    (r"(?:Platelets?|PLT|Thrombocyte)\s*(?:Count\s*)?[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(?:×?\s*10[³3]/[μu]?L|thou/uL|lakh/cumm)?",
     "Platelets", "×10³/μL"),
    # TSH
    (r"(?:TSH|Thyroid\s+Stimulating\s+Hormone)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mIU/L|μIU/mL|uIU/mL)?",
     "TSH", "mIU/L"),
    # Vitamin D
    (r"(?:Vitamin\s+D|25-OH\s+Vitamin\s+D|25\(OH\)D)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(ng/mL|nmol/L)?",
     "Vitamin D", "ng/mL"),
    # ESR
    (r"(?:ESR|Erythrocyte\s+Sedimentation\s+Rate)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mm/hr|mm/h)?",
     "ESR", "mm/hr"),
    # Uric Acid
    (r"(?:Uric\s+Acid|Serum\s+Uric\s+Acid)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL)?",
     "Uric Acid", "mg/dL"),
    # SGPT/ALT
    (r"(?:SGPT|ALT|Alanine\s+Aminotransferase)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(U/L|IU/L)?",
     "SGPT/ALT", "U/L"),
    # SGOT/AST
    (r"(?:SGOT|AST|Aspartate\s+Aminotransferase)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(U/L|IU/L)?",
     "SGOT/AST", "U/L"),
]

# ---------------------------------------------------------------------------
# Date patterns
# ---------------------------------------------------------------------------
DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b", "dmy"),
    # YYYY-MM-DD (ISO)
    (r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b", "ymd"),
    # Month DD, YYYY
    (r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b", "mdy_full"),
    # DD Month YYYY
    (r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", "dmy_full"),
    # Mon DD, YYYY
    (r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})\b", "mdy_short"),
    # DD Mon YYYY
    (r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b", "dmy_short"),
    # Month YYYY
    (r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", "my_full"),
]

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# ---------------------------------------------------------------------------
# Dosage patterns
# ---------------------------------------------------------------------------
DOSAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg|ml|mL|mcg|µg|g|IU|units?|tablets?|caps?|capsules?)"
    r"(?:\s*(?:×|x|X)\s*(\d+))?"
    r"(?:\s*(?:per|/)\s*(day|daily|BD|TDS|OD|QID|BID|TID))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Doctor / Hospital patterns
# ---------------------------------------------------------------------------
DOCTOR_PATTERNS = [
    re.compile(r"(?:Dr\.?|Doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
    re.compile(r"(?:Consultant|Physician|Surgeon|Specialist)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
    re.compile(r"(?:Attending|Referring)\s+(?:Doctor|Physician)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", re.IGNORECASE),
]

HOSPITAL_PATTERNS = [
    re.compile(r"([\w\s]+(?:Hospital|Medical\s+Center|Clinic|Healthcare|Laboratory|Labs?|Institute|Diagnostics))", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Common drug names (for regex-based drug detection backup)
# ---------------------------------------------------------------------------
COMMON_DRUGS = [
    "Metformin", "Insulin", "Glimepiride", "Sitagliptin", "Empagliflozin",
    "Amlodipine", "Losartan", "Telmisartan", "Atenolol", "Ramipril",
    "Atorvastatin", "Rosuvastatin", "Aspirin", "Clopidogrel", "Warfarin",
    "Omeprazole", "Pantoprazole", "Ranitidine", "Metoprolol", "Lisinopril",
    "Levothyroxine", "Prednisone", "Amoxicillin", "Azithromycin", "Ciprofloxacin",
    "Ibuprofen", "Paracetamol", "Acetaminophen", "Diclofenac", "Naproxen",
    "Gabapentin", "Pregabalin", "Sertraline", "Fluoxetine", "Escitalopram",
    "Hydrochlorothiazide", "Furosemide", "Spironolactone", "Doxycycline",
    "Cetirizine", "Montelukast", "Salbutamol", "Budesonide",
]

DRUG_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(d) for d in COMMON_DRUGS) + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_structured_data(text: str) -> dict:
    """
    Extract all structured data from medical text using regex patterns.
    
    Returns dict with:
        lab_values: [{metric, value, unit, raw_match}]
        dates: [{date_str, normalized, format}]
        dosages: [{amount, unit, frequency, raw_match}]
        drugs: [{name}]
        hospital_name: str or None
        doctor_name: str or None
        report_date: str or None (best guess at the report date)
    """
    result = {
        "lab_values": extract_lab_values(text),
        "dates": extract_dates(text),
        "dosages": extract_dosages(text),
        "drugs": extract_drug_names(text),
        "hospital_name": extract_hospital_name(text),
        "doctor_name": extract_doctor_name(text),
        "report_date": None,
    }

    # Set report_date as the most likely date from extracted dates
    if result["dates"]:
        result["report_date"] = result["dates"][0]["normalized"]

    return result


def extract_lab_values(text: str) -> list[dict]:
    """Extract lab test values with units."""
    results = []
    seen = set()

    for pattern, metric_name, default_unit in LAB_VALUE_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            groups = match.groups()

            try:
                if metric_name == "Blood Pressure":
                    # BP has two values
                    systolic = float(groups[0])
                    diastolic = float(groups[1])
                    unit = groups[2] if groups[2] else default_unit

                    # Sanity check: BP values should be reasonable
                    if not (30 <= systolic <= 300 and 20 <= diastolic <= 200):
                        continue

                    bp_key = f"BP Systolic:{systolic}"
                    if bp_key not in seen:
                        seen.add(bp_key)
                        results.append({
                            "metric": "BP Systolic",
                            "value": systolic,
                            "unit": unit,
                            "raw_match": match.group(),
                        })
                    bp_key_d = f"BP Diastolic:{diastolic}"
                    if bp_key_d not in seen:
                        seen.add(bp_key_d)
                        results.append({
                            "metric": "BP Diastolic",
                            "value": diastolic,
                            "unit": unit,
                            "raw_match": match.group(),
                        })
                else:
                    raw_val = groups[0].strip()
                    # Skip values that are just dots/empty or clearly not numeric
                    if not raw_val or raw_val == '.':
                        continue
                    value = float(raw_val)
                    # Skip zero or unreasonably large values (OCR garbage)
                    if value <= 0 or value > 100000:
                        continue
                    unit = groups[1] if len(groups) > 1 and groups[1] else default_unit

                    dedup = f"{metric_name}:{value}"
                    if dedup not in seen:
                        seen.add(dedup)
                        results.append({
                            "metric": metric_name,
                            "value": value,
                            "unit": unit,
                            "raw_match": match.group(),
                        })
            except (ValueError, TypeError) as e:
                # OCR may produce garbage that looks like a number but isn't
                logger.debug(f"Skipping unparseable lab value for {metric_name}: {groups} — {e}")
                continue

    return results


def extract_dates(text: str) -> list[dict]:
    """Extract and normalize dates from text."""
    dates = []
    seen = set()

    for pattern, fmt in DATE_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            groups = match.groups()
            normalized = _normalize_date(groups, fmt)
            if normalized and normalized not in seen:
                seen.add(normalized)
                dates.append({
                    "date_str": match.group(),
                    "normalized": normalized,
                    "format": fmt,
                })

    # Sort by date (most recent first for report_date detection)
    dates.sort(key=lambda d: d["normalized"], reverse=True)
    return dates


def _normalize_date(groups: tuple, fmt: str) -> str | None:
    """Normalize date groups to YYYY-MM-DD format."""
    try:
        if fmt == "dmy":
            d, m, y = int(groups[0]), int(groups[1]), int(groups[2])
        elif fmt == "ymd":
            y, m, d = int(groups[0]), int(groups[1]), int(groups[2])
        elif fmt == "mdy_full":
            m = MONTH_MAP.get(groups[0].lower(), 0)
            d, y = int(groups[1]), int(groups[2])
        elif fmt == "dmy_full":
            d = int(groups[0])
            m = MONTH_MAP.get(groups[1].lower(), 0)
            y = int(groups[2])
        elif fmt == "mdy_short":
            m = MONTH_MAP.get(groups[0].lower(), 0)
            d, y = int(groups[1]), int(groups[2])
        elif fmt == "dmy_short":
            d = int(groups[0])
            m = MONTH_MAP.get(groups[1].lower(), 0)
            y = int(groups[2])
        elif fmt == "my_full":
            m = MONTH_MAP.get(groups[0].lower(), 0)
            y = int(groups[1])
            d = 1  # Default to first of month
        else:
            return None

        if m < 1 or m > 12 or d < 1 or d > 31:
            return None
        if y < 1900 or y > 2100:
            return None

        return f"{y:04d}-{m:02d}-{d:02d}"

    except (ValueError, IndexError):
        return None


def extract_dosages(text: str) -> list[dict]:
    """Extract medication dosages."""
    dosages = []
    seen = set()

    for match in DOSAGE_PATTERN.finditer(text):
        amount = match.group(1)
        unit = match.group(2)
        multiplier = match.group(3)
        frequency = match.group(4)

        key = f"{amount}{unit}"
        if key not in seen:
            seen.add(key)
            dosages.append({
                "amount": float(amount),
                "unit": unit,
                "multiplier": int(multiplier) if multiplier else 1,
                "frequency": frequency or "as directed",
                "raw_match": match.group(),
            })

    return dosages


def extract_drug_names(text: str) -> list[dict]:
    """Extract drug names using known drug list."""
    drugs = []
    seen = set()

    for match in DRUG_REGEX.finditer(text):
        name = match.group(1)
        key = name.lower()
        if key not in seen:
            seen.add(key)
            drugs.append({"name": name, "source": "regex"})

    return drugs


def extract_doctor_name(text: str) -> str | None:
    """Extract doctor name from report."""
    for pattern in DOCTOR_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def extract_hospital_name(text: str) -> str | None:
    """Extract hospital/clinic name from report."""
    for pattern in HOSPITAL_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip()
            # Filter out too-short or too-long matches
            if 5 < len(name) < 100:
                return name
    return None
