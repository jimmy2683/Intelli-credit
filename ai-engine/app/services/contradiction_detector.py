"""
Contradiction detection and red-flag module.
Compares GST vs bank, revenue vs cash flow, debt vs sanctions, management vs notes, growth vs legal, auditor vs health.
"""
from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _get_numeric(facts: dict, path: str) -> float | None:
    v = facts.get(path)
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _get_qualitative(facts: dict, path: str) -> list[str]:
    v = facts.get(path)
    if isinstance(v, dict):
        v = v.get("value")
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str) and v:
        return [v]
    return []


def detect_contradictions(
    extracted_facts: dict[str, Any],
    officer_notes: str | None,
    parsed_chunks: list[dict],
    file_metadata: list[dict],
) -> list[dict[str, Any]]:
    """
    Compare sources and generate contradiction/red flags.
    Returns list of flags with flag_type, severity, description, evidence_refs, confidence, impact_on_score.
    """
    flags: list[dict[str, Any]] = []
    note_lower = (officer_notes or "").lower()
    doc_types = {m.get("doc_type", "unknown") for m in file_metadata}

    revenue = _get_numeric(extracted_facts, "revenue")
    debt = _get_numeric(extracted_facts, "total_debt")
    dscr = _get_numeric(extracted_facts, "dscr")
    current_ratio = _get_numeric(extracted_facts, "current_ratio")
    wc = _get_numeric(extracted_facts, "working_capital")
    pat = _get_numeric(extracted_facts, "PAT")

    auditor = _get_qualitative(extracted_facts, "auditor_remarks")
    legal = _get_qualitative(extracted_facts, "legal_mentions")
    rpt = _get_qualitative(extracted_facts, "related_party_transactions")
    bank_gst = _get_qualitative(extracted_facts, "bank_gst_mismatch_clues")

    evidence_refs = []
    for ch in parsed_chunks[:5]:
        if ch.get("chunk_id"):
            evidence_refs.append(ch["chunk_id"])

    def add_flag(
        flag_type: str,
        severity: str,
        desc: str,
        conf: float,
        impact: str,
        refs: list[str] | None = None,
    ):
        flags.append({
            "flag_type": flag_type,
            "severity": severity,
            "description": desc,
            "evidence_refs": refs or evidence_refs[:3],
            "confidence": conf,
            "impact_on_score": impact,
        })

    if any("mismatch" in str(b).lower() or "reconcil" in str(b).lower() for b in bank_gst):
        add_flag(
            "gst_bank_mismatch",
            "high",
            "GST sales vs bank credits mismatch or reconciliation issues identified.",
            0.8,
            "Significant negative impact; may indicate revenue quality concerns.",
        )

    if revenue and revenue > 0 and (dscr is not None and dscr < 1.0):
        add_flag(
            "weak_cash_conversion",
            "high",
            f"Reported revenue {revenue:,.0f} contrasts with DSCR {dscr:.2f} below 1.0.",
            0.85,
            "High impact on repayment capacity assessment.",
        )

    if debt and debt > 0 and "sanction_letter" in doc_types:
        add_flag(
            "debt_vs_sanction_check",
            "medium",
            "Declared debt should be cross-checked against sanction letters.",
            0.7,
            "Moderate impact; verify debt consistency.",
        )

    if officer_notes:
        neg_terms = ["concern", "risk", "caution", "doubt", "weak", "unclear", "mismatch"]
        if any(t in note_lower for t in neg_terms):
            add_flag(
                "officer_concerns",
                "medium",
                "Officer notes contain cautionary language; validate management claims.",
                0.75,
                "Moderate impact; warrants manual review.",
            )

    if legal and any("litigation" in str(l).lower() or "lawsuit" in str(l).lower() for l in legal):
        add_flag(
            "litigation_risk",
            "high",
            "Legal/litigation mentions detected; potential contingent liability.",
            0.85,
            "High impact on governance and contingent exposure.",
        )

    auditor_neg = ["qualification", "adverse", "disclaimer", "uncertainty", "emphasis"]
    if auditor and any(any(n in str(a).lower() for n in auditor_neg) for a in auditor):
        if (pat is not None and pat > 0) or (revenue and revenue > 0):
            add_flag(
                "auditor_concern",
                "high",
                "Auditor remarks suggest qualification or emphasis vs positive financials.",
            0.9,
            "High impact; auditor concern flags governance and reporting quality.",
            )

    if len(rpt) >= 3:
        add_flag(
            "high_related_party_dependency",
            "medium",
            f"Multiple related party transaction mentions ({len(rpt)}); assess dependency.",
            0.75,
            "Moderate impact on governance and transparency.",
        )

    if current_ratio is not None and current_ratio < 1.0:
        add_flag(
            "low_liquidity",
            "medium",
            f"Current ratio {current_ratio:.2f} below 1.0 indicates liquidity stress.",
            0.9,
            "Moderate negative impact on short-term solvency.",
        )

    if wc is not None and wc < 0:
        add_flag(
            "negative_working_capital",
            "high",
            f"Negative working capital ({wc:,.0f}); potential operational strain.",
            0.9,
            "High impact on operational sustainability.",
        )

    return flags
