import logging
from typing import List, Dict, Any
from .mistral_service import call_mistral
from .ai_extraction import extract_json_safely

logger = logging.getLogger(__name__)

IDENTITY_PROMPT = """
You are a document verification specialist. Your task is to determine if the provided document chunks belong to the target company.

Target Company: {target_company}

Input: A list of text chunks from the first pages of a document.
Output: A JSON object with the following fields:
{{
  "detected_company_name": "string — exact legal name from document header/letterhead/title",
  "gstin": "string | null — 15-char GSTIN if found, else null",
  "cin": "string | null — 21-char CIN (Company Identification Number) if found, else null",
  "match_score": "float 0.0-1.0 — how closely detected_company_name matches Target Company",
  "is_mismatch": "boolean",
  "confidence": "float 0.0-1.0 — how confident you are in the detected_company_name",
  "reason": "string — short explanation of match/mismatch decision",
  "requires_human_review": "boolean"
}}

Matching Criteria:
1. Extract the EXACT legal entity name from document headers, letterhead, or title page.
2. Compare with Target Company using fuzzy/semantic matching:
   - Exact match → match_score 1.0
   - Abbreviated vs. full name (e.g. "Google" vs "Google India Pvt Ltd") → match_score 0.9, is_mismatch: false
   - Same root company, different subsidiary → match_score 0.75, is_mismatch: false, requires_human_review: true
   - Completely different company → match_score < 0.4, is_mismatch: true
3. If match_score < 0.80 → is_mismatch: true
4. If document has no company name mentions → match_score: 0.0, requires_human_review: true
5. If your confidence in the detected name is < 0.70 → requires_human_review: true

GSTIN Format: 2-digit state code + 10-char PAN + 1 digit + Z + 1 alphanumeric = 15 chars total.
CIN Format: Letter + 5 digits + 2 letters + 4 digits + 3 letters + 6 digits = 21 chars.

--- DOCUMENT CHUNKS ---
{chunks_text}

Return ONLY the JSON object. No explanations outside the JSON.
"""


def resolve_identity(chunks: List[Dict[str, Any]], target_company: str) -> Dict[str, Any]:
    """
    Verify if the document chunks belong to the target company.

    FIX #D1: Default match_score was 1.0 when key was missing — this silently
             approved mismatched documents. Changed to 0.0 (conservative/fail-safe).

    FIX #D2: Added per-document grouping so multi-document uploads don't blur
             identity signals from different files across the first 10 chunks.
             Falls back to global first-10 if chunks have no file_name metadata.
    """
    if not chunks:
        return _error_result("No chunks provided for identity verification.")

    # FIX #D2: Group chunks by file and sample the first 5 from each document.
    # For most uploads this still collapses to chunks[:10], but correctly handles
    # multi-doc payloads by ensuring each doc contributes to the identity sample.
    file_groups: dict[str, list[dict]] = {}
    for ch in chunks:
        fname = ch.get("file_name", "__unknown__")
        file_groups.setdefault(fname, []).append(ch)

    identity_chunks: list[dict] = []
    for fname, doc_chunks in file_groups.items():
        # Take first 5 chunks (cover page / headers) from each document
        identity_chunks.extend(doc_chunks[:5])
        if len(identity_chunks) >= 15:
            break

    chunks_text = ""
    for ch in identity_chunks:
        fname_label = ch.get("file_name", "")
        chunks_text += f"[FILE: {fname_label}] {str(ch.get('text', ''))[:800]}\n\n"

    prompt = IDENTITY_PROMPT.format(
        target_company=target_company,
        chunks_text=chunks_text,
    )

    try:
        response = call_mistral(prompt, response_format={"type": "json_object"})
        result = extract_json_safely(response)

        # FIX #D1: Default to 0.0 (fail-safe), not 1.0 (trust-by-default)
        score = float(result.get("match_score", 0.0))
        result["match_score"] = score

        # Enforce mismatch threshold
        if score < 0.80:
            result["is_mismatch"] = True
            result["requires_human_review"] = True

        # Enforce low-confidence review flag
        confidence = float(result.get("confidence", 0.0))
        if confidence < 0.70:
            result["requires_human_review"] = True

        logger.info(
            "Identity Resolution | target='%s' detected='%s' match=%.2f mismatch=%s confidence=%.2f",
            target_company,
            result.get("detected_company_name"),
            score,
            result.get("is_mismatch"),
            confidence,
        )
        return result

    except Exception as e:
        logger.error("Identity resolution failed: %s", e)
        return _error_result(f"System error during identity resolution: {e}")


def _error_result(reason: str) -> Dict[str, Any]:
    """Conservative fail-safe result for identity resolution errors."""
    return {
        "detected_company_name": "Unknown",
        "gstin": None,
        "cin": None,
        # FIX #D1: match_score 0.0 on error — never 1.0
        "match_score": 0.0,
        "is_mismatch": True,
        "confidence": 0.0,
        "reason": reason,
        "requires_human_review": True,
    }