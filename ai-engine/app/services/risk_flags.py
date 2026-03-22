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
    "high_leverage",
    "company_identity_mismatch",
    "identity_uncertainty",
    "low_liquidity",
    "negative_working_capital",
]


def _rank_key(flag: dict) -> tuple[int, float]:
    sev = SEVERITY_ORDER.get(str(flag.get("severity", "low")).lower(), 0)
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


def _get_fact_value(facts: dict, key: str) -> Any:
    """
    FIX #C1: Handle BOTH normalized format (plain float/list at key) and
    structured format ({"value": x, "confidence": y} dict at key).
    After pipeline._normalize_facts() runs, values are plain Python types.
    Before normalization (e.g. when called from contradiction_detector), they
    are structured dicts. This helper reads both transparently.
    """
    v = facts.get(key)
    if isinstance(v, dict) and "value" in v:
        return v["value"]
    return v


def _collect_evidence(facts: dict) -> list[str]:
    """
    FIX #C2: Collect source_refs from BOTH structured (dict with source_ref)
    and normalized (_source_ref suffixed keys) fact formats.
    """
    refs: list[str] = []
    for k, v in facts.items():
        if k.endswith("_source_ref"):
            if isinstance(v, str) and v:
                refs.append(v)
        elif isinstance(v, dict) and v.get("source_ref"):
            refs.append(str(v["source_ref"]))
    return list(dict.fromkeys(refs))  # deduplicated, order-preserving


def generate_additional_flags(
    extracted_facts: dict[str, Any],
    contradiction_flags: list[dict],
) -> list[dict[str, Any]]:
    """
    Add heuristic flags based on extracted facts.
    Merges with contradiction_flags and returns ranked result.

    FIX #C1: Uses _get_fact_value() for both normalized and structured facts.
    FIX #C3: Deduplication guards added for circular_trading_suspicion and auditor_concern.
    FIX #C4: Removed redundant `if revenue else 0` inside `lev = debt / revenue` —
             the outer `if revenue` guard already ensures revenue > 0.
    """
    flags = list(contradiction_flags)
    evidence = _collect_evidence(extracted_facts)

    # FIX #C1: Read values correctly regardless of normalization state
    revenue  = _get_fact_value(extracted_facts, "revenue")
    debt     = _get_fact_value(extracted_facts, "total_debt")
    rpt_val  = _get_fact_value(extracted_facts, "related_party_transactions")
    bg_val   = _get_fact_value(extracted_facts, "bank_gst_mismatch_clues")
    aud_val  = _get_fact_value(extracted_facts, "auditor_remarks")

    # Ensure list types
    rpt_list = rpt_val if isinstance(rpt_val, list) else ([] if rpt_val is None else [rpt_val])
    bg_list  = bg_val  if isinstance(bg_val,  list) else ([] if bg_val  is None else [bg_val])
    aud_list = aud_val if isinstance(aud_val, list) else ([] if aud_val is None else [aud_val])

    # Helper: check if a flag_type is already present
    def _has_flag(flag_type: str) -> bool:
        return any(f.get("flag_type") == flag_type for f in flags)

    # --- High leverage ---
    if revenue and debt and float(revenue) > 0 and float(debt) > 0:
        # FIX #C4: Removed redundant `if revenue else 0` — already guarded above
        lev = float(debt) / float(revenue)
        if lev > 2.0 and not _has_flag("high_leverage"):
            flags.append({
                "flag_type": "high_leverage",
                "severity": "high",
                "description": f"Debt/revenue ratio ~{lev:.1f}x indicates elevated leverage.",
                "evidence_refs": evidence[:2],
                "confidence": 0.8,
                "impact_on_score": "High negative impact on financial strength.",
            })

    # --- High related-party dependency ---
    if len(rpt_list) >= 4 and not _has_flag("high_related_party_dependency"):
        flags.append({
            "flag_type": "high_related_party_dependency",
            "severity": "medium",
            "description": f"Extensive related party transactions ({len(rpt_list)} mentions); dependency risk.",
            "evidence_refs": evidence[:2],
            "confidence": 0.7,
            "impact_on_score": "Moderate governance concern.",
        })

    # --- Circular trading suspicion ---
    circular_signals = [
        x for x in bg_list
        if "circular" in str(x).lower() or "round" in str(x).lower()
    ]
    # FIX #C3: Deduplicate — don't add if already in flags
    if circular_signals and not _has_flag("circular_trading_suspicion"):
        flags.append({
            "flag_type": "circular_trading_suspicion",
            "severity": "critical",
            "description": "Circular or round-tripping trading patterns suspected.",
            "evidence_refs": evidence[:3],
            "confidence": 0.65,
            "impact_on_score": "Critical; requires deep investigation.",
        })

    # --- Auditor going concern ---
    # FIX #C3: Deduplicate — don't add if already in flags
    if aud_list and not _has_flag("auditor_concern"):
        aud_str = " ".join(str(x).lower() for x in aud_list)
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