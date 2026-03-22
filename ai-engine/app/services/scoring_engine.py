"""
Explainable scoring engine for credit cases.
Transparent weighted model with hard override rules.
"""
from __future__ import annotations

import logging  # FIX #1: was imported inside compute_score() function body — moved to module top
from typing import Any

logger = logging.getLogger(__name__)

# Weights (must sum to 1.0)
WEIGHTS = {
    "financial_strength": 0.25,
    "cash_flow": 0.20,
    "governance": 0.15,
    "contradiction_severity": 0.15,
    "secondary_research": 0.15,
    "officer_note": 0.10,
}

# Sanity check at import time
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"

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
    # FIX #10: Use explicit None check + separate default so we can distinguish
    # "not extracted" (None → skip leverage) from "extracted as 0" (0.0 → use it).
    revenue_raw = _get_numeric(extracted_facts, "revenue")
    revenue = revenue_raw if revenue_raw is not None else 0.0
    debt_raw = _get_numeric(extracted_facts, "total_debt")
    debt = debt_raw if debt_raw is not None else 0.0
    pat = _get_numeric(extracted_facts, "PAT")          # None = not found
    current_ratio = _get_numeric(extracted_facts, "current_ratio")
    wc = _get_numeric(extracted_facts, "working_capital")

    score = 70.0  # base
    reasons: list[str] = []

    if revenue > 0:
        lev = debt / revenue
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

    # FIX #9 + #10: guard against None pat correctly; add reason for positive margin
    if pat is not None and revenue > 0:
        margin = pat / revenue
        if margin > 0.15:
            score += 8.0
            reasons.append(f"Strong profitability (PAT margin {margin:.0%})")
        elif margin > 0.05:
            score += 3.0
            reasons.append(f"Positive profitability (PAT margin {margin:.0%})")
        elif margin < 0:
            score -= 15.0
            reasons.append(f"Loss-making (PAT margin {margin:.0%})")

    return max(0.0, min(100.0, score)), reasons


def _cash_flow_score(extracted_facts: dict) -> tuple[float, list[str]]:
    """0-100. Based on DSCR, EBITDA margin."""
    dscr = _get_numeric(extracted_facts, "dscr")
    revenue = _get_numeric(extracted_facts, "revenue")
    ebitda = _get_numeric(extracted_facts, "EBITDA")

    score = 70.0
    reasons: list[str] = []

    if dscr is not None:
        if dscr >= 1.5:
            score += 15.0
            reasons.append(f"Strong DSCR ({dscr:.2f})")
        elif dscr >= 1.25:
            score += 8.0
            reasons.append(f"Adequate DSCR ({dscr:.2f})")
        elif dscr >= 1.0:
            score += 2.0
            # Borderline — no positive reason appended; neutral
        else:
            score -= 25.0
            reasons.append(f"Weak DSCR ({dscr:.2f}) — repayment capacity at risk")

    if revenue and ebitda is not None and revenue > 0:
        ebitda_margin = ebitda / revenue
        if ebitda_margin >= 0.20:
            score += 5.0
            reasons.append(f"Strong EBITDA margin ({ebitda_margin:.0%})")
        elif ebitda_margin < 0.05:
            score -= 10.0
            reasons.append(f"Low EBITDA margin ({ebitda_margin:.0%})")
        elif ebitda_margin < 0:
            score -= 20.0
            reasons.append(f"Negative EBITDA ({ebitda_margin:.0%})")

    return max(0.0, min(100.0, score)), reasons


