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
from .identity_resolver import resolve_identity

logger = logging.getLogger(__name__)

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "../data"))


def _normalize_facts(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize extracted facts for API: flatten value/confidence/source_ref into
    a structure suitable for JSON schema (with optional _confidence and _source_ref).
    """
    out: dict[str, Any] = {}
    for k, v in raw.items():
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

    FIX: Now always returns 'parsed_text_chunks' so extract_service.py doesn't KeyError.
    FIX: Blocks pipeline on critical company identity mismatch as per spec.
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
            "doc_type": _to_dict(m).get("user_confirmed_type") or _to_dict(m).get("doc_type"),
        }
        for m in (file_meta if isinstance(file_meta, list) else [])
    ]

    if file_meta_list:
        logger.info("file_meta_list: %s", file_meta_list)
        chunks, parse_errors = parse_documents(file_meta_list, case_id)
        if parse_errors:
            logger.warning("Parse errors: %s", parse_errors)
        parsed_chunks = chunks

        if parsed_chunks:
            # ----------------------------------------------------------------
            # 0. Identity Resolution (First-class check)
            # ----------------------------------------------------------------
            target_company = "Unknown Company"
            if payload.company_details and payload.company_details.company_name:
                target_company = payload.company_details.company_name

            identity = resolve_identity(parsed_chunks, target_company)

            is_mismatch = identity.get("is_mismatch", False)
            requires_review = identity.get("requires_human_review", False)

            if is_mismatch or requires_review:
                logger.warning("Identity issue detected: %s", identity.get("reason"))
                flag_type = "company_identity_mismatch" if is_mismatch else "identity_uncertainty"
                severity = "critical" if is_mismatch else "high"
                risk_flags.append({
                    "flag_type": flag_type,
                    "severity": severity,
                    "description": identity.get("reason", "Company identity mismatch or uncertainty detected."),
                    "confidence": identity.get("confidence", 0.5),
                    "evidence_refs": ["ai_identity_resolver"],
                })

            # FIX: BLOCK pipeline on critical mismatch as per spec.
            # A confirmed mismatch (match_score < 0.80) means we cannot trust
            # ANY extracted facts from this document — return early with empty facts
            # and only the identity flag so the frontend can surface the issue.
            if is_mismatch:
                logger.error(
                    "Pipeline BLOCKED — confirmed company mismatch for case %s. "
                    "Detected: '%s' vs Target: '%s'",
                    case_id,
                    identity.get("detected_company_name"),
                    target_company,
                )
                output = {
                    "extracted_facts": _empty_facts(),
                    "risk_flags": risk_flags,
                    "parsed_text_chunks": parsed_chunks,   # Still return chunks for UI preview
                }
                _save_output(parsed_dir, output)
                return output

            # ----------------------------------------------------------------
            # 1. Standard regex-based extraction
            # ----------------------------------------------------------------
            raw_facts = extract_structured(parsed_chunks)

            # ----------------------------------------------------------------
            # 2. AI-driven extraction (per doc_type expert prompt)
            # ----------------------------------------------------------------
            try:
                schema = payload.extraction_schema
                ai_facts_merged: dict[str, Any] = {}
                ai_risk_flags: list[dict[str, Any]] = []

                # Group chunks by doc_type to apply expert prompts
                chunks_by_type: dict[str, list[dict]] = {}
                for ch in parsed_chunks:
                    dt = ch.get("doc_type", "annual_report")
                    chunks_by_type.setdefault(dt, []).append(ch)

                for dt, type_chunks in chunks_by_type.items():
                    if dt == "unknown" and len(chunks_by_type) > 1:
                        continue  # skip unknown if we have classified ones

                    type_facts = extract_with_ai(type_chunks, doc_type=dt, custom_schema=schema)
                    if not type_facts:
                        continue

                    # FIX: Harvest AI risk_flags BEFORE merging (merge_ai_results
                    # deliberately skips "risk_flags" via special_keys).
                    if isinstance(type_facts.get("risk_flags"), list):
                        ai_risk_flags.extend(type_facts["risk_flags"])

                    ai_facts_merged = merge_ai_results(ai_facts_merged, type_facts)

                if ai_facts_merged:
                    raw_facts = merge_ai_results(raw_facts, ai_facts_merged)

                    if ai_facts_merged.get("requires_human_review"):
                        raw_facts["requires_human_review"] = True
                        raw_facts["review_reason"] = ai_facts_merged.get("review_reason")

                # Accumulate AI-sourced risk flags separately
                risk_flags.extend(ai_risk_flags)

            except Exception as e:
                logger.warning("AI extraction failed: %s", e)

            extracted_facts = _normalize_facts(raw_facts)

            # ----------------------------------------------------------------
            # 3. Contradiction detection + additional rule-based flags
            # ----------------------------------------------------------------
            contradiction_flags = detect_contradictions(
                raw_facts,
                payload.officer_notes,
                parsed_chunks,
                file_meta_list,
            )
            all_flags = risk_flags + generate_additional_flags(raw_facts, contradiction_flags)
            risk_flags = all_flags

        else:
            extracted_facts = _empty_facts()
    else:
        extracted_facts = _empty_facts()

    output = {
        "extracted_facts": extracted_facts,
        "risk_flags": risk_flags,
        # FIX: Always include parsed_text_chunks so callers don't KeyError.
        "parsed_text_chunks": parsed_chunks,
    }

    _save_output(parsed_dir, output)
    return output


def _save_output(parsed_dir: Path, output: dict[str, Any]) -> None:
    """Persist extraction output to disk (best-effort)."""
    out_path = parsed_dir / "extraction_output.json"
    try:
        with open(out_path, "w") as f:
            # parsed_text_chunks can be large; exclude from on-disk snapshot if needed
            json.dump(output, f, indent=2, default=str)
    except OSError as e:
        logger.warning("Could not save extraction output: %s", e)


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
    out["legal_mentions"] = []
    out["director_promoter_mentions"] = []
    out["bank_gst_mismatch_clues"] = []
    return out