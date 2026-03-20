"""
Tests for officer notes processor.
Covers:
- Keyword-based signal extraction for all 6 dimensions
- Positive and negative pattern matching
- Capacity percentage parsing
- Composite score computation
- Empty/null notes defaults
- Pluggable extractor interface
"""
import pytest
from app.services.officer_notes import (
    process_notes,
    KeywordNoteExtractor,
    _score_dimension,
    _empty_signals,
    CAPACITY_PATTERNS,
    MANAGEMENT_PATTERNS,
    PROMOTER_PATTERNS,
)


class TestScoreDimension:
    def test_positive_signal_increases_score(self):
        score, explanations = _score_dimension("cooperative transparent management", MANAGEMENT_PATTERNS)
        assert score > 70  # Above base

    def test_negative_signal_decreases_score(self):
        score, explanations = _score_dimension("management evasive and hostile", MANAGEMENT_PATTERNS)
        assert score < 70  # Below base

    def test_neutral_text(self):
        score, explanations = _score_dimension("the sky is blue", MANAGEMENT_PATTERNS)
        assert score == 70  # Base score
        assert len(explanations) == 0

    def test_score_clamped_0_100(self):
        # Many negatives should not go below 0
        text = "evasive uncooperative hostile misleading reluctant defensive not transparent"
        score, _ = _score_dimension(text, MANAGEMENT_PATTERNS, neg_weight=20)
        assert score >= 0
        assert score <= 100


class TestCapacityPatterns:
    def test_low_capacity_percentage(self):
        signals = process_notes("Factory at 40% capacity")
        cap = signals["capacity_utilization"]
        assert cap["score"] < 60
        assert any("40%" in e for e in cap["explanations"])

    def test_high_capacity_percentage(self):
        signals = process_notes("running at 90% capacity. Plant expansion visible.")
        cap = signals["capacity_utilization"]
        assert cap["score"] >= 60  # Positive signal partially offsets negative pattern match

    def test_idle_plant(self):
        signals = process_notes("idle plant spotted during visit")
        assert signals["capacity_utilization"]["score"] < 70


class TestManagementQuality:
    def test_cooperative(self):
        signals = process_notes("Management was cooperative and transparent")
        assert signals["management_quality"]["score"] > 70

    def test_evasive(self):
        signals = process_notes("Management was evasive and reluctant")
        assert signals["management_quality"]["score"] < 70


class TestPromoterBehavior:
    def test_strong_promoter(self):
        signals = process_notes("Promoter track record strong. Promoter is experienced.")
        assert signals["promoter_behavior_score"]["score"] > 70

    def test_evasive_promoter_with_litigation(self):
        signals = process_notes("Promoter was evasive. Promoter has pending litigation.")
        assert signals["promoter_behavior_score"]["score"] < 60


class TestCollectionRisk:
    def test_healthy_receivables(self):
        signals = process_notes("Healthy receivables and timely collection.")
        assert signals["collection_risk"]["score"] > 70

    def test_weak_collection(self):
        signals = process_notes("Debtor collection weak. Bad debts increasing.")
        assert signals["collection_risk"]["score"] < 70


class TestSiteVisitRisk:
    def test_inventory_verified(self):
        signals = process_notes("Inventory tallied with books.")
        assert signals["site_visit_risk"]["score"] > 70

    def test_stock_mismatch(self):
        signals = process_notes("Stock mismatch observed during site visit.")
        assert signals["site_visit_risk"]["score"] < 70


class TestCompositeScore:
    def test_healthy_composite(self):
        signals = process_notes(
            "Factory running at 85% capacity. Management cooperative. "
            "Modern equipment. Healthy receivables. Inventory tallied. "
            "Strong promoter track record."
        )
        assert signals["composite_score"] > 70

    def test_risky_composite(self):
        signals = process_notes(
            "Factory at 40% capacity. Management evasive. "
            "Outdated equipment. Debtor collection weak. "
            "Stock mismatch. Promoter evasive with litigation."
        )
        assert signals["composite_score"] < 55


class TestProcessNotes:
    def test_none_input(self):
        signals = process_notes(None)
        assert signals["composite_score"] == 70.0
        assert all("No officer notes" in signals[d]["explanations"][0] for d in [
            "capacity_utilization", "management_quality", "operational_health"
        ])

    def test_empty_string(self):
        signals = process_notes("")
        assert signals["composite_score"] == 70.0

    def test_output_structure(self):
        signals = process_notes("Some notes here")
        expected_dims = [
            "capacity_utilization", "management_quality", "operational_health",
            "collection_risk", "site_visit_risk", "promoter_behavior_score",
        ]
        for dim in expected_dims:
            assert dim in signals
            assert "score" in signals[dim]
            assert "explanations" in signals[dim]
            assert isinstance(signals[dim]["score"], float)
            assert isinstance(signals[dim]["explanations"], list)
        assert "composite_score" in signals
        assert "all_explanations" in signals

    def test_custom_extractor(self):
        class AlwaysHighExtractor(KeywordNoteExtractor):
            def extract_signals(self, notes):
                base = _empty_signals()
                for d in base:
                    if isinstance(base[d], dict):
                        base[d]["score"] = 95.0
                base["composite_score"] = 95.0
                return base

        signals = process_notes("anything", extractor=AlwaysHighExtractor())
        assert signals["composite_score"] == 95.0
