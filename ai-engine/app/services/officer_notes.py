"""
Officer notes processor: converts qualitative officer notes into structured risk signals.
Supports keyword-based extraction with a pluggable interface for future LLM-assisted extraction.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class NoteExtractor(ABC):
    """Pluggable interface: swap keyword rules for LLM-based extraction."""

    @abstractmethod
    def extract_signals(self, notes: str) -> dict[str, Any]:
        pass


# ---------------------------------------------------------------------------
# Pattern definitions for keyword-based extraction
# ---------------------------------------------------------------------------

CAPACITY_PATTERNS = {
    "negative": [
        (r"(\d{1,3})\s*%\s*capacity", "capacity_pct"),      # "40% capacity"
        (r"operating at (\d{1,3})\s*%", "capacity_pct"),     # "operating at 40%"
        (r"under-?utiliz", None),
        (r"idle\s+(plant|machinery|capacity)", None),
        (r"shut\s*down", None),
        (r"low\s+utiliz", None),
    ],
    "positive": [
        (r"full\s+capacity", None),
        (r"capacity\s+expansion", None),
        (r"plant\s+expansion", None),
        (r"running\s+at\s+(8[5-9]|9\d|100)\s*%", None),
    ],
}

MANAGEMENT_PATTERNS = {
    "negative": [
        (r"evasive", None),
        (r"uncooperative", None),
        (r"non[\s-]?responsive", None),
        (r"misleading", None),
        (r"reluctant", None),
        (r"hostile", None),
        (r"defensive", None),
        (r"not\s+transparent", None),
        (r"hiding\s+information", None),
    ],
    "positive": [
        (r"cooperative", None),
        (r"transparent", None),
        (r"responsive", None),
        (r"professional", None),
        (r"forthcoming", None),
        (r"well[\s-]?organized", None),
        (r"open\s+(to|with)", None),
    ],
}

OPERATIONAL_PATTERNS = {
    "negative": [
        (r"poor\s+maintenance", None),
        (r"outdated\s+(equipment|machinery)", None),
        (r"disrepair", None),
        (r"safety\s+concern", None),
        (r"poor\s+housekeeping", None),
        (r"dilapidated", None),
    ],
    "positive": [
        (r"well[\s-]?maintain", None),
        (r"modern\s+(equipment|machinery|plant)", None),
        (r"expansion\s+visible", None),
        (r"new\s+(equipment|machinery|line)", None),
        (r"good\s+housekeeping", None),
        (r"clean\s+(factory|plant|premises)", None),
    ],
}

COLLECTION_PATTERNS = {
    "negative": [
        (r"debtor\s+collection\s+(looks\s+)?weak", None),
        (r"collection\s+(is\s+)?weak", None),
        (r"receivable\s+aging", None),
        (r"overdue\s+(receivable|debtor)", None),
        (r"slow\s+collection", None),
        (r"bad\s+debt", None),
        (r"write[\s-]?off", None),
        (r"stuck\s+receivable", None),
    ],
    "positive": [
        (r"collection\s+(is\s+)?strong", None),
        (r"timely\s+collection", None),
        (r"healthy\s+receivable", None),
        (r"low\s+debtor\s+days", None),
    ],
}

SITE_VISIT_PATTERNS = {
    "negative": [
        (r"site\s+.*\s*concern", None),
        (r"discrepanc", None),
        (r"mismatch\s+(between|in|on)\s+site", None),
        (r"inventory\s+(mismatch|concern|low|missing)", None),
        (r"stock\s+(mismatch|concern|discrepanc)", None),
        (r"inflated\s+(stock|inventory)", None),
    ],
    "positive": [
        (r"site\s+visit\s+(satisfactory|positive|good)", None),
        (r"inventory\s+(tallied|verified|matched)", None),
        (r"stock\s+(verified|matches)", None),
    ],
}

PROMOTER_PATTERNS = {
    "negative": [
        (r"promoter\s+(response\s+)?(was\s+)?evasive", None),
        (r"promoter\s+.*\s*doubt", None),
        (r"promoter\s+.*\s*concern", None),
        (r"promoter\s+lifestyle\s+.*\s*(extravagant|lavish)", None),
        (r"promoter\s+.*\s*(legal|litigation|case)", None),
        (r"diversion\s+of\s+fund", None),
        (r"fund\s+diversion", None),
        (r"promoter\s+.*\s*not\s+credible", None),
    ],
    "positive": [
        (r"promoter\s+.*\s*(credible|experienced|reputed)", None),
        (r"strong\s+promoter", None),
        (r"promoter\s+track\s+record\s+(good|strong)", None),
        (r"promoter\s+.*\s*cooperative", None),
    ],
}


def _score_dimension(
    text: str,
    patterns: dict[str, list[tuple[str, str | None]]],
    base: float = 70.0,
    neg_weight: float = 12.0,
    pos_weight: float = 8.0,
) -> tuple[float, list[str]]:
    """Score a dimension from 0-100 using pattern matching.  Returns (score, explanations)."""
    score = base
    explanations: list[str] = []

    for pat, extra in patterns.get("negative", []):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            score -= neg_weight
            if extra == "capacity_pct":
                try:
                    pct = int(m.group(1))
                    if pct < 50:
                        score -= 10
                        explanations.append(f"Low capacity utilization (~{pct}%)")
                    elif pct < 70:
                        score -= 5
                        explanations.append(f"Below-average capacity utilization (~{pct}%)")
                except (IndexError, ValueError):
                    pass
            else:
                explanations.append(f"Negative signal: '{m.group(0).strip()}'")

    for pat, _ in patterns.get("positive", []):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            score += pos_weight
            explanations.append(f"Positive signal: '{m.group(0).strip()}'")

    return max(0.0, min(100.0, score)), explanations


class KeywordNoteExtractor(NoteExtractor):
    """Keyword and pattern-based officer note extraction."""

    def extract_signals(self, notes: str) -> dict[str, Any]:
        if not notes or not notes.strip():
            return _empty_signals()

        text = notes.strip()

        cap_score, cap_reasons = _score_dimension(text, CAPACITY_PATTERNS, neg_weight=15.0)
        mgmt_score, mgmt_reasons = _score_dimension(text, MANAGEMENT_PATTERNS)
        ops_score, ops_reasons = _score_dimension(text, OPERATIONAL_PATTERNS)
        coll_score, coll_reasons = _score_dimension(text, COLLECTION_PATTERNS)
        site_score, site_reasons = _score_dimension(text, SITE_VISIT_PATTERNS)
        prom_score, prom_reasons = _score_dimension(text, PROMOTER_PATTERNS, neg_weight=14.0)

        composite = (
            0.20 * cap_score
            + 0.20 * mgmt_score
            + 0.15 * ops_score
            + 0.15 * coll_score
            + 0.15 * site_score
            + 0.15 * prom_score
        )

        return {
            "capacity_utilization": {"score": round(cap_score, 1), "explanations": cap_reasons},
            "management_quality": {"score": round(mgmt_score, 1), "explanations": mgmt_reasons},
            "operational_health": {"score": round(ops_score, 1), "explanations": ops_reasons},
            "collection_risk": {"score": round(coll_score, 1), "explanations": coll_reasons},
            "site_visit_risk": {"score": round(site_score, 1), "explanations": site_reasons},
            "promoter_behavior_score": {"score": round(prom_score, 1), "explanations": prom_reasons},
            "composite_score": round(composite, 1),
            "all_explanations": cap_reasons + mgmt_reasons + ops_reasons + coll_reasons + site_reasons + prom_reasons,
        }


def _empty_signals() -> dict[str, Any]:
    """Neutral default when no officer notes provided."""
    dims = [
        "capacity_utilization", "management_quality", "operational_health",
        "collection_risk", "site_visit_risk", "promoter_behavior_score",
    ]
    out: dict[str, Any] = {}
    for d in dims:
        out[d] = {"score": 70.0, "explanations": ["No officer notes provided; neutral default"]}
    out["composite_score"] = 70.0
    out["all_explanations"] = ["No officer notes provided"]
    return out


def process_notes(notes: str | None, extractor: NoteExtractor | None = None) -> dict[str, Any]:
    """
    Main entry point. Processes officer notes into structured signals.
    Uses KeywordNoteExtractor by default; pass a custom NoteExtractor for LLM-based extraction.
    """
    ext = extractor or KeywordNoteExtractor()
    return ext.extract_signals(notes or "")
