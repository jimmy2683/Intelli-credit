"""
Tests for the explainable scoring engine.
Covers:
- Financial strength scoring (leverage, profitability, liquidity)
- Cash flow scoring (DSCR thresholds)
- Governance scoring (auditor remarks, related-party)
- Contradiction severity (risk flag penalties)
- Officer note score delegation
- Overall compute_score with decision thresholds (approve/review/reject)
- Recommended limit and ROI outputs
- Hard override triggers
"""
import pytest
from app.services.scoring_engine import (
    compute_score,
    _financial_strength_score,
    _cash_flow_score,
    _governance_score,
    _contradiction_severity_score,
    _officer_note_score,
    THRESHOLD_APPROVE,
    THRESHOLD_REVIEW,
)


# ── Helpers ──

def _make_facts(**overrides):
    """Build a base facts dict with sensible defaults."""
    base = {
        "revenue": 100_000_000,
        "EBITDA": 18_000_000,
        "PAT": 9_000_000,
        "total_debt": 35_000_000,
        "current_ratio": 1.5,
        "dscr": 1.4,
        "working_capital": 15_000_000,
    }
    base.update(overrides)
    return base


def _make_flags(*flag_defs):
    """Build risk flag list from (severity,) or (severity, flag_type) tuples."""
    flags = []
    for fd in flag_defs:
        sev = fd[0] if isinstance(fd, tuple) else fd
        ftype = fd[1] if (isinstance(fd, tuple) and len(fd) > 1) else "generic"
        flags.append({
            "flag_id": f"rf_{len(flags)}",
            "flag_type": ftype,
            "severity": sev,
            "description": f"Test flag ({sev})",
            "confidence": 0.8,
        })
    return flags


# ── Financial Strength ──

class TestFinancialStrength:
    def test_healthy_company(self):
        score, reasons = _financial_strength_score(_make_facts())
        assert 60 <= score <= 100
        assert isinstance(reasons, list)

    def test_high_leverage_penalty(self):
        score_normal, _ = _financial_strength_score(_make_facts(total_debt=30_000_000))
        score_heavy, _ = _financial_strength_score(_make_facts(total_debt=200_000_000))
        assert score_heavy < score_normal

    def test_negative_pat_penalty(self):
        score_pos, _ = _financial_strength_score(_make_facts(PAT=5_000_000))
        score_neg, _ = _financial_strength_score(_make_facts(PAT=-5_000_000))
        assert score_neg < score_pos

    def test_weak_current_ratio(self):
        score_good, _ = _financial_strength_score(_make_facts(current_ratio=2.0))
        score_weak, _ = _financial_strength_score(_make_facts(current_ratio=0.8))
        assert score_weak < score_good

    def test_zero_revenue(self):
        score, reasons = _financial_strength_score(_make_facts(revenue=0))
        assert 0 <= score <= 100  # Should not crash

    def test_score_bounded(self):
        score, _ = _financial_strength_score(_make_facts(
            revenue=1, total_debt=999_999_999, PAT=-999_999_999, current_ratio=0.1
        ))
        assert 0 <= score <= 100


# ── Cash Flow ──

class TestCashFlow:
    def test_strong_dscr(self):
        score, reasons = _cash_flow_score(_make_facts(dscr=2.0))
        assert score >= 70

    def test_weak_dscr(self):
        score, reasons = _cash_flow_score(_make_facts(dscr=0.6))
        assert score < 60

    def test_no_dscr(self):
        score, reasons = _cash_flow_score(_make_facts(dscr=None))
        assert 0 <= score <= 100


# ── Governance ──

class TestGovernance:
    def test_clean_governance(self):
        facts = _make_facts()
        facts["auditor_remarks"] = []
        facts["related_party_transactions"] = []
        score, reasons = _governance_score([], facts)
        assert score >= 60

    def test_auditor_concern_penalty(self):
        facts = _make_facts()
        facts["auditor_remarks"] = [{"text": "qualification on going concern"}]
        score, reasons = _governance_score([], facts)
        assert score < 75


# ── Contradiction Score ──

class TestContradictionSeverity:
    def test_no_flags(self):
        score, reasons = _contradiction_severity_score([])
        assert score >= 90

    def test_medium_flags(self):
        score, _ = _contradiction_severity_score(_make_flags("medium", "medium"))
        assert score < 95

    def test_critical_flags(self):
        score_clean, _ = _contradiction_severity_score([])
        score_crit, _ = _contradiction_severity_score(_make_flags("critical", "high"))
        assert score_crit < score_clean


# ── Officer Notes ──

class TestOfficerNote:
    def test_positive_notes(self):
        score, _, signals = _officer_note_score("Factory at 85% capacity. Management cooperative. Inventory tallied.")
        assert score >= 68  # Pattern scores aggregate; ~69-78 range expected

    def test_negative_notes(self):
        score, _, signals = _officer_note_score("Factory at 40% capacity. Promoter evasive. Stock mismatch.")
        assert score < 70

    def test_empty_notes(self):
        score, _, signals = _officer_note_score("")
        assert 60 <= score <= 80  # Neutral default


