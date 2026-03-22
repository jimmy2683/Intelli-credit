"""
Score service: runs explainable scoring engine.
Runs research agent for secondary_research when company_details present and web_search_context absent.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.contracts import PipelineInput

from .research_agent import run_research_agent
from .scoring_engine import compute_score

logger = logging.getLogger(__name__)


def _normalise_secondary(raw: Any) -> dict | None:
    """
    FIX #17: Safely coerce web_search_context to a plain dict regardless of whether
    it is a Pydantic model, a dict, or None.  compute_score() calls .get() on it,
    so it must be a real dict.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return raw.model_dump()
    try:
        return dict(raw)
    except Exception:
        logger.warning("Could not normalise web_search_context; ignoring it.")
        return None


def run_score(payload: PipelineInput) -> dict[str, Any]:
    """
    Run scoring engine. Expects extracted_facts, risk_flags in payload.
    Runs research agent when company_details present and web_search_context not provided.

    FIX #17: secondary coerced to plain dict via _normalise_secondary().
    FIX #18: web_research_summary is now incorporated — it is already inside the
             secondary dict returned by run_research_agent(); _secondary_research_score()
             in scoring_engine.py now reads it. No extra wiring needed here beyond
             ensuring the full secondary dict is passed through.
    FIX #19: case_confidence and escalation_level forwarded to caller.
    FIX #20: overrides_triggered forwarded to caller.
    """
    facts = payload.extracted_facts or {}
    risk_flags = payload.risk_flags or []
    secondary = _normalise_secondary(payload.web_search_context)
    notes = payload.officer_notes

    if secondary is None and payload.company_details:
        cd = payload.company_details
        cd_dict = (
            cd.model_dump() if hasattr(cd, "model_dump")
            else (cd if isinstance(cd, dict) else {})
        )

        # Derive hints from document-level flags before running agent
        doc_lit = any(
            f.get("flag_type") == "litigation_risk"
            and f.get("severity") in ("high", "critical")
            for f in (risk_flags or [])
        )
        doc_aud = any(
            f.get("flag_type") == "auditor_concern"
            and f.get("severity") in ("high", "critical")
            for f in (risk_flags or [])
        )

        try:
            secondary = run_research_agent(
                company_name=cd_dict.get("company_name", ""),
                sector=cd_dict.get("sector"),
                promoter_names=cd_dict.get("promoter_names") or [],
                document_litigation_hint=doc_lit,
                document_auditor_concern=doc_aud,
            )
        except Exception as e:
            logger.warning("Research agent failed during scoring; proceeding without secondary: %s", e)
            secondary = None

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
        "requires_human_review": result.get("requires_human_review", False),
        "review_reason": result.get("review_reason"),
        "officer_note_signals": result.get("officer_note_signals"),
        # FIX #19: expose confidence and escalation so the frontend can render them
        "case_confidence": result.get("case_confidence"),
        "escalation_level": result.get("escalation_level"),
        # FIX #20: expose what triggered overrides for full explainability
        "overrides_triggered": result.get("overrides_triggered", []),
        "source": "scoring_engine",
    }