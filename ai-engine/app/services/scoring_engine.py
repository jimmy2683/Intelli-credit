"""
Explainable scoring engine for credit cases.
Transparent weighted model with hard override rules.
"""
from __future__ import annotations

from typing import Any

# Weights (must sum to 1.0)
WEIGHTS = {
    "financial_strength": 0.25,
    "cash_flow": 0.20,
    "governance": 0.15,
    "contradiction_severity": 0.15,
    "secondary_research": 0.15,
    "officer_note": 0.10,
}

# Decision thresholds
THRESHOLD_APPROVE = 70
THRESHOLD_REVIEW = 50
# Below 50 = reject

# Risk level to penalty (0-100 scale)
RISK_LEVEL_PENALTY = {"low": 0, "medium": 15, "high": 35, "critical": 50}
SEVERITY_PENALTY = {"low": 0, "medium": 10, "high": 25, "critical": 45}


def _get_numeric(facts: dict, key: str) -> float | None:
    v = facts.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _financial_strength_score(extracted_facts: dict) -> tuple[float, list[str]]:
    """0-100. Based on leverage, current ratio, profitability."""
    revenue = _get_numeric(extracted_facts, "revenue") or 0
    debt = _get_numeric(extracted_facts, "total_debt") or 0
    pat = _get_numeric(extracted_facts, "PAT") or 0
    current_ratio = _get_numeric(extracted_facts, "current_ratio")
    wc = _get_numeric(extracted_facts, "working_capital")

    score = 70.0  # base
    reasons = []

    if revenue > 0 and debt >= 0:
        lev = debt / revenue if revenue else 0
        if lev > 1.5:
            score -= 20
            reasons.append(f"High leverage (debt/revenue ~{lev:.1f}x)")
        elif lev > 1.0:
            score -= 10
            reasons.append(f"Moderate leverage ({lev:.1f}x)")
        elif lev < 0.5:
            score += 5
            reasons.append("Conservative leverage")

    if current_ratio is not None:
        if current_ratio >= 1.5:
            score += 5
            reasons.append(f"Strong liquidity (CR={current_ratio:.2f})")
        elif current_ratio < 1.0:
            score -= 15
            reasons.append(f"Weak liquidity (CR={current_ratio:.2f})")

    if wc is not None and wc < 0:
        score -= 15
        reasons.append("Negative working capital")

    if pat is not None and revenue and revenue > 0:
        margin = pat / revenue
        if margin > 0.1:
            score += 5
        elif margin < 0:
            score -= 15
            reasons.append("Loss-making")

    return max(0, min(100, score)), reasons


def _cash_flow_score(extracted_facts: dict) -> tuple[float, list[str]]:
    """0-100. Based on DSCR, cash conversion."""
    dscr = _get_numeric(extracted_facts, "dscr")
    revenue = _get_numeric(extracted_facts, "revenue")
    ebitda = _get_numeric(extracted_facts, "EBITDA")

    score = 70.0
    reasons = []

    if dscr is not None:
        if dscr >= 1.5:
            score += 15
            reasons.append(f"Strong DSCR ({dscr:.2f})")
        elif dscr >= 1.0:
            score += 5
        elif dscr < 1.0:
            score -= 25
            reasons.append(f"Weak DSCR ({dscr:.2f})")

    if revenue and ebitda is not None and revenue > 0:
        ebitda_margin = ebitda / revenue
        if ebitda_margin < 0.05:
            score -= 10
            reasons.append("Low EBITDA margin")

    return max(0, min(100, score)), reasons


def _governance_score(risk_flags: list[dict], extracted_facts: dict) -> tuple[float, list[str]]:
    """0-100. Based on RPT, auditor, governance flags."""
    score = 75.0
    reasons = []

    gov_flags = [f for f in risk_flags if f.get("flag_type") in ("governance_instability", "high_related_party_dependency", "auditor_concern")]
    for f in gov_flags:
        sev = f.get("severity", "medium")
        pen = SEVERITY_PENALTY.get(sev, 10)
        score -= pen
        reasons.append(f"Governance: {f.get('description', '')[:60]}")

    auditor = extracted_facts.get("auditor_remarks")
    aud_val = auditor.get("value", []) if isinstance(auditor, dict) else (auditor if isinstance(auditor, list) else [])
    if isinstance(aud_val, list):
        aud_str = " ".join(str(x).lower() for x in aud_val)
        if "qualification" in aud_str or "adverse" in aud_str:
            score -= 20
            reasons.append("Auditor qualification/adverse remark")

    return max(0, min(100, score)), reasons


