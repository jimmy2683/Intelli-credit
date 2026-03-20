"""
Research service: runs contradiction detection, risk flag generation, and secondary research agent.
"""
from __future__ import annotations

from typing import Any

from app.schemas.contracts import PipelineInput

from .contradiction_detector import detect_contradictions
from .pipeline import run_extraction_pipeline
from .research_agent import run_research_agent
from .risk_flags import generate_additional_flags


def _to_dict(m: Any) -> dict:
    if hasattr(m, "model_dump"):
        return m.model_dump()
    if isinstance(m, dict):
        return m
    return {}


def run_research(payload: PipelineInput) -> dict[str, Any]:
    """
    Generate risk flags and secondary research signals.
    If extracted_facts and parsed_text_chunks are provided, use them.
    Otherwise run full pipeline (when uploaded_file_metadata has files).
    Runs research agent for structured secondary research signals.
    """
    facts = payload.extracted_facts
    chunks = payload.parsed_text_chunks or []
    file_meta = payload.uploaded_file_metadata or payload.document_references or []
    file_meta_list = [_to_dict(m) for m in (file_meta if isinstance(file_meta, list) else [])]

    if facts and chunks:
        contradiction_flags = detect_contradictions(
            facts,
            payload.officer_notes,
            chunks,
            file_meta_list,
        )
        risk_flags = generate_additional_flags(facts, contradiction_flags)
    elif file_meta_list and payload.case_id:
        result = run_extraction_pipeline(payload)
        risk_flags = result["risk_flags"]
    else:
        risk_flags = []

    secondary_signals = {}
    if payload.company_details:
        cd = _to_dict(payload.company_details)
        doc_lit = any(
            f.get("flag_type") == "litigation_risk" and f.get("severity") in ("high", "critical")
            for f in risk_flags
        )
        doc_aud = any(
            f.get("flag_type") == "auditor_concern" and f.get("severity") in ("high", "critical")
            for f in risk_flags
        )
        secondary_signals = run_research_agent(
            company_name=cd.get("company_name", ""),
            sector=cd.get("sector"),
            promoter_names=cd.get("promoter_names") or [],
            document_litigation_hint=doc_lit,
            document_auditor_concern=doc_aud,
        )

    return {
        "risk_flags": risk_flags,
        "secondary_research_signals": secondary_signals,
        "source": "pipeline",
    }
