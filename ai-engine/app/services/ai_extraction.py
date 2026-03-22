import json
import logging
import re
from typing import Any, List, Dict, Optional
from .mistral_service import call_mistral

logger = logging.getLogger(__name__)

# FIX: Single authoritative constant for the relevance-selection limit.
# Previously get_relevant_chunks() defaulted to 80 but was called with limit=100,
# creating a confusing mismatch. Use 100 everywhere.
_CHUNK_SELECTION_LIMIT = 100


def get_expert_prompt(doc_type: str, custom_schema: Optional[Dict[str, Any]] = None) -> str:
    if custom_schema:
        schema_str = json.dumps(custom_schema, indent=2)
    else:
        if doc_type in ["annual_report", "financial_statement"]:
            schema_str = """{
  "fields": {
    "revenue": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "EBITDA": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "PAT": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "total_debt": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "current_ratio": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "dscr": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"}
  }
}"""
        elif doc_type == "alm":
            schema_str = """{
  "fields": {
    "short_term_assets": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "short_term_liabilities": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "mismatch_1yr": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "mismatch_3yr": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"}
  }
}"""
        elif doc_type == "shareholding_pattern":
            schema_str = """{
  "fields": {
    "promoter_percentage": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "pledged_shares": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "institutional_holding": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"}
  }
}"""
        elif doc_type == "borrowing_profile":
            schema_str = """{
  "fields": {
    "total_borrowing": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "top_lender_exposure": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "avg_interest_rate": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"}
  }
}"""
        elif doc_type == "portfolio_cuts":
            schema_str = """{
  "fields": {
    "GNPA": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "NNPA": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"},
    "sector_concentration": {"value": "float | null", "confidence": "0.0-1.0", "source_ref": "string"}
  }
}"""
        else:
            schema_str = """{
  "fields": {}
}"""

    # FIX: Build the prompt with simple string concatenation instead of mixing
    # f-strings and manual .replace(). This avoids confusion and makes it clear
    # that CHUNKS_PLACEHOLDER is a runtime substitution token, not a Python variable.
    #
    # The schema_str and doc_type are injected at build time; the actual chunk text
    # is injected later via str.replace() in extract_with_ai().
    prompt = (
        "You are a financial document extraction engine.\n\n"
        "You MUST extract structured data strictly according to the schema.\n\n"
        "INPUT:\n"
        f"- Document Type: {doc_type}\n"
        f"- Schema: {schema_str}\n"
        "- Text Chunk: __CHUNKS_TEXT__\n\n"
        "INSTRUCTIONS:\n\n"
        "1. Extract ONLY fields defined in schema\n"
        "2. For each field:\n"
        "   - find exact match in text\n"
        "   - assign value\n"
        "   - assign confidence:\n"
        "     - 0.9+ → exact match\n"
        "     - 0.7–0.9 → strong contextual match\n"
        "     - <0.7 → weak (prefer null)\n"
        "3. Assign source_ref as the chunk id shown in [ID: ...] prefix\n\n"
        "4. If field not present → value = null, confidence = 0.0\n\n"
        "5. Do NOT:\n"
        "   - infer\n"
        "   - calculate\n"
        "   - assume\n"
        "   - summarize (unless instructed for text arrays below)\n\n"
        "6. Ensure output is valid JSON\n\n"
        "GLOBAL RULES:\n"
        "1. STRICT JSON OUTPUT\n"
        "- Output ONLY valid JSON\n"
        "- No explanations, no text outside JSON\n"
        "- No markdown\n"
        "- No comments\n\n"
        "2. SCHEMA COMPLIANCE\n"
        "- Follow the provided schema EXACTLY\n"
        "- Do not add extra fields\n"
        "- Do not omit required fields\n"
        "- Maintain exact field names\n\n"
        "3. NULL vs ZERO HANDLING\n"
        "- If value explicitly stated as 0, return 0.0\n"
        "- If value not found or uncertain, return null\n"
        "- NEVER guess values\n\n"
        "4. NO HALLUCINATION\n"
        "- Extract only from given text\n"
        "- Do not infer missing values\n"
        "- Do not use prior knowledge\n\n"
        "5. CONFIDENCE SCORING\n"
        "- Each field must include value, confidence (0.0-1.0), and source_ref (chunk id)\n\n"
        "6. FIELD MAPPING RULES\n"
        "- Map based on keywords ONLY (e.g. 'Profit After Tax' -> PAT). NEVER swap fields.\n\n"
        "7. NUMBER NORMALIZATION (CRITICAL)\n"
        "- Convert all values to absolute float values.\n"
        "- If text says '₹ 2.5 Cr' or '2.5 Crores' or '250 Lakhs', multiply and convert to absolute "
        "(e.g., 25000000.0). 'crore' * 1e7, 'lakh' * 1e5.\n"
        "- Remove currency symbols.\n\n"
        "8. TEXT ARRAYS & SUMMARIZATION\n"
        "- If schema expects a list of strings (e.g. auditor_remarks, contingent_liabilities, "
        "director_promoter_mentions), extract key CONCISE facts.\n"
        "- DO NOT copy-paste raw text chunks. Keep each string summary under 100 characters.\n"
        "- If no matching facts are found, return an empty list [], not null.\n\n"
        "FAILURE HANDLING:\n"
        "If text is irrelevant or schema fields not found:\n"
        "Return all fields = null, confidence = 0.0\n\n"
        "Ensure about lacs or crores are converted to absolute values.\n\n"
        "VALIDATION:\n"
        "Before returning, ensure JSON is valid, ensure all schema fields exist, ensure no extra keys.\n\n"
        "This is a STRICT extraction task. Accuracy and correctness are more important than completeness.\n"
        "Return ONLY JSON.\n"
    )
    return prompt


