"""
AI Summary Generator using Google Gemini API (free tier).

Sends structured patient data to Gemini to generate a comprehensive,
doctor-ready medical summary in JSON format.
Supports multilingual output.

Free tier: 15 RPM, 1M+ tokens/day with gemini-2.0-flash.
Get your key at: https://aistudio.google.com/apikey
"""

import json
import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Language names for prompt
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "bn": "Bengali",
    "te": "Telugu",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
}

# Gemini API endpoint
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def generate_summary(
    timeline: list[dict],
    trends: list[dict],
    drug_interactions: dict,
    entities: dict,
    patient_info: dict,
    language: str = "en",
) -> dict:
    """
    Generate a comprehensive medical summary using Google Gemini.

    Args:
        timeline: Full patient timeline events
        trends: Lab value trend analysis results
        drug_interactions: Drug interaction check results
        entities: All extracted entities
        patient_info: Basic patient information
        language: Target language for the summary

    Returns:
        Structured JSON summary with sections.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("No Gemini API key — returning template summary")
        return _generate_fallback_summary(timeline, trends, drug_interactions, entities, patient_info)

    try:
        lang_name = LANGUAGE_NAMES.get(language, "English")
        prompt = _build_prompt(timeline, trends, drug_interactions, entities, patient_info, lang_name)

        url = GEMINI_API_URL.format(model=settings.GEMINI_MODEL)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": settings.GEMINI_MAX_TOKENS,
                "responseMimeType": "application/json",
            },
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are an expert medical AI assistant. Analyze patient data and generate structured medical summaries. "
                            "Always respond with valid JSON only, no markdown formatting.\n\n"
                            "CRITICAL ACCURACY RULES — YOU MUST FOLLOW THESE:\n\n"
                            "1. REFERENCE RANGES vs PATIENT VALUES: Medical reports contain reference range tables, thresholds, "
                            "and educational text. These are NOT patient data. Examples of INFORMATIONAL text to IGNORE:\n"
                            "   - 'EST. GLOMERULAR FILTRATION RATE (eGFR)' sections with lines like '> = 90 : Normal', "
                            "'60 - 89 : Mild Decrease', '< 15 : Kidney Failure' — these are interpretation guides, NOT diagnoses.\n"
                            "   - 'Bio. Ref. Interval' or 'Reference Range' columns showing normal ranges like '70 - 100 mg/dL'.\n"
                            "   - 'Clinical Significance' sections describing what abnormal values could mean.\n"
                            "   - Lines starting with comparison operators (< > ≤ ≥) followed by a number and a condition name.\n"
                            "   - Phrases like 'if value is', 'indicates', 'suggests', 'may represent'.\n\n"
                            "2. ONLY report conditions the patient ACTUALLY HAS based on their measured values. "
                            "If the report has an eGFR value of 85 and the reference table says '< 15 : Kidney Failure', "
                            "the patient does NOT have kidney failure — report their actual eGFR of 85 and note it falls in the 'Mild Decrease' range.\n\n"
                            "3. Only list medications the patient is ACTUALLY TAKING, not drugs mentioned in warnings or references.\n\n"
                            "4. When uncertain about whether something is a real finding vs. reference text, OMIT it.\n\n"
                            "5. For lab values, always report the ACTUAL measured value, not the reference range boundaries."
                        )
                    }
                ]
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json=payload,
            )
            response.raise_for_status()

        result = response.json()

        # Extract text from Gemini response
        response_text = ""
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if "text" in part:
                    response_text += part["text"]

        if not response_text.strip():
            logger.warning("Empty response from Gemini — using fallback")
            return _generate_fallback_summary(timeline, trends, drug_interactions, entities, patient_info)

        # Parse JSON response
        response_text = response_text.strip()
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        summary = json.loads(response_text)
        summary["_metadata"] = {
            "model": settings.GEMINI_MODEL,
            "language": language,
            "generated_by": "gemini",
        }

        logger.info(f"Gemini summary generated in {lang_name}")
        return summary

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.debug(f"Response was: {response_text[:500]}")
        return _generate_fallback_summary(timeline, trends, drug_interactions, entities, patient_info)
    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API HTTP error {e.response.status_code}: {e.response.text[:300]}")
        return _generate_fallback_summary(timeline, trends, drug_interactions, entities, patient_info)
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return _generate_fallback_summary(timeline, trends, drug_interactions, entities, patient_info)


def _build_prompt(
    timeline: list[dict],
    trends: list[dict],
    drug_interactions: dict,
    entities: dict,
    patient_info: dict,
    language: str,
) -> str:
    """Build the structured prompt for Gemini."""

    # Limit data size for prompt
    timeline_summary = timeline[:30]  # Last 30 events
    trend_summary = [
        {k: v for k, v in t.items() if k != "data_points"}
        for t in trends
    ]

    prompt = f"""
Analyze this patient's medical data and generate a comprehensive doctor-ready summary.

## Patient Information
{json.dumps(patient_info, indent=2, default=str)}

## Health Timeline (chronological events, most recent first)
{json.dumps(timeline_summary, indent=2, default=str)}

## Lab Value Trends
{json.dumps(trend_summary, indent=2, default=str)}

## Drug Interaction Analysis
{json.dumps(drug_interactions, indent=2, default=str)}

## Extracted Medical Entities
Diagnoses: {json.dumps(entities.get("diagnoses", []), default=str)}
Medications: {json.dumps(entities.get("drugs", []), default=str)}
Symptoms: {json.dumps(entities.get("symptoms", []), default=str)}

## Instructions
Generate a structured medical summary as a JSON object with EXACTLY these keys:

