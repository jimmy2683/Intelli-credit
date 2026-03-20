import json
import logging
import re
from typing import Any, List, Dict
from .mistral_service import call_mistral

logger = logging.getLogger(__name__)

# NOTE: Structural curly braces in the prompt must be ESCAPED as {{ and }} 
# because we use .format(chunks_text=...) on this string.
EXTRACTION_PROMPT = """
You are a highly accurate Credit Analyst AI. Your task is to extract structured financial data and risk signals from a series of document chunks.

Input: A list of text chunks from an annual report or financial statement.
Output: A valid JSON object matching the schema below.

--- SCHEMA ---
{{
  "revenue": {{"value": float | null, "confidence": float, "source_ref": string}},
  "EBITDA": {{"value": float | null, "confidence": float, "source_ref": string}},
  "PAT": {{"value": float | null, "confidence": float, "source_ref": string}},
  "total_debt": {{"value": float | null, "confidence": float, "source_ref": string}},
  "working_capital": {{"value": float | null, "confidence": float, "source_ref": string}},
  "current_ratio": {{"value": float | null, "confidence": float, "source_ref": string}},
  "dscr": {{"value": float | null, "confidence": float, "source_ref": string}},
  "risk_flags": [
    {{
      "flag_type": string,
      "severity": "low" | "medium" | "high" | "critical",
      "description": string,
      "confidence": float,
      "evidence_refs": [string]
    }}
  ],
  "entities": [
    {{
      "name": string,
      "type": "person" | "company",
      "role": string,
      "source_ref": string
    }}
  ],
  "qualitative_insights": {{
    "contingent_liabilities": string[],
    "related_party_transactions": string[],
    "auditor_remarks": string[]
  }}
}}

--- INSTRUCTIONS ---
1. Values: Extract numeric values as ABSOLUTE NUMBERS (float). 
   - If unit is " Crore" (Cr): Multiply by 10,000,000 (e.g., 48.5 Cr -> 485000000).
   - If unit is " Lakh" (L): Multiply by 100,000 (e.g., 9.2 L -> 920000).
   - If unit is " Million": Multiply by 1,000,000 (e.g., 5 M -> 5000000).
   - ALWAYS output the full absolute number with all zeros.
2. Confidence: Provide a score from 0.0 to 1.0 based on how explicitly the data is stated.
3. Source Reference: Provide the 'chunk_id' where the data was found.
4. Qualitative: Summarize specific notes for auditor remarks, related party transactions, and contingent liabilities.
5. If a field is not found, use null or an empty list, and 0.0 for confidence.
6. Return ONLY the JSON object. Do not include markdown formatting or explanations.
7. Ensure all keys in the JSON exactly match the schema above, with no leading or trailing whitespace.

--- DOCUMENT CHUNKS ---
{chunks_text}

---
Return ONLY the JSON object.
"""

def extract_json_safely(text: str) -> dict:
    """Robust JSON extractor that finds the first JSON block and parses it."""
    text = text.strip()
    
    # Remove markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text)
        text = text.rstrip("```").strip()
    
    # Try to find the first '{' and the last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    
    if start_idx == -1 or end_idx == -1:
        raise ValueError(f"No JSON object found in response. Raw text: {text[:100]}...")
        
    json_str = text[start_idx:end_idx + 1]
    
    # Clean up common LLM JSON artifacts
    json_str = json_str.replace('\n', ' ').replace('\r', ' ')
    
    return json.loads(json_str)