def extract_json_safely(text: str) -> dict:
    """Robust JSON extractor that finds the first JSON block and parses it."""
    text = text.strip()

    # Remove markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text)
        text = text.rstrip("`").strip()

    # Find outermost JSON object
    start_idx = text.find('{')
    end_idx = text.rfind('}')

    if start_idx == -1 or end_idx == -1:
        raise ValueError(f"No JSON object found in response. Raw text: {text[:200]}")

    json_str = text[start_idx:end_idx + 1]
    json_str = json_str.replace('\r', ' ')

    return json.loads(json_str)


def get_relevant_chunks(chunks: List[Dict[str, Any]], limit: int = _CHUNK_SELECTION_LIMIT) -> List[Dict[str, Any]]:
    """Smart selection of chunks based on financial keywords."""
    keywords = [
        r"balance\s*sheet", r"profit\s*&\s*loss", r"cash\s*flow",
        r"auditor's\s*report", r"directors'\s*report", r"financial\s*statement",
        r"notes\s*to\s*accounts", r"related\s*party", r"contingent\s*liability",
        r"revenue\s*from\s*operations", r"borrowings",
    ]

    scored_chunks = []
    for i, ch in enumerate(chunks):
        text = (ch.get("text") or "").lower()
        score = sum(1 for kw in keywords if re.search(kw, text))
        scored_chunks.append({"index": i, "score": score, "chunk": ch})

    top_scored = sorted(scored_chunks, key=lambda x: x["score"], reverse=True)
    selected_indices: set[int] = set()

    # Always include first few for document header / identity
    for i in range(min(5, len(chunks))):
        selected_indices.add(i)

    # Include top scored chunks and immediate neighbours
    for item in top_scored:
        if len(selected_indices) >= limit:
            break
        if item["score"] > 0:
            idx = int(item["index"])
            for neighbor in range(max(0, idx - 2), min(len(chunks), idx + 3)):
                if len(selected_indices) < limit:
                    selected_indices.add(neighbor)
                else:
                    break

    # Fill remaining slots sequentially
    for i in range(len(chunks)):
        if len(selected_indices) >= limit:
            break
        selected_indices.add(i)

    final_indices = sorted(list(selected_indices))
    return [chunks[i] for i in final_indices]


def extract_with_ai(
    chunks: List[Dict[str, Any]],
    doc_type: str = "annual_report",
    custom_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Uses Mistral to extract structured facts using multi-type expert prompts."""
    relevant_chunks = get_relevant_chunks(chunks, limit=_CHUNK_SELECTION_LIMIT)

    chunks_text = ""
    for ch in relevant_chunks:
        chunks_text += f"[ID: {ch.get('chunk_id')}] {ch.get('text', '')}\n\n"

    # FIX: Use the sentinel token __CHUNKS_TEXT__ so there is zero ambiguity
    # about what is being replaced, and so curly braces inside financial text
    # cannot accidentally collide with the substitution logic.
    prompt = get_expert_prompt(doc_type, custom_schema)
    prompt = prompt.replace("__CHUNKS_TEXT__", chunks_text)

    response_text = ""
    try:
        response_text = call_mistral(prompt, response_format={"type": "json_object"})
        logger.info("AI RAW RESPONSE (top 300 chars): %s", response_text[:300])
        result = extract_json_safely(response_text)

        # Unwrap "fields" wrapper if model strictly followed schema format
        if isinstance(result, dict) and "fields" in result and isinstance(result["fields"], dict):
            logger.info("Unwrapping 'fields' from AI response.")
            unwrapped = result["fields"]
            for k, v in result.items():
                if k != "fields" and k not in unwrapped:
                    unwrapped[k] = v
            result = unwrapped

        logger.info(
            "AI PARSED KEYS: %s",
            list(result.keys()) if isinstance(result, dict) else "NOT A DICT",
        )
        return result
    except Exception as e:
        logger.error("AI extraction internal failure: %s: %s", type(e).__name__, e)
        logger.error("RAW RESPONSE FULL:\n%s", response_text)
        return None


def merge_ai_results(regex_results: Dict[str, Any], ai_results: Dict[str, Any]) -> Dict[str, Any]:
    """Merges AI results into regex/accumulated results with type safety."""
    if not ai_results or not isinstance(ai_results, dict):
        return regex_results

    merged = regex_results.copy()

    # Keys handled separately — never clobber via field merge loop
    special_keys = {
        "qualitative_insights", "requires_human_review", "review_reason",
        "entities", "risk_flags", "extracted_data",
    }

    for k, ai_val in ai_results.items():
        if k in special_keys:
            continue

        if isinstance(ai_val, dict):
            # Keep the higher-confidence result
            existing = merged.get(k)
            existing_conf = existing.get("confidence", 0) if isinstance(existing, dict) else 0
            ai_conf = ai_val.get("confidence", 0)
            if ai_conf >= existing_conf:
                merged[k] = ai_val
        elif ai_val is not None:
            # Flat LLM response fallback
            if k not in merged or not isinstance(merged.get(k), dict):
                merged[k] = {"value": ai_val, "confidence": 0.7, "source_ref": "ai_inference"}

    # Qualitative insights block
    ai_qual = ai_results.get("qualitative_insights", {})
    if isinstance(ai_qual, dict):
        for k in ["contingent_liabilities", "related_party_transactions", "auditor_remarks"]:
            val = ai_qual.get(k)
            if val:
                merged[k] = {"value": val, "confidence": 0.85, "source_ref": "ai_inference"}

    # Human escalation flag
    if ai_results.get("requires_human_review"):
        merged["requires_human_review"] = True
        merged["review_reason"] = ai_results.get("review_reason")

    return merged