def _governance_score(risk_flags: list[dict], extracted_facts: dict) -> tuple[float, list[str]]:
    """0-100. Based on RPT, auditor, governance flags."""
    score = 75.0
    reasons: list[str] = []

    gov_flags = [
        f for f in risk_flags
        if f.get("flag_type") in (
            "governance_instability", "high_related_party_dependency", "auditor_concern"
        )
    ]

    # Track whether auditor_concern came via a flag to avoid double-penalising below
    auditor_flag_applied = False

    for f in gov_flags:
        sev = f.get("severity", "medium")
        pen = SEVERITY_PENALTY.get(sev, 10)
        score -= pen
        reasons.append(f"Governance: {f.get('description', '')[:60]}")
        if f.get("flag_type") == "auditor_concern":
            auditor_flag_applied = True

    # FIX #16: only apply the direct auditor text penalty when no flag has already penalised it
    if not auditor_flag_applied:
        auditor = extracted_facts.get("auditor_remarks")
        aud_val = (
            auditor.get("value", []) if isinstance(auditor, dict)
            else (auditor if isinstance(auditor, list) else [])
        )
        if isinstance(aud_val, list):
            aud_str = " ".join(str(x).lower() for x in aud_val)
            if "qualification" in aud_str or "adverse" in aud_str:
                score -= 20
                reasons.append("Auditor qualification/adverse remark (text-based detection)")

    return float(max(0.0, min(100.0, score))), reasons


def _contradiction_severity_score(risk_flags: list[dict]) -> tuple[float, list[str]]:
    """0-100. Inverse of contradiction/red-flag severity.
    FIX #3: Critical penalty was 20 — same as high. Now critical=40 to properly differentiate.
    Comment header was already documenting the intended scale; the dict was wrong.
    """
    base = 100.0
    reasons: list[str] = []
    # Penalties per flag: critical is far more damaging than high
    penalties = {"low": 5, "medium": 10, "high": 20, "critical": 40}
    for f in risk_flags:
        sev = f.get("severity", "low").lower()
        pen = penalties.get(sev, 5)
        base -= pen
        reasons.append(f"{sev.upper()}: {f.get('description', '')[:50]}")
    return max(0.0, min(100.0, base)), reasons


def _secondary_research_score(secondary_research: dict | None) -> tuple[float, list[str]]:
    """0-100. From research agent signals.

    FIX #11 + #12:
    - Mock/low-confidence research (confidence < 0.3) is treated as neutral (70.0)
      rather than penalising at full weight based on placeholder LLM output.
    - Also incorporates the AI-synthesised web_research_summary when present and
      when it has higher confidence than the provider-level signals.
    """
    if not secondary_research:
        return 70.0, ["No secondary research; neutral default"]

    # Check if this is mock data — if so, return neutral to avoid false penalisation
    source = secondary_research.get("_source", "unknown")
    if source == "mock":
        return 70.0, ["Secondary research is mock data; neutral default applied"]

    score = 100.0
    reasons: list[str] = []

    # Provider-level signals
    for key in ("litigation_risk", "regulatory_risk", "promoter_reputation_risk", "sector_headwind_risk"):
        sig = secondary_research.get(key) or {}
        level = sig.get("level", "low")
        confidence = float(sig.get("confidence", 0.6))

        # FIX #11: Only apply full penalty when confidence >= 0.5; scale down for uncertain signals
        if confidence < 0.3:
            continue  # insufficient confidence — ignore signal entirely

        pen = RISK_LEVEL_PENALTY.get(level, 0)
        effective_pen = pen * min(1.0, confidence / 0.7)  # scale penalty by confidence
        score -= effective_pen

        if pen > 0:
            reasons.append(f"{key}: {level} (conf={confidence:.2f})")

    # FIX #12: Also incorporate AI-synthesised web_research_summary if available
    web = secondary_research.get("web_research_summary") or {}
    web_source = web.get("_source", "unknown")

    if web_source not in ("mock", "error", "unknown"):
        for web_key in ("litigation_risk", "sentiment_risk", "sector_risk"):
            sig = web.get(web_key) or {}
            level = sig.get("level", "low")
            confidence = float(sig.get("confidence", 0.5))

            if confidence < 0.4:
                continue

            pen = RISK_LEVEL_PENALTY.get(level, 0)
            # Weight web signals at 60% of provider signals (secondary corroboration)
            effective_pen = pen * min(1.0, confidence / 0.8) * 0.6
            score -= effective_pen

            if pen > 0:
                reasons.append(f"web_{web_key}: {level} (conf={confidence:.2f})")

    return float(max(0.0, min(100.0, score))), reasons


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
        return max(0.0, min(100.0, score)), reasons, signals
    except Exception as exc:
        logger.warning("officer_notes processor failed, using keyword fallback: %s", exc)
        # FIX #8: Removed dead `if not officer_notes:` check — can never be True here
        note_lower = officer_notes.lower()
        score = 70.0
        reasons: list[str] = []
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
        return max(0.0, min(100.0, score)), reasons, None


