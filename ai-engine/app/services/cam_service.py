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


def run_cam(payload: PipelineInput) -> dict[str, Any]:
    """
    Generate CAM. Runs scoring engine when extracted_facts and risk_flags are present
    to get decision, reasons, and limit/roi. Generates DOCX file and returns metadata.
    """
    case_id = payload.case_id or "unknown"
    facts = payload.extracted_facts or {}
    risk_flags = payload.risk_flags or []
    secondary = payload.web_search_context or {}
    score_breakdown = payload.score_breakdown or {}
    overall_score = payload.overall_score

    if facts and risk_flags is not None:
        score_result = compute_score(facts, risk_flags, secondary or None, payload.officer_notes)
        final_decision = score_result["cam_decision"]
        rec_limit = score_result["recommended_limit"]
        rec_roi = score_result["recommended_roi"]
        reasons = score_result["reasons"]
        decision_explanation = score_result["decision_explanation"]
        overall_score = score_result["overall_score"]
    else:
        score_result = {}
        if overall_score is None:
            overall_score = 65.0
        final_decision = "approve" if overall_score >= 70 else ("manual_review" if overall_score >= 50 else "decline")
        revenue = facts.get("revenue")
        if isinstance(facts.get("revenue"), dict):
            revenue = facts["revenue"].get("value")
        debt = facts.get("total_debt")
        if isinstance(facts.get("total_debt"), dict):
            debt = facts["total_debt"].get("value")
        base = (revenue or 1_000_000) * 0.2
        rec_limit = round(base * (overall_score / 100), 0)
        rec_roi = 12.0 + (100 - overall_score) * 0.05
        reasons = [f"{k}: {v}" for k, v in score_breakdown.items()]
        decision_explanation = f"Overall score {overall_score}. Decision: {final_decision}."
        score_result = {
            "overall_score": overall_score,
            "score_breakdown": score_breakdown,
            "cam_decision": final_decision,
            "decision": final_decision,
            "recommended_limit": rec_limit,
            "recommended_roi": rec_roi,
            "reasons": reasons,
            "decision_explanation": decision_explanation,
        }

    # Build company details dict
    company_details = None
    if payload.company_details:
        cd = payload.company_details
        company_details = cd.model_dump() if hasattr(cd, "model_dump") else (cd if isinstance(cd, dict) else {})

    # Generate DOCX CAM
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
        logger.warning("DOCX generation failed, falling back to path placeholder: %s", e)
        cam_doc_path = f"data/evidence/{case_id}/cam.md"

    evidence_parts = []
    for f in risk_flags[:5]:
        evidence_parts.append(f"{f.get('flag_type', '')}: {f.get('description', '')[:80]}")
    evidence_summary = decision_explanation
    if evidence_parts:
        evidence_summary += " Risk flags: " + "; ".join(evidence_parts)[:300]

    return {
        "case_id": case_id,
        "final_decision": final_decision,
        "recommended_limit": rec_limit,
        "recommended_roi": rec_roi,
        "key_reasons": reasons[:8],
        "evidence_summary": evidence_summary[:500],
        "cam_doc_path": cam_doc_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "cam_service",
    }