{{
    "patient_overview": "2-3 sentence overview of the patient's overall health status and primary conditions",
    "critical_alerts": ["List of urgent findings that need immediate attention"],
    "lab_trends": [
        {{
            "metric": "metric name",
            "status": "RISING/FALLING/STABLE/CRITICAL",
            "interpretation": "What this trend means clinically",
            "action": "Recommended action"
        }}
    ],
    "medication_summary": {{
        "current_medications": ["List of all current medications with dosages if available"],
        "notes": "Any medication-related observations"
    }},
    "drug_interaction_warnings": ["Clear warnings about drug interactions found"],
    "diagnoses_summary": ["List of all diagnosed conditions with current status"],
    "recommendations": ["Actionable medical recommendations"],
    "follow_up_tests_suggested": ["Specific tests recommended for next visit"],
    "risk_assessment": {{
        "overall_risk": "LOW/MODERATE/HIGH",
        "risk_factors": ["List of identified risk factors"]
    }}
}}

IMPORTANT: 
- Respond ONLY with the JSON object, no other text
- Generate the summary in {language}
- Be clinically accurate and use appropriate medical terminology
- Highlight any values that are outside normal range
- If data is insufficient for a section, still include the key with a note

CRITICAL — ACCURACY RULES (you MUST follow these):
- ONLY use ACTUAL patient lab results/values. Do NOT confuse reference ranges, thresholds, or educational text with real patient data.
- Medical reports often contain lines like "If GFR < 15 → kidney failure" or "Normal range: 70-100 mg/dL" — these are INFORMATIONAL, NOT the patient's values. IGNORE them completely.
- If a value appears next to comparison operators (<, >, ≤, ≥) or phrases like "less than", "greater than", "indicates", "suggests", "if value is" — it is a REFERENCE threshold, not patient data.
- Only report diagnoses that the patient ACTUALLY HAS, not conditions mentioned as possibilities or educational context.
- Only list medications the patient is ACTUALLY TAKING, not drugs mentioned in reference or interaction warnings.
- When in doubt about whether something is a real finding vs. reference text, OMIT it rather than include false data.
"""
    return prompt


def _generate_fallback_summary(
    timeline: list[dict],
    trends: list[dict],
    drug_interactions: dict,
    entities: dict,
    patient_info: dict,
) -> dict:
    """
    Generate a rule-based summary when Gemini API is unavailable.
    Uses extracted data directly to build a structured summary.
    """
    # Collect critical alerts
    critical_alerts = []
    for trend in trends:
        if trend.get("trend") == "CRITICAL":
            critical_alerts.append(
                f"{trend['metric']}: {trend['current_value']} {trend.get('unit', '')} — {trend.get('threshold_label', 'Critical level')}"
            )

    # Collect rising trends
    lab_trends = []
    for trend in trends:
        lab_trends.append({
            "metric": trend.get("metric", ""),
            "status": trend.get("trend", "STABLE"),
            "interpretation": trend.get("message", ""),
            "action": "Monitor closely" if trend.get("trend") in ("RISING", "CRITICAL") else "Continue monitoring",
        })

    # Medications
    drugs = entities.get("drugs", [])
    drug_names = [d.get("entity", d.get("name", "")) if isinstance(d, dict) else str(d) for d in drugs]

    # Drug interaction warnings
    interaction_warnings = []
    for interaction in drug_interactions.get("potential_interactions", []):
        pair = interaction.get("drug_pair", [])
        warning = interaction.get("warning_text", "")
        interaction_warnings.append(f"{' + '.join(pair)}: {warning[:150]}")

    # Diagnoses
    diagnoses = entities.get("diagnoses", [])
    diag_names = [d.get("entity", str(d)) if isinstance(d, dict) else str(d) for d in diagnoses]

    # Risk assessment
    risk = "LOW"
    risk_factors = []
    if len(critical_alerts) > 0:
        risk = "HIGH"
        risk_factors.extend(critical_alerts)
    elif any(t.get("trend") == "RISING" for t in trends):
        risk = "MODERATE"
        risk_factors.append("Rising lab values detected")
    if interaction_warnings:
        risk = max(risk, "MODERATE")
        risk_factors.append("Drug interaction warnings present")

    # Build overview
    patient_name = patient_info.get("name", "Patient")
    report_count = patient_info.get("report_count", 1)
    overview = f"{patient_name} has {report_count} report(s) on file."
    if diag_names:
        overview += f" Diagnosed conditions: {', '.join(diag_names[:5])}."
    if critical_alerts:
        overview += f" {len(critical_alerts)} critical alert(s) require attention."

    return {
        "patient_overview": overview,
        "critical_alerts": critical_alerts if critical_alerts else ["No critical alerts at this time"],
        "lab_trends": lab_trends,
        "medication_summary": {
            "current_medications": drug_names if drug_names else ["No medications extracted"],
            "notes": f"{len(drug_names)} medication(s) identified",
        },
        "drug_interaction_warnings": interaction_warnings if interaction_warnings else ["No interactions detected"],
        "diagnoses_summary": diag_names if diag_names else ["No diagnoses extracted"],
        "recommendations": [
            "Review all lab values that are outside normal range",
            "Discuss medication changes with healthcare provider",
            "Schedule follow-up within 3 months for trending values",
        ],
        "follow_up_tests_suggested": [
            f"Recheck {t['metric']}" for t in trends
            if t.get("trend") in ("RISING", "CRITICAL", "FALLING")
        ][:5] or ["Complete blood count", "Basic metabolic panel"],
        "risk_assessment": {
            "overall_risk": risk,
            "risk_factors": risk_factors if risk_factors else ["None identified"],
        },
        "_metadata": {
            "model": "rule-based-fallback",
            "language": "en",
            "generated_by": "fallback",
        },
    }