def _check_hard_overrides(
    risk_flags: list[dict],
    extracted_facts: dict,
    secondary_research: dict | None,
    case_confidence: float,
    contra_score: float,
) -> tuple[list[str], list[str]]:
    """
    Returns (reject_reasons, review_reasons).

    REJECT overrides (hard block):
      1. DSCR < 1.0
      2. ≥2 high/critical severity risk flags
      3. Litigation confirmed HIGH/CRITICAL (both document and research — FIX #4 & #5)
      4. Auditor going-concern or adverse opinion (FIX #6 — tightened keyword check)
      5. Company identity mismatch flag present
      6. Case confidence critically low (< 0.5)

    REVIEW overrides (soft escalation):
      - Contradiction score < 60
      - Moderate extraction confidence (0.5–0.7)
      - Schema incomplete
    """
    reject_reasons: list[str] = []
    review_reasons: list[str] = []

    # 1. DSCR < 1 — real repayment risk
    dscr = _get_numeric(extracted_facts, "dscr")
    if dscr is not None and dscr < 1.0:
        reject_reasons.append(f"DSCR {dscr:.2f} below 1.0 — insufficient repayment capacity")

    # 2. ≥2 high/critical risk flags
    high_flags = [
        f for f in risk_flags
        if str(f.get("severity", "")).lower() in ("high", "critical")
    ]
    if len(high_flags) >= 2:
        reject_reasons.append(
            f"Multiple high-severity risk flags detected ({len(high_flags)} flags)"
        )
    elif len(high_flags) == 1:
        review_reasons.append(f"1 HIGH/CRITICAL risk flag: {high_flags[0].get('flag_type', '')}")

    # 3. FIX #4 + #5: Litigation hard-reject ONLY when severity is confirmed HIGH or CRITICAL
    #    in BOTH secondary research AND document flags.  A medium flag alone is review, not reject.
    lit_research = (secondary_research or {}).get("litigation_risk", {})
    research_lit_high = lit_research.get("level") in ("high", "critical") and float(lit_research.get("confidence", 0)) >= 0.5

    doc_lit_high = any(
        f.get("flag_type") == "litigation_risk"
        and str(f.get("severity", "")).lower() in ("high", "critical")
        for f in risk_flags
    )
    doc_lit_any = any(f.get("flag_type") == "litigation_risk" for f in risk_flags)

    if research_lit_high and doc_lit_high:
        reject_reasons.append(
            "Severe litigation risk confirmed in both documents and secondary research"
        )
    elif research_lit_high or doc_lit_high:
        review_reasons.append("High-severity litigation risk detected — manual verification required")
    elif doc_lit_any:
        review_reasons.append("Litigation mention in documents — verify scope and severity")

    # 4. FIX #6: Tightened auditor keyword check — "qualification" alone is too broad.
    #    Now requires explicit adverse / going-concern / material uncertainty language.
    auditor_adverse_keywords = [
        "going concern",
        "material uncertainty",
        "adverse opinion",
        "disclaimer of opinion",
        "qualified opinion",    # more specific than just "qualification"
    ]
    aud_raw = extracted_facts.get("auditor_remarks")
    aud_val = (
        aud_raw.get("value", []) if isinstance(aud_raw, dict)
        else (aud_raw if isinstance(aud_raw, list) else [])
    )
    if isinstance(aud_val, list):
        aud_text = " ".join(str(x).lower() for x in aud_val)
        matched_kw = [kw for kw in auditor_adverse_keywords if kw in aud_text]
        if matched_kw:
            reject_reasons.append(
                f"Auditor adverse/going-concern language detected: {', '.join(matched_kw)}"
            )

    # 5. Company mismatch — should have blocked pipeline already but guard scoring too
    if any(
        f.get("flag_type") in ("company_identity_mismatch", "identity_mismatch")
        or "mismatch" in str(f.get("flag_type", "")).lower()
        for f in risk_flags
    ):
        reject_reasons.append("Company identity mismatch detected")

    # 6. Critically low extraction confidence
    if case_confidence < 0.5:
        reject_reasons.append(
            f"Extraction confidence critically low ({case_confidence:.2f}) — data unreliable"
        )

    # --- REVIEW OVERRIDES ---
    if contra_score < 60:
        review_reasons.append(f"Contradiction score low ({contra_score:.0f} < 60)")

    if 0.5 <= case_confidence < 0.7:
        review_reasons.append(f"Moderate extraction confidence ({case_confidence:.2f})")

    # Schema completeness heuristic
    core_keys = ["revenue", "total_debt", "short_term_assets", "total_borrowing", "GNPA", "promoter_percentage"]
    if not any(k in extracted_facts for k in core_keys):
        review_reasons.append("Core financial fields missing — extraction may have failed")

    return reject_reasons, review_reasons