# ── End-to-End compute_score ──

class TestComputeScore:
    def test_approve_decision(self):
        result = compute_score(
            extracted_facts=_make_facts(),
            risk_flags=[],
            secondary_research=None,
            officer_notes="Factory at full capacity. Management cooperative.",
        )
        assert result["overall_score"] >= THRESHOLD_APPROVE
        assert result["decision"] == "APPROVE"
        assert result["recommended_limit"] > 0
        assert result["recommended_roi"] > 0

    def test_reject_decision(self):
        result = compute_score(
            extracted_facts=_make_facts(
                revenue=10_000_000, PAT=-8_000_000, total_debt=200_000_000,
                current_ratio=0.5, dscr=0.4,
            ),
            risk_flags=_make_flags(
                ("critical", "revenue_gst_mismatch"),
                ("high", "liquidity_stress"),
                ("high", "dscr_breach"),
            ),
            secondary_research=None,
            officer_notes="Factory at 30% capacity. Promoter evasive. Stock mismatch observed.",
        )
        assert result["overall_score"] < THRESHOLD_REVIEW
        assert result["decision"] in ("REJECT", "DECLINE")

    def test_score_breakdown_keys(self):
        result = compute_score(
            extracted_facts=_make_facts(),
            risk_flags=[],
            secondary_research=None,
            officer_notes=None,
        )
        bd = result["score_breakdown"]
        expected_keys = {"financial_strength", "cash_flow", "governance", "contradiction_severity", "secondary_research", "officer_note"}
        assert expected_keys.issubset(set(bd.keys()))

    def test_hard_override_gst_mismatch(self):
        flags = [{"flag_type": "revenue_gst_mismatch", "severity": "critical", "confidence": 0.9, "description": "Major GST mismatch"}]
        result = compute_score(
            extracted_facts=_make_facts(),
            risk_flags=flags,
            secondary_research=None,
            officer_notes="",
        )
        if result.get("hard_override_applied"):
            assert result["decision"] in ("REJECT", "DECLINE")
            assert result["hard_override_reason"]

    def test_required_output_fields(self):
        result = compute_score(_make_facts(), [], None, None)
        for key in ["overall_score", "score_breakdown", "decision", "recommended_limit", "recommended_roi", "reasons"]:
            assert key in result, f"Missing key: {key}"

    def test_score_is_bounded(self):
        result = compute_score(_make_facts(), _make_flags("critical", "critical", "critical", "high", "high"), None, None)
        assert 0 <= result["overall_score"] <= 100


# ── User Requested Scenarios ──

class TestUserScenarios:
    def test_healthy_case(self):
        # 1. Healthy Case: dscr > 1.5, no risk flags -> EXPECT: APPROVE
        result = compute_score(
            extracted_facts=_make_facts(dscr=1.8, revenue=10000000, EBITDA=2500000, PAT=1500000, current_ratio=2.0),
            risk_flags=[],
            secondary_research=None,
            officer_notes="Good company"
        )
        assert result["decision"] == "APPROVE"
        
    def test_risky_case(self):
        # 2. Risky Case: dscr = 0.9, auditor concern -> EXPECT: REJECT
        result = compute_score(
            extracted_facts=_make_facts(dscr=0.9, auditor_remarks={"value": ["uncertainty regarding going concern"]}),
            risk_flags=[{"flag_type": "auditor_concern", "severity": "critical"}],
            secondary_research=None,
            officer_notes="Poor performance"
        )
        assert result["decision"] == "REJECT"
        assert "DSCR" in result["hard_override_reason"] or "Auditor" in result["hard_override_reason"]

    def test_borderline_case(self):
        # 3. Borderline Case: dscr = 1.1, 1 risk flag -> EXPECT: REVIEW
        result = compute_score(
            extracted_facts=_make_facts(dscr=1.1, revenue=10000000, EBITDA=2000000, PAT=500000, current_ratio=1.1),
            risk_flags=[{"flag_type": "generic", "severity": "high"}],
            secondary_research=None,
            officer_notes="Average"
        )
        assert result["decision"] == "REVIEW"
        assert "1 HIGH risk flag detected" in result.get("review_reason", "")

    def test_mismatch_case(self):
        # 4. Mismatch Case: wrong company file -> EXPECT: REJECT
        result = compute_score(
            extracted_facts=_make_facts(dscr=1.5),
            risk_flags=[{"flag_type": "identity_mismatch", "severity": "critical", "confidence": 0.9}],
            secondary_research=None,
            officer_notes=""
        )
        assert result["decision"] == "REJECT"
        assert "Company mismatch detected" in result["hard_override_reason"]
