"""
Risk flag generation and ranking.
Produces flags with flag_type, severity, description, evidence_refs, confidence, impact_on_score.
Ranked by severity and confidence.
"""
from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}

FLAG_TYPES = [
    "gst_bank_mismatch",
    "circular_trading_suspicion",
    "weak_cash_conversion",
    "low_factory_utilization",
    "litigation_risk",
    "governance_instability",
    "auditor_concern",
    "high_related_party_dependency",
]


def _rank_key(flag: dict) -> tuple[int, float]:
    sev = SEVERITY_ORDER.get(flag.get("severity", "low"), 0)
    conf = flag.get("confidence", 0)
    return (sev, conf)


def rank_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort flags by severity (desc) then confidence (desc). Assign flag_id."""
    sorted_flags = sorted(flags, key=_rank_key, reverse=True)
    out = []
    for i, f in enumerate(sorted_flags):
        dup = dict(f)
        dup["flag_id"] = dup.get("flag_id") or f"rf_{i + 1:03d}"
        out.append(dup)
    return out


def generate_additional_flags(
    extracted_facts: dict[str, Any],
    contradiction_flags: list[dict],
) -> list[dict[str, Any]]:
    """
    Add heuristic flags based on extracted facts (e.g. circular trading, utilization).
    Merge with contradiction flags and rank.
    """
    flags = list(contradiction_flags)
    evidence = []
    for k, v in extracted_facts.items():
        if isinstance(v, dict) and v.get("source_ref"):
            evidence.append(v["source_ref"])

    revenue = None
    if isinstance(extracted_facts.get("revenue"), dict):
        revenue = extracted_facts["revenue"].get("value")
    debt = None
    if isinstance(extracted_facts.get("total_debt"), dict):
        debt = extracted_facts["total_debt"].get("value")

    if revenue and debt and debt > 0:
        lev = debt / revenue if revenue else 0
        if lev > 2.0:
            flags.append({
                "flag_type": "high_leverage",
                "severity": "high",
                "description": f"Debt/revenue ratio ~{lev:.1f}x indicates elevated leverage.",
                "evidence_refs": evidence[:2],
                "confidence": 0.8,
                "impact_on_score": "High negative impact on financial strength.",
            })

    rpt = extracted_facts.get("related_party_transactions")
    rpt_val = rpt.get("value", []) if isinstance(rpt, dict) else (rpt if isinstance(rpt, list) else [])
    if isinstance(rpt_val, list) and len(rpt_val) >= 4:
        if not any(f.get("flag_type") == "high_related_party_dependency" for f in flags):
            flags.append({
                "flag_type": "high_related_party_dependency",
                "severity": "medium",
                "description": "Extensive related party transactions; dependency risk.",
                "evidence_refs": evidence[:2],
                "confidence": 0.7,
                "impact_on_score": "Moderate governance concern.",
            })

    bank_gst = extracted_facts.get("bank_gst_mismatch_clues")
    bg_val = bank_gst.get("value", []) if isinstance(bank_gst, dict) else (bank_gst if isinstance(bank_gst, list) else [])
    if isinstance(bg_val, list) and any("circular" in str(x).lower() or "round" in str(x).lower() for x in bg_val):
        flags.append({
            "flag_type": "circular_trading_suspicion",
            "severity": "critical",
            "description": "Circular or round-tripping trading patterns suspected.",
            "evidence_refs": evidence[:3],
            "confidence": 0.65,
            "impact_on_score": "Critical; requires deep investigation.",
        })

    auditor = extracted_facts.get("auditor_remarks")
    aud_val = auditor.get("value", []) if isinstance(auditor, dict) else (auditor if isinstance(auditor, list) else [])
    if isinstance(aud_val, list):
        aud_str = " ".join(str(x).lower() for x in aud_val)
        if "going concern" in aud_str and "material" in aud_str:
            flags.append({
                "flag_type": "auditor_concern",
                "severity": "critical",
                "description": "Auditor raised going concern or material uncertainty.",
                "evidence_refs": evidence[:3],
                "confidence": 0.95,
                "impact_on_score": "Critical impact on credit assessment.",
            })

    return rank_flags(flags)
