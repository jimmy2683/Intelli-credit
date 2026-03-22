import pytest
from app.services.scoring_engine import compute_score

def test_approve_threshold():
    # Ideal case
    facts = {
        "revenue": {"value": 100000000.0, "confidence": 0.9},
        "total_debt": {"value": 10000000.0, "confidence": 0.9},
        "PAT": {"value": 15000000.0, "confidence": 0.9},
        "current_ratio": {"value": 2.0, "confidence": 0.9},
        "dscr": {"value": 2.5, "confidence": 0.9},
    }
    result = compute_score(facts, [], None, "Strong performance")
    assert result["decision"] == "APPROVE"
    assert result["overall_score"] >= 70

def test_reject_low_score():
    # Weak case but no hard overrides
    facts = {
        "revenue": {"value": 10000000.0, "confidence": 0.9},
        "total_debt": {"value": 20000000.0, "confidence": 0.9},
        "PAT": {"value": -1000000.0, "confidence": 0.9},
        "current_ratio": {"value": 0.8, "confidence": 0.9},
        "dscr": {"value": 1.1, "confidence": 0.9}, # Keep DSCR > 1 to avoid override
    }
    result = compute_score(facts, [], None, "Poor performance")
    assert result["decision"] == "REJECT"
    assert result["overall_score"] < 50

def test_review_band():
    # Average case
    facts = {
        "revenue": {"value": 50000000.0, "confidence": 0.9},
        "total_debt": {"value": 30000000.0, "confidence": 0.9},
        "PAT": {"value": 2000000.0, "confidence": 0.9},
        "current_ratio": {"value": 1.1, "confidence": 0.9},
        "dscr": {"value": 1.2, "confidence": 0.9},
    }
    result = compute_score(facts, [], None, "Moderate performance")
    assert result["decision"] == "REVIEW"
    assert 50 <= result["overall_score"] < 70

def test_override_dscr_reject():
    # High score but DSCR < 1
    facts = {
        "revenue": {"value": 100000000.0, "confidence": 0.9},
        "total_debt": {"value": 10000000.0, "confidence": 0.9},
        "dscr": {"value": 0.8, "confidence": 0.9},
    }
    result = compute_score(facts, [], None, "Good but can't pay")
    assert result["decision"] == "REJECT"
    assert "DSCR below 1" in result["hard_override_reason"]

def test_override_high_flags_reject():
    facts = {
        "revenue": {"value": 100000000.0, "confidence": 0.9},
        "dscr": {"value": 2.0, "confidence": 0.9},
    }
    flags = [
        {"flag_type": "legal", "severity": "high", "description": "L1"},
        {"flag_type": "fraud", "severity": "critical", "description": "F1"},
    ]
    result = compute_score(facts, flags, None, None)
    assert result["decision"] == "REJECT"
    assert "Multiple high-severity risk flags" in result["hard_override_reason"]

def test_override_legal_risk_reject():
    facts = {"dscr": {"value": 2.0, "confidence": 0.9}}
    secondary = {"litigation_risk": {"level": "high", "summary": "Bad legal"}}
    result = compute_score(facts, [], secondary, None)
    assert result["decision"] == "REJECT"
    assert "Legal risk identified" in result["hard_override_reason"]

def test_override_auditor_reject():
    facts = {
        "dscr": {"value": 2.0, "confidence": 0.9},
        "auditor_remarks": {"value": ["Major uncertainty exists"], "confidence": 0.9}
    }
    result = compute_score(facts, [], None, None)
    assert result["decision"] == "REJECT"
    assert "Auditor contains 'uncertainty'" in result["hard_override_reason"]

def test_override_mismatch_reject():
    facts = {"dscr": {"value": 2.0, "confidence": 0.9}}
    flags = [{"flag_type": "identity_mismatch", "severity": "critical", "description": "Wrong co"}]
    result = compute_score(facts, flags, None, None)
    assert result["decision"] == "REJECT"
    assert "Company mismatch detected" in result["hard_override_reason"]

def test_override_low_confidence_reject():
    facts = {
        "revenue": {"value": 100000000.0, "confidence": 0.3},
        "dscr": {"value": 2.0, "confidence": 0.3},
    }
    result = compute_score(facts, [], None, None)
    assert result["decision"] == "REJECT"
    assert "Case confidence is critically low" in result["hard_override_reason"]