def _contradiction_severity_score(risk_flags: list[dict]) -> tuple[float, list[str]]:
    """0-100. Inverse of contradiction/red-flag severity."""
    base = 100.0
    reasons = []
    for f in risk_flags:
        sev = f.get("severity", "low")
        pen = SEVERITY_PENALTY.get(sev, 5)
        base -= pen
        reasons.append(f"{sev}: {f.get('description', '')[:50]}")
    return max(0, min(100, base)), reasons


def _secondary_research_score(secondary_research: dict | None) -> tuple[float, list[str]]:
    """0-100. From research agent signals."""
    if not secondary_research:
        return 70.0, ["No secondary research; neutral default"]
    score = 100.0
    reasons = []

    for key in ("litigation_risk", "regulatory_risk", "promoter_reputation_risk", "sector_headwind_risk"):
        sig = secondary_research.get(key) or {}
        level = sig.get("level", "low")
        pen = RISK_LEVEL_PENALTY.get(level, 0)
        score -= pen
        if pen > 0:
            reasons.append(f"{key}: {level}")

    return max(0, min(100, score)), reasons


def _officer_note_score(officer_notes: str | None) -> tuple[float, list[str], dict | None]:
    """0-100. Uses structured officer notes processor for rich signal extraction.
    Returns (score, reasons, officer_note_signals_dict_or_None).
    """
    if not officer_notes or not officer_notes.strip():
        return 70.0, ["No officer notes; neutral default"], None

    try:
        from .officer_notes import process_notes
        signals = process_notes(officer_notes)
        score = signals.get("composite_score", 70.0)
        reasons = signals.get("all_explanations", [])
        if not reasons:
            reasons = ["Officer notes processed; no specific signals detected"]
        return max(0, min(100, score)), reasons, signals
    except Exception:
        # Fallback to simple keyword counting
        note_lower = officer_notes.lower()
        score = 70.0
        reasons = []
        neg = ["concern", "risk", "caution", "doubt", "weak", "unclear", "mismatch", "decline", "avoid"]
        pos = ["strong", "comfortable", "adequate", "positive", "recommend"]
        neg_count = sum(1 for w in neg if w in note_lower)
        pos_count = sum(1 for w in pos if w in note_lower)
        score -= neg_count * 8
        score += pos_count * 5
        if neg_count:
            reasons.append("Officer notes contain cautionary language")
        if pos_count:
            reasons.append("Officer notes contain positive indicators")
        return max(0, min(100, score)), reasons, None


# Hard override rule checks
def _check_hard_overrides(
    risk_flags: list[dict],
    extracted_facts: dict,
    secondary_research: dict | None,
) -> tuple[bool, str | None]:
    """
    Returns (should_override, override_reason).
    If override, decision should be reject regardless of score.
    """
    flags_by_type = {f.get("flag_type"): f for f in risk_flags}

    # Severe litigation
    if flags_by_type.get("litigation_risk", {}).get("severity") == "critical":
        return True, "Hard override: Severe litigation risk identified."

    lit_sig = (secondary_research or {}).get("litigation_risk", {})
    if lit_sig.get("level") == "high" and lit_sig.get("confidence", 0) > 0.8:
        return True, "Hard override: High litigation risk from secondary research."

    # Major GST mismatch
    gst = flags_by_type.get("gst_bank_mismatch", {})
    if gst.get("severity") in ("high", "critical") and gst.get("confidence", 0) > 0.75:
        return True, "Hard override: Major GST/bank mismatch flagged."

    # Serious auditor concern
    aud = flags_by_type.get("auditor_concern", {})
    if aud.get("severity") == "critical":
        return True, "Hard override: Serious auditor concern (e.g. going concern)."

    aud_remarks = extracted_facts.get("auditor_remarks")
    aud_val = aud_remarks.get("value", []) if isinstance(aud_remarks, dict) else (aud_remarks if isinstance(aud_remarks, list) else [])
    if isinstance(aud_val, list):
        s = " ".join(str(x).lower() for x in aud_val)
        if "going concern" in s and "material" in s:
            return True, "Hard override: Auditor raised going concern / material uncertainty."

    # Governance instability
    gov = flags_by_type.get("governance_instability", {})
    if gov.get("severity") in ("high", "critical"):
        return True, "Hard override: Governance instability."

    # Low utilization with weak financials (simplified)
    rev = _get_numeric(extracted_facts, "revenue")
    util_flag = flags_by_type.get("low_factory_utilization", {})
    if util_flag.get("severity") in ("high", "critical") and (not rev or rev < 1e6):
        return True, "Hard override: Low utilization with weak financials."

    return False, None


