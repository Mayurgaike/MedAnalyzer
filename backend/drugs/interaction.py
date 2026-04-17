"""
Drug Interaction Checker using OpenFDA API.

HONEST IMPLEMENTATION NOTE:
OpenFDA provides drug label information (warnings, interactions listed on the label)
but does NOT perform true pairwise drug interaction checks. This module:
  1. Fetches each drug's label warnings from OpenFDA
  2. Checks if Drug A's label mentions Drug B (and vice versa)
  3. Flags these as *potential* interactions based on label text
  
For confirmed clinical drug interactions, a specialized database like 
DrugBank or RxNorm would be needed.
"""

import logging
import asyncio
from functools import lru_cache

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache for FDA responses to avoid repeated API calls
_fda_cache: dict[str, dict | None] = {}


async def check_drug_interactions(drug_names: list[str]) -> dict:
    """
    Check for drug interactions across all drugs found in reports.
    
    Args:
        drug_names: List of drug names extracted from reports
    
    Returns:
        {
            "drug_labels": [{drug, warnings, interactions_text}],
            "potential_interactions": [{drug_pair, severity, warning_text, source}],
            "summary": str
        }
    """
    if not drug_names:
        return {"drug_labels": [], "potential_interactions": [], "summary": "No drugs to check"}

    # Deduplicate and normalize drug names
    unique_drugs = list({d.strip().lower(): d.strip() for d in drug_names if d.strip()}.values())

    logger.info(f"Checking drug interactions for: {unique_drugs}")

    # Step 1: Fetch label info for each drug
    drug_labels = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for drug in unique_drugs:
            label_info = await _fetch_drug_label(client, drug)
            if label_info:
                drug_labels.append(label_info)

    # Step 2: Cross-check drug pairs for mentions in each other's labels
    potential_interactions = _cross_check_interactions(unique_drugs, drug_labels)

    # Step 3: Build summary
    if potential_interactions:
        summary = f"Found {len(potential_interactions)} potential interaction(s) among {len(unique_drugs)} medications. Review recommended."
    else:
        summary = f"No known interactions found among {len(unique_drugs)} medications via OpenFDA labels."

    return {
        "drug_labels": drug_labels,
        "potential_interactions": potential_interactions,
        "summary": summary,
    }


def check_drug_interactions_sync(drug_names: list[str]) -> dict:
    """Synchronous wrapper for check_drug_interactions."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context (FastAPI)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, check_drug_interactions(drug_names))
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(check_drug_interactions(drug_names))
    except RuntimeError:
        return asyncio.run(check_drug_interactions(drug_names))


async def _fetch_drug_label(client: httpx.AsyncClient, drug_name: str) -> dict | None:
    """Fetch drug label information from OpenFDA API."""
    # Check cache first
    cache_key = drug_name.lower()
    if cache_key in _fda_cache:
        return _fda_cache[cache_key]

    try:
        # Try brand name first
        url = f"{settings.OPENFDA_BASE_URL}"
        params = {
            "search": f'openfda.brand_name:"{drug_name}"',
            "limit": 1,
        }

        response = await client.get(url, params=params)

        if response.status_code != 200:
            # Try generic name
            params["search"] = f'openfda.generic_name:"{drug_name}"'
            response = await client.get(url, params=params)

        if response.status_code != 200:
            logger.warning(f"OpenFDA returned {response.status_code} for {drug_name}")
            _fda_cache[cache_key] = None
            return None

        data = response.json()
        results = data.get("results", [])

        if not results:
            _fda_cache[cache_key] = None
            return None

        label = results[0]

        # Extract relevant sections
        warnings = _extract_section(label, "warnings")
        interactions = _extract_section(label, "drug_interactions")
        contraindications = _extract_section(label, "contraindications")
        adverse_reactions = _extract_section(label, "adverse_reactions")

        label_info = {
            "drug": drug_name,
            "brand_name": label.get("openfda", {}).get("brand_name", [drug_name])[0] if label.get("openfda") else drug_name,
            "generic_name": label.get("openfda", {}).get("generic_name", [""])[0] if label.get("openfda") else "",
            "warnings": warnings[:500] if warnings else "No warnings listed",
            "interactions_text": interactions[:500] if interactions else "No interaction data available",
            "contraindications": contraindications[:300] if contraindications else "",
            "has_interaction_data": bool(interactions),
        }

        _fda_cache[cache_key] = label_info
        return label_info

    except httpx.TimeoutException:
        logger.warning(f"OpenFDA timeout for {drug_name}")
        _fda_cache[cache_key] = None
        return None
    except Exception as e:
        logger.error(f"OpenFDA error for {drug_name}: {e}")
        _fda_cache[cache_key] = None
        return None


def _extract_section(label: dict, section: str) -> str:
    """Extract a text section from an FDA drug label."""
    value = label.get(section, [])
    if isinstance(value, list):
        return " ".join(value)
    return str(value) if value else ""


def _cross_check_interactions(
    drug_names: list[str], drug_labels: list[dict]
) -> list[dict]:
    """
    Cross-check drugs for mentions in each other's label text.
    This is a best-effort check — not a clinical interaction database.
    """
    interactions = []
    label_map = {dl["drug"].lower(): dl for dl in drug_labels}

    checked_pairs = set()

    for i, drug_a in enumerate(drug_names):
        for j, drug_b in enumerate(drug_names):
            if i >= j:
                continue

            pair_key = tuple(sorted([drug_a.lower(), drug_b.lower()]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            label_a = label_map.get(drug_a.lower())
            label_b = label_map.get(drug_b.lower())

            warning_text = ""
            severity = "safe"

            # Check if drug B is mentioned in drug A's interaction section
            if label_a and label_a.get("interactions_text"):
                if drug_b.lower() in label_a["interactions_text"].lower():
                    warning_text = f"{drug_a}'s label mentions {drug_b}: {label_a['interactions_text'][:200]}"
                    severity = "monitor"

            # Check reverse
            if label_b and label_b.get("interactions_text"):
                if drug_a.lower() in label_b["interactions_text"].lower():
                    text_b = f"{drug_b}'s label mentions {drug_a}: {label_b['interactions_text'][:200]}"
                    if warning_text:
                        warning_text += f" | {text_b}"
                        severity = "dangerous"  # Mentioned in both directions
                    else:
                        warning_text = text_b
                        severity = "monitor"

            # Check warnings/contraindications too
            if severity == "safe":
                for label_x, drug_y in [(label_a, drug_b), (label_b, drug_a)]:
                    if label_x:
                        all_text = f"{label_x.get('warnings', '')} {label_x.get('contraindications', '')}".lower()
                        if drug_y.lower() in all_text:
                            warning_text = f"{label_x['drug']}'s warnings mention {drug_y}"
                            severity = "monitor"
                            break

            if severity != "safe":
                interactions.append({
                    "drug_pair": [drug_a, drug_b],
                    "severity": severity,
                    "warning_text": warning_text[:500],
                    "source": "OpenFDA label cross-reference",
                })

    return interactions
