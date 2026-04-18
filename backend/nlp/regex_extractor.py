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
# Reference range / informational line filters
# These patterns identify lines that describe reference ranges, thresholds,
# or educational content — NOT actual patient values.
# ---------------------------------------------------------------------------

# Words/phrases that indicate a line is describing a reference range, not a patient value
REFERENCE_LINE_MARKERS = re.compile(
    r"(?:"
    r"reference\s*(?:range|value|interval)"
    r"|normal\s*(?:range|value|level)"
    r"|ref\.?\s*(?:range|value|interval)"
    r"|bio\.?\s*ref\.?\s*(?:range|interval)?"
    r"|biological\s*ref"
    r"|expected\s*(?:range|value)"
    r"|desirable\s*(?:range|level|value)"
    r"|optimal\s*(?:range|level)"
    r"|target\s*(?:range|level|value)"
    r"|therapeutic\s*(?:range|level)"
    r"|cut[\s-]?off"
    r"|indicat(?:es|ive|ing)\s+(?:of|that)"
    r"|suggest(?:s|ive|ing)\s+(?:of|that)"
    r"|consistent\s+with"
    r"|may\s+(?:indicate|suggest|represent)"
    r"|implies\s"
    r"|signif(?:ies|icant\s+for)"
    r"|\bif\s+(?:value|level|result|GFR|eGFR|HbA1c|creatinine)"
    r"|\bwhen\s+(?:value|level|result)"
    r"|stage\s*[\d:IViv]"
    r"|note\s*:"
    r"|disclaimer"
    r"|interpretation\s*(?:guide|key|note)"
    r"|methodology"
    r"|\*\s*(?:ref|normal|range)"
    r")",
    re.IGNORECASE,
)

# Patterns immediately before a number that signal it's a reference value, not patient value
REFERENCE_CONTEXT_PATTERN = re.compile(
    r"(?:"
    r"[<>≤≥]\s*$"           # Comparison operator right before the value
    r"|less\s+than\s*$"
    r"|greater\s+than\s*$"
    r"|more\s+than\s*$"
    r"|below\s*$"
    r"|above\s*$"
    r"|under\s*$"
    r"|over\s*$"
    r"|upto\s*$"
    r"|up\s+to\s*$"
    r"|between\s+\d+\s*(?:to|and|-|–)\s*$"  # "between 90 to" → next num is ref
    r"|range\s*:?\s*\d+\s*(?:to|[-–])\s*$" # "range: 70-" → next num is ref
    r")",
    re.IGNORECASE,
)

# Pattern for lines that contain range expressions like "70 - 100" or "70-100 mg/dL"
RANGE_EXPRESSION = re.compile(
    r"\b(\d+\.?\d*)\s*(?:to|[-–—])\s*(\d+\.?\d*)\s*(?:mg/dL|g/dL|mmol/L|mIU/L|%|U/L|IU/L|ng/mL|mm/hr|×10|cells|/cumm|/[μu]L)",
    re.IGNORECASE,
)

# Patterns for lines that look like reference table entries:
#   "> = 90 : Normal", "60 - 89 : Mild Decrease", "< 15 : Kidney Failure"
# These are ranges paired with a clinical interpretation label.
REFERENCE_TABLE_LINE = re.compile(
    r"^\s*"
    r"(?:[<>≤≥]=?\s*)?"                   # optional leading comparison operator
    r"\d+\.?\d*"                           # first number
    r"(?:\s*[-–—]\s*\d+\.?\d*)?"           # optional range (e.g., "60 - 89")
    r"\s*[:;]?\s*"                          # optional colon/semicolon
    r"(?:Normal|Mild|Moderate|Severe|High|Low|Optimal|Borderline|Desirable"
    r"|Acceptable|Elevated|Very\s+High|Failure|Decrease|Increase|Insufficien"
    r"|Deficien|Risk|Abnormal|Positive|Negative|Pre[- ]?diabetic|Diabetic"
    r"|Kidney\s+Failure|Renal\s+Failure|Impaired|Adequate|Inadequate"
    r"|Stage|Chronic|Acute)",
    re.IGNORECASE,
)

# Lines that are clearly section headers for reference information
REFERENCE_SECTION_HEADERS = re.compile(
    r"(?:"
    r"est\.?\s+glomerular\s+filtration"
    r"|e?GFR\s*(?:interpretation|reference|range|value|categories)"
    r"|interpretation\s*:?\s*$"
    r"|Bio\.?\s*Ref\.?\s*Interval"
    r"|reference\s*:?\s*$"
    r"|\bref\.?\s*range\s*:?\s*$"
    r"|clinical\s+significance"
    r"|result\s+interpretation"
    r"|\bhow\s+to\s+read"
    r"|\babout\s+this\s+test"
    r")",
    re.IGNORECASE,
)


