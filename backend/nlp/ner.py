"""
Biomedical Named Entity Recognition using HuggingFace d4data/biomedical-ner-all.

Extracts: diseases, chemicals (drugs), genes, species from medical text.
Gracefully falls back to empty results if the model isn't available.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
_ner_pipeline = None
NER_AVAILABLE = False


def _load_ner_model():
    """Load the HuggingFace biomedical NER pipeline (cached)."""
    global _ner_pipeline, NER_AVAILABLE

    if _ner_pipeline is not None:
        return _ner_pipeline

    try:
        from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
        from backend.config import get_settings

        settings = get_settings()
        model_name = settings.NER_MODEL_NAME
        cache_dir = settings.NER_CACHE_DIR

        logger.info(f"Loading NER model: {model_name} (first run downloads ~400MB)...")

        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        model = AutoModelForTokenClassification.from_pretrained(model_name, cache_dir=cache_dir)

        _ner_pipeline = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
            device=-1,  # CPU — use 0 for GPU
        )

        NER_AVAILABLE = True
        logger.info("NER model loaded successfully.")
        return _ner_pipeline

    except Exception as e:
        logger.error(f"Failed to load NER model: {e}")
        NER_AVAILABLE = False
        return None


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------
# Map model entity groups to our categories
ENTITY_MAP = {
    "Disease_disorder": "diagnoses",
    "Sign_symptom": "symptoms",
    "Medication": "drugs",
    "Drug": "drugs",
    "Chemical": "drugs",
    "Therapeutic_procedure": "procedures",
    "Diagnostic_procedure": "procedures",
    "Lab_value": "lab_values",
    "Biological_structure": "anatomy",
    # d4data model outputs
    "B-Disease": "diagnoses",
    "I-Disease": "diagnoses",
    "B-Chemical": "drugs",
    "I-Chemical": "drugs",
    "B-Gene": "genes",
    "I-Gene": "genes",
    "B-Species": "species",
    "I-Species": "species",
    "DISEASE": "diagnoses",
    "CHEMICAL": "drugs",
}


def extract_entities(text: str, max_length: int = 512) -> dict[str, list[dict]]:
    """
    Extract biomedical entities from text using NER.
    
    Args:
        text: Medical report text
        max_length: Max token length per chunk (model limit = 512)
    
    Returns:
        Dict with keys: diagnoses, drugs, symptoms, procedures, genes, lab_values
        Each value is a list of {entity, score, category} dicts.
    """
    result = {
        "diagnoses": [],
        "drugs": [],
        "symptoms": [],
        "procedures": [],
        "genes": [],
        "lab_values": [],
        "anatomy": [],
        "species": [],
    }

    pipe = _load_ner_model()
    if pipe is None:
        logger.warning("NER model unavailable — returning empty entities")
        return result

    try:
        # Chunk text so we don't exceed model's max length
        chunks = _chunk_text(text, max_chars=1500)

        seen = set()  # Deduplication

        for chunk in chunks:
            if not chunk.strip():
                continue

            try:
                entities = pipe(chunk)
            except Exception as e:
                logger.warning(f"NER failed on chunk: {e}")
                continue

            for ent in entities:
                word = ent.get("word", "").strip()
                # Clean up tokenizer artifacts
                word = word.replace("##", "").strip()
                if len(word) < 2:
                    continue

                score = float(ent.get("score", 0))
                if score < 0.5:  # Low confidence filter
                    continue

                entity_group = ent.get("entity_group", ent.get("entity", ""))
                category = _map_entity_group(entity_group)

                if not category:
                    continue

                # Dedup key
                dedup_key = f"{category}:{word.lower()}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                result[category].append({
                    "entity": word,
                    "score": round(score, 3),
                    "category": category,
                    "entity_group": entity_group,
                })

        # Sort each category by score descending
        for cat in result:
            result[cat].sort(key=lambda x: x["score"], reverse=True)

        logger.info(
            f"NER extracted: {sum(len(v) for v in result.values())} entities "
            f"({len(result['diagnoses'])} diagnoses, {len(result['drugs'])} drugs, "
            f"{len(result['symptoms'])} symptoms)"
        )

    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")

    return result


def _map_entity_group(group: str) -> str | None:
    """Map a model entity group to our category. Returns None if unmapped."""
    # Direct match
    if group in ENTITY_MAP:
        return ENTITY_MAP[group]

    # Partial match (handles B-, I- prefixes)
    group_clean = group.replace("B-", "").replace("I-", "").strip()
    for key, value in ENTITY_MAP.items():
        clean_key = key.replace("B-", "").replace("I-", "").strip()
        if clean_key.lower() == group_clean.lower():
            return value

    # Try case-insensitive
    for key, value in ENTITY_MAP.items():
        if key.lower() == group.lower():
            return value

    return None


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """
    Split text into chunks that fit within the model's token limit.
    Uses paragraph boundaries when possible.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 <= max_chars:
            current_chunk += para + "\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            # If single paragraph exceeds limit, split by sentences
            if len(para) > max_chars:
                sentences = para.replace(". ", ".\n").split("\n")
                sub_chunk = ""
                for sent in sentences:
                    if len(sub_chunk) + len(sent) + 1 <= max_chars:
                        sub_chunk += sent + " "
                    else:
                        if sub_chunk.strip():
                            chunks.append(sub_chunk.strip())
                        sub_chunk = sent + " "
                if sub_chunk.strip():
                    chunks.append(sub_chunk.strip())
                current_chunk = ""
            else:
                current_chunk = para + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def merge_with_regex_entities(
    ner_entities: dict[str, list[dict]],
    regex_entities: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge NER-extracted entities with regex-extracted structured data.
    Deduplicates, with regex taking priority for lab values (more precise).
    """
    merged = {
        "diagnoses": list(ner_entities.get("diagnoses", [])),
        "drugs": list(ner_entities.get("drugs", [])),
        "symptoms": list(ner_entities.get("symptoms", [])),
        "procedures": list(ner_entities.get("procedures", [])),
        "genes": list(ner_entities.get("genes", [])),
        "anatomy": list(ner_entities.get("anatomy", [])),
        # Regex provides these structured fields
        "lab_values": regex_entities.get("lab_values", []),
        "dates": regex_entities.get("dates", []),
        "dosages": regex_entities.get("dosages", []),
        "hospital_name": regex_entities.get("hospital_name"),
        "doctor_name": regex_entities.get("doctor_name"),
        "report_date": regex_entities.get("report_date"),
    }

    # Add any drugs from regex that NER missed
    ner_drug_names = {d["entity"].lower() for d in merged["drugs"]}
    for drug in regex_entities.get("drugs", []):
        name = drug if isinstance(drug, str) else drug.get("name", "")
        if name.lower() not in ner_drug_names:
            merged["drugs"].append({
                "entity": name,
                "score": 1.0,
                "category": "drugs",
                "source": "regex",
            })

    return merged
