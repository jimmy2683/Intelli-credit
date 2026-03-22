"""
CAM service: generates Credit Appraisal Memo with explainable content.
Uses scoring engine for decision/reasons and cam_generator for DOCX output.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.schemas.contracts import PipelineInput

from .cam_generator import generate_cam_docx
from .scoring_engine import compute_score

logger = logging.getLogger(__name__)

# ROI cap must match scoring_engine.py — keep in sync
_ROI_MAX = 18.0
_ROI_BASE = 12.0


def _coerce_secondary(raw: Any) -> dict | None:
    """FIX #B1: web_search_context may be a Pydantic model; compute_score needs a plain dict."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw or None   # treat {} as None so scoring engine uses neutral default
    if hasattr(raw, "model_dump"):
        d = raw.model_dump()
        return d or None
    return None


def run_cam(payload: PipelineInput) -> dict[str, Any]:
    """
    Generate CAM. Runs scoring engine when extracted_facts are present
    to get decision, reasons, and limit/roi. Generates DOCX/markdown file.

    FIX #B2: `if facts and risk_flags is not None` — `risk_flags is not None` is
             ALWAYS True (it was assigned `payload.risk_flags or []`). Simplified to
             `if facts` so the scoring branch fires whenever facts are non-empty.

    FIX #B1: secondary properly coerced to plain dict.
    FIX #B3: fallback ROI capped at _ROI_MAX to match scoring_engine behaviour.
    FIX #B4: Removed redundant dead `debt` variable in fallback path.
    FIX #B5: score_result always passed with hard_override fields so CAM template
             can render the override banner correctly.
    """
    case_id        = payload.case_id or "unknown"
    facts          = payload.extracted_facts or {}
    risk_flags     = payload.risk_flags or []
    secondary      = _coerce_secondary(payload.web_search_context)
    score_breakdown = payload.score_breakdown or {}
    overall_score  = payload.overall_score

    # FIX #B2: was `if facts and risk_flags is not None` — second clause is always True
    if facts:
        score_result   = compute_score(facts, risk_flags, secondary, payload.officer_notes)
        final_decision = score_result["cam_decision"]
        rec_limit      = score_result["recommended_limit"]
        rec_roi        = score_result["recommended_roi"]
        reasons        = score_result["reasons"]
        decision_explanation = score_result["decision_explanation"]
        overall_score  = score_result["overall_score"]
    else:
        # Lightweight fallback when no facts available (e.g. upstream pipeline not run yet)
        if overall_score is None:
            overall_score = 65.0
        if overall_score >= 70:
            final_decision = "approve"
        elif overall_score >= 50:
            final_decision = "manual_review"
        else:
            final_decision = "decline"

        revenue_raw = facts.get("revenue")
        if isinstance(revenue_raw, dict):
            revenue_raw = revenue_raw.get("value")
        revenue = revenue_raw or 1_000_000

        # FIX #B4: debt was computed then never used in the original; removed.
        base      = revenue * 0.2
        rec_limit = round(base * (overall_score / 100), 0)

        # FIX #B3: cap ROI to _ROI_MAX, matching the scoring engine
        rec_roi   = min(_ROI_BASE + (100 - overall_score) * 0.05, _ROI_MAX)
        reasons   = [f"{k}: {v}" for k, v in score_breakdown.items()]
        decision_explanation = f"Overall score {overall_score}. Decision: {final_decision}."

        # FIX #B5: Include hard_override fields so cam_generator renders correctly
        score_result = {
            "overall_score": overall_score,
            "score_breakdown": score_breakdown,
            "cam_decision": final_decision,
            "decision": final_decision,
            "recommended_limit": rec_limit,
            "recommended_roi": rec_roi,
            "reasons": reasons,
            "decision_explanation": decision_explanation,
            "hard_override_applied": False,
            "hard_override_reason": None,
            "requires_human_review": final_decision == "manual_review",
            "case_confidence": None,
            "escalation_level": "normal",
        }

    # Build company details dict
    company_details = None
    if payload.company_details:
        cd = payload.company_details
        company_details = (
            cd.model_dump() if hasattr(cd, "model_dump")
            else (cd if isinstance(cd, dict) else {})
        )

    # Generate DOCX / markdown CAM
    try:
        cam_doc_path = generate_cam_docx(
            case_id=case_id,
            company_details=company_details,
            extracted_facts=facts,
            risk_flags=risk_flags,
            score_result=score_result,
            officer_notes=payload.officer_notes,
        )
    except Exception as e:
        logger.warning("DOCX/markdown generation failed; using placeholder path: %s", e)
        cam_doc_path = f"data/evidence/{case_id}/cam.md"

    evidence_parts = [
        f"{f.get('flag_type', '')}: {f.get('description', '')[:80]}"
        for f in risk_flags[:5]
    ]
    evidence_summary = decision_explanation
    if evidence_parts:
        evidence_summary += " Risk flags: " + "; ".join(evidence_parts)
    evidence_summary = evidence_summary[:500]

    return {
        "case_id": case_id,
        "final_decision": final_decision,
        "recommended_limit": rec_limit,
        "recommended_roi": rec_roi,
        "key_reasons": reasons[:8],
        "evidence_summary": evidence_summary,
        "cam_doc_path": cam_doc_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "cam_service",
    }