def _is_reference_line(line: str) -> bool:
    """Check if a line is describing reference ranges or educational info, not patient data."""
    stripped = line.strip()
    
    # Check explicit reference line markers
    if REFERENCE_LINE_MARKERS.search(stripped):
        return True
    
    # Check reference table line format (e.g., "> = 90 : Normal", "60 - 89 : Mild Decrease")
    if REFERENCE_TABLE_LINE.match(stripped):
        return True
    
    # Lines starting with comparison operators followed by a number and a label
    # e.g., "< 15  : Kidney Failure", "> = 90 : Normal"
    if re.match(r'^\s*[<>≤≥]=?\s*\d', stripped):
        return True
    
    # Lines that are purely "number - number : description" (range-to-label mappings)
    if re.match(r'^\s*\d+\s*[-–—]\s*\d+\s*[:;]', stripped):
        return True
    
    return False


def _is_reference_context(text: str, match_start: int) -> bool:
    """
    Check if the text immediately surrounding a regex match indicates
    this is a reference value, not an actual patient measurement.
    """
    # Get the 80 chars before the match for context
    context_before = text[max(0, match_start - 80):match_start]
    
    # Check for comparison operators or reference phrases before the value
    if REFERENCE_CONTEXT_PATTERN.search(context_before):
        return True
    
    # Check if this value is inside a range expression (e.g., "70 - 100 mg/dL")
    # Look at the surrounding 20 chars
    context_window = text[max(0, match_start - 20):min(len(text), match_start + 60)]
    if RANGE_EXPRESSION.search(context_window):
        return True
    
    # Check if the match line contains a condition label after the value
    # (e.g., "< 15 : Kidney Failure" — the number 15 is a threshold, not a patient value)
    match_line_start = text.rfind('\n', 0, match_start) + 1
    match_line_end = text.find('\n', match_start)
    if match_line_end == -1:
        match_line_end = len(text)
    match_line = text[match_line_start:match_line_end].strip()
    
    # If the line matches a reference table format, it's a reference
    if REFERENCE_TABLE_LINE.match(match_line):
        return True
    
    return False


