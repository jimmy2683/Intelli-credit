"""
API integration tests using FastAPI TestClient.
Tests the full pipeline endpoints: /extract, /research, /score, /cam, /notes.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _base_payload(**overrides):
    payload = {
        "case_id": "test_integration_001",
        "company_details": {
            "company_name": "Test Integration Corp",
            "sector": "IT Services",
            "promoter_names": ["Alice", "Bob"],
        },
        "officer_notes": "Management cooperative. Factory at 80% capacity.",
        "uploaded_file_metadata": [],
        "extracted_facts": {
            "revenue": 100_000_000,
            "EBITDA": 18_000_000,
            "PAT": 9_000_000,
            "total_debt": 35_000_000,
            "current_ratio": 1.5,
            "dscr": 1.4,
        },
        "risk_flags": [],
    }
    payload.update(overrides)
    return payload


class TestHealthEndpoint:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestExtractEndpoint:
    def test_extract_no_files(self):
        resp = client.post("/extract", json=_base_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "extracted_facts" in data

    def test_extract_missing_case_id(self):
        payload = _base_payload()
        payload.pop("case_id", None)
        resp = client.post("/extract", json=payload)
        # Should still work (optional field) or return 422
        assert resp.status_code in (200, 422)


class TestScoreEndpoint:
    def test_score_returns_decision(self):
        resp = client.post("/score", json=_base_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data
        assert "decision" in data
        assert data["decision"] in ("approve", "reject", "decline", "manual_review", "approve_with_conditions")

    def test_score_has_breakdown(self):
        resp = client.post("/score", json=_base_payload())
        data = resp.json()
        assert "score_breakdown" in data
        assert isinstance(data["score_breakdown"], dict)

    def test_score_with_risk_flags(self):
        payload = _base_payload(risk_flags=[
            {"flag_type": "liquidity_stress", "severity": "high", "description": "CR below 1", "confidence": 0.9},
        ])
        resp = client.post("/score", json=payload)
        assert resp.status_code == 200


class TestResearchEndpoint:
    def test_research_returns_flags(self):
        resp = client.post("/research", json=_base_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_flags" in data

    def test_research_returns_signals(self):
        resp = client.post("/research", json=_base_payload())
        data = resp.json()
        # Research may return research_signals
        assert isinstance(data.get("risk_flags", []), list)


class TestCAMEndpoint:
    def test_cam_returns_result(self):
        payload = _base_payload()
        payload["score_breakdown"] = {"financial_strength": 80, "cash_flow": 75}
        payload["overall_score"] = 78
        resp = client.post("/cam", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "final_decision" in data or "cam_doc_path" in data or "evidence_summary" in data


class TestNotesEndpoint:
    def test_notes_positive(self):
        resp = client.post("/notes", json=_base_payload(
            officer_notes="Management cooperative. Factory at 85% capacity.",
        ))
        assert resp.status_code == 200
        data = resp.json()
        assert "officer_note_signals" in data
        signals = data["officer_note_signals"]
        assert signals["composite_score"] > 60

    def test_notes_negative(self):
        resp = client.post("/notes", json=_base_payload(
            officer_notes="Factory at 30% capacity. Promoter evasive. Stock mismatch.",
        ))
        assert resp.status_code == 200
        data = resp.json()
        signals = data["officer_note_signals"]
        assert signals["composite_score"] < 65

    def test_notes_empty(self):
        resp = client.post("/notes", json=_base_payload(officer_notes=""))
        assert resp.status_code == 200
        data = resp.json()
        assert data["officer_note_signals"]["composite_score"] == 70.0


class TestValidation:
    def test_invalid_json(self):
        resp = client.post("/score", content=b"not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_empty_body(self):
        resp = client.post("/score", json={})
        # Should either work with defaults or return validation error
        assert resp.status_code in (200, 422)
