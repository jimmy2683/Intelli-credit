"""
Tests for CAM generator.
Covers:
- DOCX generation with proper sections
- Markdown fallback
- Currency formatting helper
- Five Cs computation
- Edge cases (empty flags, missing fields)
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from app.services.cam_generator import (
    generate_cam_docx,
    _fmt_inr,
    _get_v,
    _severity_badge,
    _compute_five_cs,
)


@pytest.fixture
def tmp_data_root(tmp_path):
    """Provide a temporary DATA_ROOT."""
    with patch("app.services.cam_generator.DATA_ROOT", tmp_path):
        yield tmp_path


def _base_company():
    return {"company_name": "Test Corp", "sector": "Manufacturing", "promoter_names": ["Alice"], "cin_optional": "U12345"}


def _base_facts():
    return {
        "revenue": 100_000_000,
        "EBITDA": 18_000_000,
        "PAT": 9_000_000,
        "total_debt": 35_000_000,
        "current_ratio": 1.5,
        "dscr": 1.4,
    }


def _base_score():
    return {
        "overall_score": 78,
        "score_breakdown": {"financial_strength": 80, "cash_flow": 75, "governance": 70},
        "decision": "approve",
        "decision_explanation": "Healthy case",
        "recommended_limit": 50_000_000,
        "recommended_roi": 12.5,
        "reasons": ["Strong revenue", "Adequate DSCR"],
    }


# ── Helpers ──

class TestFmtInr:
    def test_crore(self):
        assert "Cr" in _fmt_inr(150_000_000)

    def test_lakh(self):
        assert "L" in _fmt_inr(500_000)

    def test_small(self):
        result = _fmt_inr(50_000)
        assert "₹" in result

    def test_none(self):
        assert "N/A" == _fmt_inr(None)


class TestGetV:
    def test_dict_with_value(self):
        assert _get_v({"revenue": {"value": 100}}, "revenue") == 100

    def test_direct_value(self):
        assert _get_v({"revenue": 100}, "revenue") == 100

    def test_missing_key(self):
        assert _get_v({}, "revenue") is None


class TestSeverityBadge:
    def test_critical(self):
        assert "CRITICAL" in _severity_badge("critical")

    def test_low(self):
        assert "LOW" in _severity_badge("low")


# ── Five Cs ──

class TestFiveCs:
    def test_all_cs_present(self):
        result = _compute_five_cs(_base_facts(), [], _base_score(), _base_company())
        assert set(result.keys()) == {"Character", "Capacity", "Capital", "Collateral", "Conditions"}

    def test_character_mentions_promoters(self):
        result = _compute_five_cs(_base_facts(), [], _base_score(), _base_company())
        assert "Alice" in result["Character"]


# ── CAM Generation ──

class TestCAMGeneration:
    def test_generates_file(self, tmp_data_root):
        path = generate_cam_docx(
            case_id="test_001",
            company_details=_base_company(),
            extracted_facts=_base_facts(),
            risk_flags=[],
            score_result=_base_score(),
            officer_notes="All good.",
        )
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_with_risk_flags(self, tmp_data_root):
        flags = [
            {"flag_type": "liquidity_stress", "severity": "high", "description": "CR below 1", "evidence_refs": ["doc.pdf"]},
            {"flag_type": "revenue_gst_mismatch", "severity": "critical", "description": "30% GST gap"},
        ]
        path = generate_cam_docx(
            case_id="test_002",
            company_details=_base_company(),
            extracted_facts=_base_facts(),
            risk_flags=flags,
            score_result=_base_score(),
        )
        assert os.path.exists(path)

    def test_with_hard_override(self, tmp_data_root):
        score = _base_score()
        score["hard_override_applied"] = True
        score["hard_override_reason"] = "GST mismatch > 25%"
        score["decision"] = "reject"
        path = generate_cam_docx(
            case_id="test_003",
            company_details=_base_company(),
            extracted_facts=_base_facts(),
            risk_flags=[],
            score_result=score,
        )
        assert os.path.exists(path)

    def test_empty_facts(self, tmp_data_root):
        path = generate_cam_docx(
            case_id="test_004",
            company_details=None,
            extracted_facts={},
            risk_flags=[],
            score_result={"overall_score": 0, "decision": "reject", "score_breakdown": {}},
        )
        assert os.path.exists(path)