def get_relevant_chunks(chunks: List[Dict[str, Any]], limit: int = 80) -> List[Dict[str, Any]]:
    """Smart selection of chunks based on financial keywords."""
    keywords = [
        r"balance\s*sheet", r"profit\s*&\s*loss", r"cash\s*flow", 
        r"auditor's\s*report", r"directors'\s*report", r"financial\s*statement",
        r"notes\s*to\s*accounts", r"related\s*party", r"contingent\s*liability",
        r"revenue\s*from\s*operations", r"borrowings"
    ]
    
    scored_chunks = []
    for i, ch in enumerate(chunks):
        text = (ch.get("text") or "").lower()
        score = sum(1 for kw in keywords if re.search(kw, text))
        scored_chunks.append({"index": i, "score": score, "chunk": ch})
    
    top_scored = sorted(scored_chunks, key=lambda x: x["score"], reverse=True)
    selected_indices = set()
    
    # Always include first few
    for i in range(min(5, len(chunks))):
        selected_indices.add(i)
        
    # Include top scored chunks and their immediate neighbors
    for item in top_scored:
        if len(selected_indices) >= limit:
            break
        if item["score"] > 0:
            idx = item["index"]
            for neighbor in range(max(0, idx - 2), min(len(chunks), idx + 3)):
                if len(selected_indices) < limit:
                    selected_indices.add(neighbor)
                else:
                    break
                    
    # Fill remaining with incremental chunks if not enough
    for i in range(len(chunks)):
        if len(selected_indices) >= limit:
            break
        selected_indices.add(i)
        
    final_indices = sorted(list(selected_indices))
    return [chunks[i] for i in final_indices]

def extract_with_ai(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Uses Mistral to extract structured facts with better error handling."""
    relevant_chunks = get_relevant_chunks(chunks, limit=100)
    
    chunks_text = ""
    for ch in relevant_chunks:
        chunks_text += f"[ID: {ch.get('chunk_id')}] {ch.get('text', '')}\n\n"
    
    # CRITICAL: We format chunks_text into the prompt. 
    # Schema braces MUST be escaped in EXTRACTION_PROMPT.
    try:
        prompt = EXTRACTION_PROMPT.format(chunks_text=chunks_text)
    except KeyError as ek:
        logger.error(f"Prompt formatting failed. Did you forget to escape curly braces? {ek}")
        # Fallback to simple concatenation if formatting fails
        prompt = EXTRACTION_PROMPT.replace("{chunks_text}", chunks_text)

    response_text = ""
    try:
        response_text = call_mistral(prompt, response_format={"type": "json_object"})
        logger.info(f"AI RAW RESPONSE (top 200 chars): {response_text[:200]}")
        result = extract_json_safely(response_text)
        logger.info(f"AI PARSED KEYS: {list(result.keys()) if isinstance(result, dict) else 'NOT A DICT'}")
        return result
    except Exception as e:
        logger.error(f"AI extraction internal failure: {type(e).__name__}: {e}")
        logger.error(f"RAW RESPONSE FULL:\n{response_text}")
        return None

def merge_ai_results(regex_results: Dict[str, Any], ai_results: Dict[str, Any]) -> Dict[str, Any]:
    """Merges AI results into regex results with type safety."""
    if not ai_results or not isinstance(ai_results, dict):
        return regex_results
    
    merged = regex_results.copy()
    fields = ["revenue", "EBITDA", "PAT", "total_debt", "working_capital", "current_ratio", "dscr"]
    
    for f in fields:
        ai_val = ai_results.get(f)
        # Handle both structured (dict) and flat (value) responses from LLM
        if isinstance(ai_val, dict):
            conf = ai_val.get("confidence", 0)
            if conf > merged.get(f, {}).get("confidence", 0):
                merged[f] = ai_val
        elif ai_val is not None:
            # Fallback for flat LLM response
            merged[f] = {"value": ai_val, "confidence": 0.7, "source_ref": "ai_inference"}
            
    # Qualitative insights
    ai_qual = ai_results.get("qualitative_insights", {})
    if isinstance(ai_qual, dict):
        for k in ["contingent_liabilities", "related_party_transactions", "auditor_remarks"]:
            val = ai_qual.get(k)
            if val:
                merged[k] = {"value": val, "confidence": 0.85, "source_ref": "ai_inference"}
            
    # Entities
    if ai_results.get("entities"):
        merged["extracted_entities"] = ai_results["entities"]
        
    return merged