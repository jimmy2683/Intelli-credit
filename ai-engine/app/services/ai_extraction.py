import json
import logging
import asyncio
from typing import Any, List, Dict
from .gemini_service import call_gemini

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are a highly accurate Credit Analyst AI. Your task is to extract structured financial data and risk signals from a series of document chunks.

Input: A list of text chunks from an annual report or financial statement.
Output: A valid JSON object matching the schema below.

--- SCHEMA ---
{
  "revenue": {"value": float | null, "confidence": float, "source_ref": string},
  "EBITDA": {"value": float | null, "confidence": float, "source_ref": string},
  "PAT": {"value": float | null, "confidence": float, "source_ref": string},
  "total_debt": {"value": float | null, "confidence": float, "source_ref": string},
  "working_capital": {"value": float | null, "confidence": float, "source_ref": string},
  "current_ratio": {"value": float | null, "confidence": float, "source_ref": string},
  "dscr": {"value": float | null, "confidence": float, "source_ref": string},
  "risk_flags": [
    {
      "flag_type": string,
      "severity": "low" | "medium" | "high" | "critical",
      "description": string,
      "confidence": float,
      "evidence_refs": [string]
    }
  ],
  "entities": [
    {
      "name": string,
      "type": "person" | "company",
      "role": string,
      "source_ref": string
    }
  ],
  "qualitative_insights": {
    "contingent_liabilities": string[],
    "related_party_transactions": string[],
    "auditor_remarks": string[]
  }
}

--- INSTRUCTIONS ---
1. Values: Extract numeric values exactly. If the document says "₹14,548 Crore", the value is 14548 (assuming Cr as base unit for your internal logic, but here just extract the number). 
   IMPORTANT: Identify the unit (Crore, Lakh, Million) and normalize to absolute numbers if possible, or keep consistent. 
2. Confidence: 0.0 to 1.0 based on how clear the data is.
3. Source Reference: Provide the 'chunk_id' where the data was found.
4. Risk Flags: Identify any red flags like auditor qualifications, significant lawsuits, GST/bank mismatches mentioned, or high debt.
5. Qualitative: Summarize specific notes for auditor remarks, RPTs, etc.
6. If a field is not found, use null for value and 0.0 for confidence.

--- DOCUMENT CHUNKS ---
{chunks_text}

---
Return ONLY the JSON object. Do not include markdown formatting or explanations.
"""

def extract_with_ai(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Uses Gemini to extract structured facts from chunks."""
    # To avoid hitting context limits or being too slow, we'll take a subset of relevant chunks
    # or just the first N chunks if they are likely to contain the financial tables.
    # Usually, the first 50-100 chunks cover the main tables.
    
    # Format chunks for the prompt
    chunks_text = ""
    for ch in chunks[:60]: # Limit to first 60 chunks for now
        chunks_text += f"[ID: {ch.get('chunk_id')}] {ch.get('text', '')}\n\n"
    
    prompt = EXTRACTION_PROMPT.format(chunks_text=chunks_text)
    
    try:
        response_text = call_gemini(prompt, config={"response_mime_type": "application/json"})
        # Remove any markdown code block wrap if it exists (Gemini sometimes adds it even if told not to)
        clean_json = response_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        result = json.loads(clean_json)
        return result
    except Exception as e:
        logger.error(f"AI extraction failed: {e}")
        return None

def merge_ai_results(regex_results: Dict[str, Any], ai_results: Dict[str, Any]) -> Dict[str, Any]:
    """Merges AI results with regex results, favoring AI for higher confidence."""
    if not ai_results:
        return regex_results
    
    merged = regex_results.copy()
    
    # Fields to potentially overwrite
    fields = ["revenue", "EBITDA", "PAT", "total_debt", "working_capital", "current_ratio", "dscr"]
    
    for f in fields:
        ai_val = ai_results.get(f)
        if ai_val and ai_val.get("confidence", 0) > merged.get(f, {}).get("confidence", 0):
            merged[f] = ai_val
            
    # Qualitative fields
    qual_map = {
        "contingent_liabilities": "contingent_liabilities",
        "related_party_transactions": "related_party_transactions",
        "auditor_remarks": "auditor_remarks"
    }
    
    ai_qual = ai_results.get("qualitative_insights", {})
    for k, merged_k in qual_map.items():
        if ai_qual.get(k):
            # If AI found something, use it (maybe append or replace)
            # For now, let's just let AI override if confidence is high (AI doesn't have confidence for these yet in schema but we can assume high if returned)
            merged[merged_k] = {
                "value": ai_qual[k],
                "confidence": 0.85,
                "source_ref": "ai_inference" # Ideally AI would provide this
            }
            
    # Entities
    if ai_results.get("entities"):
        merged["extracted_entities"] = ai_results["entities"]
        
    return merged