def _recommended_limit_and_roi(overall_score: float, revenue: float | None, debt: float | None) -> tuple[float, float]:
    """Compute recommended_limit (INR) and recommended_roi (%)."""
    base_limit = 1_000_000.0
    if revenue and revenue > 0:
        base_limit = min(revenue * 0.25, 10_000_000)
    if debt and debt > 0:
        base_limit = min(base_limit, debt * 1.2)

    factor = overall_score / 100.0
    limit = base_limit * (0.5 + 0.5 * factor)

    base_roi = 12.0
    roi = base_roi + (100 - overall_score) * 0.05
    roi = min(roi, 18.0)
    return round(limit, 0), round(roi, 2)


def compute_score(
    extracted_facts: dict[str, Any],
    risk_flags: list[dict[str, Any]],
    secondary_research: dict[str, Any] | None,
    officer_notes: str | None,
) -> dict[str, Any]:
    """
    Transparent weighted scoring. Returns:
    - overall_score (0-100)
    - score_breakdown
    - decision (approve | review | reject)
    - decision_explanation
    - recommended_limit, recommended_roi
    - reasons
    - hard_override_applied (bool, reason if any)
    - officer_note_signals (structured signals from officer notes processor)
    """
    override, override_reason = _check_hard_overrides(risk_flags, extracted_facts, secondary_research)

    fs_score, fs_reasons = _financial_strength_score(extracted_facts)
    cf_score, cf_reasons = _cash_flow_score(extracted_facts)
    gov_score, gov_reasons = _governance_score(risk_flags, extracted_facts)
    contra_score, contra_reasons = _contradiction_severity_score(risk_flags)
    sr_score, sr_reasons = _secondary_research_score(secondary_research)
    off_score, off_reasons, off_signals = _officer_note_score(officer_notes)

    breakdown = {
        "financial_strength": round(fs_score, 1),
        "cash_flow": round(cf_score, 1),
        "governance": round(gov_score, 1),
        "contradiction_severity": round(contra_score, 1),
        "secondary_research": round(sr_score, 1),
        "officer_note": round(off_score, 1),
    }

    overall = (
        WEIGHTS["financial_strength"] * fs_score
        + WEIGHTS["cash_flow"] * cf_score
        + WEIGHTS["governance"] * gov_score
        + WEIGHTS["contradiction_severity"] * contra_score
        + WEIGHTS["secondary_research"] * sr_score
        + WEIGHTS["officer_note"] * off_score
    )
    overall = round(max(0, min(100, overall)), 1)

    cam_decision = "manual_review"
    if override:
        decision = "reject"
        cam_decision = "decline"
        decision_explanation = override_reason or "Hard override applied."
    else:
        if overall >= THRESHOLD_APPROVE:
            decision = "approve"
            cam_decision = "approve"
            decision_explanation = f"Overall score {overall} meets approve threshold (≥{THRESHOLD_APPROVE})."
        elif overall >= THRESHOLD_REVIEW:
            decision = "review"
            cam_decision = "manual_review"
            decision_explanation = f"Overall score {overall} in review band ({THRESHOLD_REVIEW}-{THRESHOLD_APPROVE}). Manual assessment recommended."
        else:
            decision = "reject"
            cam_decision = "decline"
            decision_explanation = f"Overall score {overall} below review threshold (<{THRESHOLD_REVIEW})."

    revenue = _get_numeric(extracted_facts, "revenue")
    debt = _get_numeric(extracted_facts, "total_debt")
    rec_limit, rec_roi = _recommended_limit_and_roi(overall, revenue, debt)

    all_reasons = (
        [f"Financial: {r}" for r in fs_reasons[:2]]
        + [f"Cash flow: {r}" for r in cf_reasons[:2]]
        + [f"Governance: {r}" for r in gov_reasons[:2]]
        + [f"Contradictions: {r}" for r in contra_reasons[:2]]
        + [f"Research: {r}" for r in sr_reasons[:2]]
        + [f"Officer: {r}" for r in off_reasons[:2]]
    )
    all_reasons = [r for r in all_reasons if r and not r.endswith(": ")]

    return {
        "overall_score": overall,
        "score_breakdown": breakdown,
        "decision": decision,
        "cam_decision": cam_decision,
        "decision_explanation": decision_explanation,
        "recommended_limit": rec_limit,
        "recommended_roi": rec_roi,
        "reasons": all_reasons[:10],
        "hard_override_applied": override,
        "hard_override_reason": override_reason,
        "officer_note_signals": off_signals,
    }

