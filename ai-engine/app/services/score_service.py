"""
Score service: runs explainable scoring engine.
Runs research agent for secondary_research when company_details present and web_search_context absent.
"""
from __future__ import annotations

from typing import Any

from app.schemas.contracts import PipelineInput

from .research_agent import run_research_agent
from .scoring_engine import compute_score


def run_score(payload: PipelineInput) -> dict[str, Any]:
    """
    Run scoring engine. Expects extracted_facts, risk_flags in payload.
    Runs research agent when company_details present and web_search_context not provided.
    """
    facts = payload.extracted_facts or {}
    risk_flags = payload.risk_flags or []
    secondary = payload.web_search_context
    notes = payload.officer_notes

    if secondary is None and payload.company_details:
        cd = payload.company_details
        cd_dict = cd.model_dump() if hasattr(cd, "model_dump") else (cd if isinstance(cd, dict) else {})
        doc_lit = any(
            f.get("flag_type") == "litigation_risk" and f.get("severity") in ("high", "critical")
            for f in (risk_flags or [])
        )
        doc_aud = any(
            f.get("flag_type") == "auditor_concern" and f.get("severity") in ("high", "critical")
            for f in (risk_flags or [])
        )
        secondary = run_research_agent(
            company_name=cd_dict.get("company_name", ""),
            sector=cd_dict.get("sector"),
            promoter_names=cd_dict.get("promoter_names") or [],
            document_litigation_hint=doc_lit,
            document_auditor_concern=doc_aud,
        )

    result = compute_score(facts, risk_flags, secondary, notes)
    return {
        "overall_score": result["overall_score"],
        "score_breakdown": result["score_breakdown"],
        "decision": result["decision"],
        "cam_decision": result["cam_decision"],
        "decision_explanation": result["decision_explanation"],
        "recommended_limit": result["recommended_limit"],
        "recommended_roi": result["recommended_roi"],
        "reasons": result["reasons"],
        "hard_override_applied": result["hard_override_applied"],
        "hard_override_reason": result.get("hard_override_reason"),
        "officer_note_signals": result.get("officer_note_signals"),
        "source": "scoring_engine",
    }