def _recommended_limit_and_roi(
    overall_score: float,
    revenue: float | None,
    debt: float | None,
) -> tuple[float, float]:
    """Compute recommended_limit (INR) and recommended_roi (%).

    FIX #14: Cap raised to ₹10Cr (100_000_000) — the old ₹1Cr cap was far too conservative
    for enterprise B2B lending.

    FIX #15: Debt-based cap removed. Low existing debt is a sign of financial health,
    NOT a reason to reduce the recommended limit. Replaced with a debt-floor: if
    total existing debt is very high, cap limit at 30% of debt to avoid over-exposure.
    """
    # Base limit: 25% of revenue, capped at ₹10Cr
    base_limit = 1_000_000.0   # ₹10L floor
    if revenue and revenue > 0:
        base_limit = min(revenue * 0.25, 100_000_000.0)  # FIX #14: was 10_000_000

    # FIX #15: Only apply debt cap for HIGH-debt borrowers (debt/revenue > 2x)
    if debt and debt > 0 and revenue and revenue > 0:
        lev = debt / revenue
        if lev > 2.0:
            # Over-leveraged — cap at 30% of existing debt as a guardrail
            base_limit = min(base_limit, debt * 0.30)

    factor = overall_score / 100.0
    limit_out = base_limit * (0.5 + 0.5 * factor)

    # ROI: 12% base + penalty for lower score, capped at 18%
    roi = 12.0 + (100.0 - overall_score) * 0.05
    roi = max(12.0, min(roi, 18.0))

    return float(int(limit_out)), round(roi, 2)