def clean_text_for_extraction(text: str) -> str:
    """
    Pre-process extracted text to remove reference range sections,
    disclaimers, and educational content before running regex extraction.
    
    This reduces false positives from informational text like:
    'If GFR < 15 mL/min → indicates kidney failure'
    or eGFR interpretation tables:
    '> = 90 : Normal'
    '60 - 89 : Mild Decrease'
    '< 15 : Kidney Failure'
    """
    lines = text.split('\n')
    cleaned_lines = []
    skip_section = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines (keep them for structure)
        if not stripped:
            cleaned_lines.append(line)
            # Only reset section skip after 2+ consecutive blank lines
            # (single blank lines might be inside a reference table)
            continue
        
        # Detect start of reference/educational sections
        lower = stripped.lower()
        
        # Section-level headers that start a block of reference text
        if REFERENCE_SECTION_HEADERS.search(stripped):
            skip_section = True
            continue
        
        if any(marker in lower for marker in [
            'interpretation guide', 'reference range', 'note:', 'disclaimer',
            'methodology', 'instruction', 'how to read', 'explanation',
            'what the results mean', 'understanding your', 'about this test',
            'clinical significance', 'important information',
            'bio. ref. interval', 'bio ref interval', 'biological reference',
        ]):
            skip_section = True
            continue
        
        if skip_section:
            # Check if this line looks like it's still part of the reference section
            # (reference table entries, labels, etc.)
            if _is_reference_line(stripped):
                continue
            # If the line contains actual data patterns (metric: value), stop skipping
            if re.match(r'^[A-Za-z][A-Za-z\s]+[:\-=]\s*\d', stripped):
                skip_section = False
            else:
                continue
        
        # Skip individual reference lines even outside reference sections
        if _is_reference_line(stripped):
            logger.debug(f"Filtered reference line: {stripped[:80]}")
            continue
        
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

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
    # eGFR — IMPORTANT: only match when preceded by metric label and colon/equals,
    # NOT from reference table lines like "> = 90 : Normal"
    (r"(?:e?GFR|Est\.?\s*(?:Glomerular\s+Filtration\s+Rate|GFR))\s*[:\-=]\s*(\d+\.?\d*|\d*\.\d+)\s*(mL/min(?:/1\.73\s*m²?)?)?",
     "eGFR", "mL/min/1.73m²"),
    # BUN / Blood Urea Nitrogen
    (r"(?:BUN|Blood\s+Urea\s+Nitrogen|Urea\s+Nitrogen|Blood\s+Urea)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "BUN", "mg/dL"),
    # Alkaline Phosphatase
    (r"(?:ALP|Alkaline\s+Phosphatase)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(U/L|IU/L)?",
     "ALP", "U/L"),
    # Total Bilirubin
    (r"(?:Total\s+Bilirubin|Bilirubin\s+Total|Bilirubin)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL)?",
     "Bilirubin", "mg/dL"),
    # GGT
    (r"(?:GGT|Gamma\s+GT|Gamma\s+Glutamyl\s+Transferase)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(U/L|IU/L)?",
     "GGT", "U/L"),
    # Calcium
    (r"(?:Calcium|Serum\s+Calcium|Ca)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "Calcium", "mg/dL"),
    # Phosphorus
    (r"(?:Phosphorus|Phosphate|Serum\s+Phosphorus)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(mg/dL|mmol/L)?",
     "Phosphorus", "mg/dL"),
    # Albumin
    (r"(?:Albumin|Serum\s+Albumin)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(g/dL|g/L)?",
     "Albumin", "g/dL"),
    # Total Protein
    (r"(?:Total\s+Protein|Serum\s+Protein)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(g/dL|g/L)?",
     "Total Protein", "g/dL"),
    # Iron
    (r"(?:Iron|Serum\s+Iron)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(μg/dL|ug/dL|mcg/dL)?",
     "Iron", "μg/dL"),
    # Ferritin
    (r"(?:Ferritin|Serum\s+Ferritin)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(ng/mL|μg/L)?",
     "Ferritin", "ng/mL"),
    # Vitamin B12
    (r"(?:Vitamin\s+B12|B12|Cyanocobalamin)\s*[:\-=]?\s*(\d+\.?\d*|\d*\.\d+)\s*(pg/mL|pmol/L)?",
     "Vitamin B12", "pg/mL"),
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
    
    Pre-cleans text to remove reference ranges and educational content
    before running regex extraction to avoid false positives.
    
    Returns dict with:
        lab_values: [{metric, value, unit, raw_match}]
        dates: [{date_str, normalized, format}]
        dosages: [{amount, unit, frequency, raw_match}]
        drugs: [{name}]
        hospital_name: str or None
        doctor_name: str or None
        report_date: str or None (best guess at the report date)
    """
    # Clean text to remove reference ranges / educational sections
    cleaned_text = clean_text_for_extraction(text)
    
    result = {
        "lab_values": extract_lab_values(cleaned_text),
        "dates": extract_dates(text),  # Use original text for dates — they're always relevant
        "dosages": extract_dosages(cleaned_text),
        "drugs": extract_drug_names(cleaned_text),
        "hospital_name": extract_hospital_name(text),  # Use original for hospital names
        "doctor_name": extract_doctor_name(text),       # Use original for doctor names
        "report_date": None,
    }

    # Set report_date as the most likely date from extracted dates
    if result["dates"]:
        result["report_date"] = result["dates"][0]["normalized"]

    return result


def extract_lab_values(text: str) -> list[dict]:
    """Extract lab test values with units, filtering out reference ranges."""
    results = []
    seen = set()

    for pattern, metric_name, default_unit in LAB_VALUE_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            groups = match.groups()

            try:
                # --- Context check: skip if this match is in a reference range context ---
                match_line_start = text.rfind('\n', 0, match.start()) + 1
                match_line_end = text.find('\n', match.end())
                if match_line_end == -1:
                    match_line_end = len(text)
                match_line = text[match_line_start:match_line_end]

                # Skip if the line itself is a reference/informational line
                if _is_reference_line(match_line):
                    logger.debug(f"Skipping reference-line match for {metric_name}: {match_line.strip()[:80]}")
                    continue

                # Skip if the immediate context suggests this is a threshold/comparison value
                if _is_reference_context(text, match.start()):
                    logger.debug(f"Skipping reference-context match for {metric_name}: {match.group()}")
                    continue

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
                # Validate date is reasonable (not future beyond 1 month, not ancient)
                if _is_reasonable_date(normalized):
                    seen.add(normalized)
                    dates.append({
                        "date_str": match.group(),
                        "normalized": normalized,
                        "format": fmt,
                    })

    # Sort by date (most recent first for report_date detection)
    dates.sort(key=lambda d: d["normalized"], reverse=True)
    return dates


def _is_reasonable_date(date_str: str) -> bool:
    """Check if a date string (YYYY-MM-DD) is reasonable for a medical report."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        now = datetime.now()
        # Not more than 30 days in the future
        if dt > now.replace(day=min(now.day + 30, 28 if now.month == 2 else 30)):
            return False
        # Not before 1950
        if dt.year < 1950:
            return False
        return True
    except ValueError:
        return False


def _normalize_date(groups: tuple, fmt: str) -> str | None:
    """
    Normalize date groups to YYYY-MM-DD format.
    
    For ambiguous DD/MM/YYYY vs MM/DD/YYYY formats, prefer DD/MM/YYYY
    (Indian standard) when both interpretations are valid.
    """
    try:
        if fmt == "dmy":
            # Indian standard: DD/MM/YYYY
            d, m, y = int(groups[0]), int(groups[1]), int(groups[2])
            # If the day value > 12, it can only be DD/MM/YYYY
            # If day <= 12 and month <= 12, prefer DD/MM/YYYY (Indian format)
            # If day <= 12 but month > 12, swap (it was actually MM/DD/YYYY)
            if m > 12 and d <= 12:
                # Looks like it was MM/DD/YYYY
                d, m = m, d
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

        # Final validation: try to actually construct the date
        try:
            datetime(y, m, d)
        except ValueError:
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
