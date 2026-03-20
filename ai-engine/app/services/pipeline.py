"""
Orchestration pipeline: parse documents, extract facts, detect contradictions, generate risk flags.
Saves output to data/parsed/{case_id}/.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.contracts import PipelineInput

from .contradiction_detector import detect_contradictions
from .document_parser import parse_documents
from .extraction import extract_structured
from .risk_flags import generate_additional_flags
from .ai_extraction import extract_with_ai, merge_ai_results

logger = logging.getLogger(__name__)

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "../data"))


def _normalize_facts(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize extracted facts for API: flatten value/confidence/source_ref into
    a structure suitable for JSON schema (with optional _confidence and _source_ref).
    """
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k == "document_sources":
            out[k] = v
            continue
        if k == "extracted_entities":
            out[k] = v
            continue
        if isinstance(v, dict) and "value" in v:
            val = v["value"]
            conf = v.get("confidence", 0)
            ref = v.get("source_ref", "")
            out[k] = val
            out[f"{k}_confidence"] = conf
            out[f"{k}_source_ref"] = ref
        else:
            out[k] = v
    return out


def run_extraction_pipeline(payload: PipelineInput) -> dict[str, Any]:
    """
    Full pipeline: parse docs -> extract -> detect contradictions -> risk flags.
    Saves to data/parsed/{case_id}/ and returns extracted_facts, parsed_text_chunks, risk_flags.
    """
    case_id = payload.case_id or "unknown"
    file_meta = payload.uploaded_file_metadata or []

    parsed_dir = DATA_ROOT / "parsed" / case_id
    parsed_dir.mkdir(parents=True, exist_ok=True)

    parsed_chunks: list[dict[str, Any]] = []
    extracted_facts: dict[str, Any] = {}
    risk_flags: list[dict[str, Any]] = []

    def _to_dict(m: Any) -> dict:
        if hasattr(m, "model_dump"):
            return m.model_dump()
        if isinstance(m, dict):
            return m
        return {}

    file_meta_list = [
        {
            "file_name": _to_dict(m).get("file_name", ""),
            "file_path": _to_dict(m).get("file_path"),
            "doc_type": _to_dict(m).get("doc_type"),
        }
        for m in (file_meta if isinstance(file_meta, list) else [])
    ]

    if file_meta_list:
        print("file_meta_list", file_meta_list)
        chunks, parse_errors = parse_documents(file_meta_list, case_id)
        if parse_errors:
            logger.warning("Parse errors: %s", parse_errors)
        parsed_chunks = chunks

        if parsed_chunks:
            # 1. Standard regex-based extraction
            raw_facts = extract_structured(parsed_chunks)
            
            # 2. AI-driven extraction
            try:
                ai_facts = extract_with_ai(parsed_chunks)
                if ai_facts:
                    raw_facts = merge_ai_results(raw_facts, ai_facts)
                    
                    # If AI returned risk_flags, use them
                    if ai_facts.get("risk_flags"):
                        risk_flags.extend(ai_facts["risk_flags"])
            except Exception as e:
                logger.warning(f"AI extraction failed: {e}")

            extracted_facts = _normalize_facts(raw_facts)

            contradiction_flags = detect_contradictions(
                raw_facts,
                payload.officer_notes,
                parsed_chunks,
                file_meta_list,
            )
            # Combine regex-detected flags with AI flags
            all_flags = risk_flags + generate_additional_flags(raw_facts, contradiction_flags)
            # Deduplicate or process flags if needed
            risk_flags = all_flags
        else:
            extracted_facts = _empty_facts()
    else:
        extracted_facts = _empty_facts()

    output = {
        "extracted_facts": extracted_facts,
        "parsed_text_chunks": [
            {"chunk_id": c.get("chunk_id"), "text": (c.get("text", ""))[:500], "file_name": c.get("file_name")}
            for c in parsed_chunks[:50]
        ],
        "risk_flags": risk_flags,
    }

    out_path = parsed_dir / "extraction_output.json"
    try:
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2, default=str)
    except OSError as e:
        logger.warning("Could not save extraction output: %s", e)

    return output


def _empty_facts() -> dict[str, Any]:
    base = ["revenue", "EBITDA", "PAT", "total_debt", "working_capital", "current_ratio", "dscr"]
    out: dict[str, Any] = {}
    for f in base:
        out[f] = None
        out[f"{f}_confidence"] = 0.0
        out[f"{f}_source_ref"] = ""
    out["contingent_liabilities"] = []
    out["related_party_transactions"] = []
    out["auditor_remarks"] = []
    out["extracted_entities"] = []
    out["document_sources"] = []
    out["legal_mentions"] = []
    out["director_promoter_mentions"] = []
    out["bank_gst_mismatch_clues"] = []
    return out