def _calculate_confidence(extracted_facts: dict, risk_flags: list[dict]) -> float:
    """Calculates a weighted case-level confidence score (0.0 - 1.0).

    FIX #2: The original only looked for dict values with a 'confidence' key,
    which works for raw (un-normalized) facts. But after _normalize_facts() in
    pipeline.py, facts are flattened to {"revenue": v, "revenue_confidence": 0.9, ...}.
    Now handles BOTH formats.
    """
    conf_values: list[float] = []

    skip_suffixes = ("_confidence", "_source_ref")
    skip_keys = {
        "qualitative_insights", "requires_human_review", "review_reason",
        "entities", "risk_flags", "extracted_data",
    }

    for k, v in extracted_facts.items():
        if k in skip_keys:
            continue
        if any(k.endswith(s) for s in skip_suffixes):
            continue

        # Structured (un-normalized) format: {"value": x, "confidence": 0.9}
        if isinstance(v, dict) and "confidence" in v:
            conf_values.append(float(v["confidence"]))
            continue

        # Flat (normalized) format: look for matching "{field}_confidence" key
        conf_key = f"{k}_confidence"
        if conf_key in extracted_facts:
            raw_conf = extracted_facts[conf_key]
            if isinstance(raw_conf, (int, float)):
                conf_values.append(float(raw_conf))

    doc_conf = sum(conf_values) / len(conf_values) if conf_values else 0.65  # pessimistic default

    flag_confs = [float(f.get("confidence", 0.75)) for f in risk_flags]
    flag_conf = sum(flag_confs) / len(flag_confs) if flag_confs else 1.0

    # 70% weight on document extraction quality, 30% on flag confidence
    case_conf = (doc_conf * 0.70) + (flag_conf * 0.30)
    return max(0.0, min(1.0, case_conf))


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
    - decision / cam_decision (consistent lowercase — FIX #13)
    - decision_explanation
    - recommended_limit, recommended_roi
    - reasons
    - hard_override_applied, hard_override_reason
    - requires_human_review, review_reason
    - officer_note_signals
    - case_confidence, escalation_level, overrides_triggered
    """
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
    overall = round(max(0.0, min(100.0, overall)), 1)

    case_confidence = _calculate_confidence(extracted_facts, risk_flags)

    reject_reasons, review_reasons = _check_hard_overrides(
        risk_flags,
        extracted_facts,
        secondary_research,
        case_confidence,
        contra_score,
    )

    overrides_triggered = reject_reasons + review_reasons
    escalation_level = "normal"
    requires_review = False

    if reject_reasons:
        decision = "reject"
        cam_decision = "decline"
        decision_explanation = "Hard REJECT overrides: " + "; ".join(reject_reasons)
        escalation_level = "hard_review"
        requires_review = True
    elif overall < THRESHOLD_REVIEW:
        decision = "reject"
        cam_decision = "decline"
        decision_explanation = f"Overall score {overall} below reject threshold (<{THRESHOLD_REVIEW})."
        escalation_level = "hard_review"
        requires_review = True
    elif review_reasons:
        decision = "review"
        cam_decision = "manual_review"
        decision_explanation = "REVIEW overrides: " + "; ".join(review_reasons)
        escalation_level = "soft_review"
        requires_review = True
    elif overall < THRESHOLD_APPROVE:
        decision = "review"
        cam_decision = "manual_review"
        decision_explanation = f"Score {overall} in review band ({THRESHOLD_REVIEW}–{THRESHOLD_APPROVE})."
        escalation_level = "soft_review"
        requires_review = True
    else:
        decision = "approve"
        cam_decision = "approve"
        decision_explanation = f"Score {overall} meets approve threshold (≥{THRESHOLD_APPROVE}) with no overrides."

    logger.info(
        "[ScoringEngine] case_confidence=%.2f overall=%.1f decision=%s overrides=%s",
        case_confidence, overall, decision, overrides_triggered,
    )

    revenue = _get_numeric(extracted_facts, "revenue")
    debt = _get_numeric(extracted_facts, "total_debt")
    rec_limit, rec_roi = _recommended_limit_and_roi(overall, revenue, debt)

    all_reasons = (
        reject_reasons
        + review_reasons
        + [f"Financial: {r}" for r in fs_reasons[:2]]
        + [f"Cash flow: {r}" for r in cf_reasons[:2]]
        + [f"Governance: {r}" for r in gov_reasons[:2]]
        + [f"Contradictions: {r}" for r in contra_reasons[:2]]
        + [f"Research: {r}" for r in sr_reasons[:2]]
        + [f"Officer: {r}" for r in off_reasons[:2]]
    )
    all_reasons = [r for r in all_reasons if r and not r.endswith(": ")]

    return {
        # FIX #13: Both decision fields are consistently lowercase.
        # cam_decision was already lowercase; removed the .upper() from decision.
        "overall_score": overall,
        "score": overall,  # alias for legacy callers
        "score_breakdown": breakdown,
        "decision": decision,           # "approve" | "review" | "reject"
        "cam_decision": cam_decision,   # "approve" | "manual_review" | "decline"
        "decision_explanation": decision_explanation,
        "recommended_limit": rec_limit,
        "recommended_roi": rec_roi,
        "reasons": all_reasons[:10],
        "overrides_triggered": overrides_triggered,
        "hard_override_applied": len(reject_reasons) > 0,
        "hard_override_reason": " | ".join(reject_reasons) if reject_reasons else None,
        "requires_human_review": requires_review,
        "review_reason": " | ".join(review_reasons) if review_reasons else None,
        "officer_note_signals": off_signals,
        "case_confidence": round(case_confidence, 2),
        "escalation_level": escalation_level,
    }