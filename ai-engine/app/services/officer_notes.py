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
# Pattern definitions
# FIX O1: Replaced greedy `.*` in multi-word patterns with bounded `[^.]{0,50}`
#         to prevent catastrophic backtracking on long notes and false positives
#         (e.g. "site visit was great ... no concern" matching "site.*concern").
# ---------------------------------------------------------------------------

CAPACITY_PATTERNS = {
    "negative": [
        (r"(\d{1,3})\s*%\s*capacity", "capacity_pct"),
        (r"operating at (\d{1,3})\s*%", "capacity_pct"),
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
        (r"reluctant\s+to\s+share", None),    # FIX O1: was just "reluctant" — too broad
        (r"hostile", None),
        (r"defensive\s+about", None),          # FIX O1: was "defensive" — too broad
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
        # FIX O1: was `r"site\s+.*\s*concern"` — `.*` could cross sentence boundaries.
        # Now bounded to 50 chars between "site" and "concern".
        (r"site\s+[^.]{0,50}concern", None),
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
        # FIX O1: Replaced `.*` with `[^.]{0,40}` throughout to bound matching
        (r"promoter\s+[^.]{0,30}(was\s+)?evasive", None),
        (r"promoter\s+[^.]{0,40}doubt", None),
        (r"promoter\s+[^.]{0,40}concern", None),
        (r"promoter\s+lifestyle\s+[^.]{0,30}(extravagant|lavish)", None),
        (r"promoter\s+[^.]{0,40}(legal|litigation|case)", None),
        (r"diversion\s+of\s+funds?", None),
        (r"fund\s+diversion", None),
        (r"promoter\s+[^.]{0,30}not\s+credible", None),
    ],
    "positive": [
        (r"promoter\s+[^.]{0,30}(credible|experienced|reputed)", None),
        (r"strong\s+promoter", None),
        (r"promoter\s+track\s+record\s+(good|strong)", None),
        (r"promoter\s+[^.]{0,20}cooperative", None),
    ],
}

# FIX O2: Composite weights must sum to 1.0 — verified with assertion.
_COMPOSITE_WEIGHTS = {
    "capacity_utilization": 0.20,
    "management_quality":   0.20,
    "operational_health":   0.15,
    "collection_risk":      0.15,
    "site_visit_risk":      0.15,
    "promoter_behavior_score": 0.15,
}
assert abs(sum(_COMPOSITE_WEIGHTS.values()) - 1.0) < 1e-9, "Composite weights must sum to 1.0"


def _score_dimension(
    text: str,
    patterns: dict[str, list[tuple[str, str | None]]],
    base: float = 70.0,
    neg_weight: float = 12.0,
    pos_weight: float = 8.0,
) -> tuple[float, list[str]]:
    """Score a dimension 0–100 using pattern matching. Returns (score, explanations)."""
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
                        explanations.append(f"Very low capacity utilization (~{pct}%)")
                    elif pct < 70:
                        score -= 5
                        explanations.append(f"Below-average capacity utilization (~{pct}%)")
                    else:
                        # FIX O3: Previously no explanation was added for pct >= 70
                        # even though neg_weight was already deducted. Add one.
                        explanations.append(f"Capacity utilization noted (~{pct}%)")
                except (IndexError, ValueError):
                    explanations.append(f"Capacity utilization concern: '{m.group(0).strip()}'")
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

        cap_score,  cap_reasons  = _score_dimension(text, CAPACITY_PATTERNS,  neg_weight=15.0)
        mgmt_score, mgmt_reasons = _score_dimension(text, MANAGEMENT_PATTERNS)
        ops_score,  ops_reasons  = _score_dimension(text, OPERATIONAL_PATTERNS)
        coll_score, coll_reasons = _score_dimension(text, COLLECTION_PATTERNS)
        site_score, site_reasons = _score_dimension(text, SITE_VISIT_PATTERNS)
        prom_score, prom_reasons = _score_dimension(text, PROMOTER_PATTERNS, neg_weight=14.0)

        scores = {
            "capacity_utilization":    cap_score,
            "management_quality":      mgmt_score,
            "operational_health":      ops_score,
            "collection_risk":         coll_score,
            "site_visit_risk":         site_score,
            "promoter_behavior_score": prom_score,
        }
        composite = sum(_COMPOSITE_WEIGHTS[k] * v for k, v in scores.items())

        reasons_map = {
            "capacity_utilization":    cap_reasons,
            "management_quality":      mgmt_reasons,
            "operational_health":      ops_reasons,
            "collection_risk":         coll_reasons,
            "site_visit_risk":         site_reasons,
            "promoter_behavior_score": prom_reasons,
        }

        return {
            **{
                dim: {"score": round(scores[dim], 1), "explanations": reasons_map[dim]}
                for dim in scores
            },
            "composite_score": round(composite, 1),
            "all_explanations": (
                cap_reasons + mgmt_reasons + ops_reasons
                + coll_reasons + site_reasons + prom_reasons
            ),
        }


def _empty_signals() -> dict[str, Any]:
    """Neutral default when no officer notes provided."""
    dims = list(_COMPOSITE_WEIGHTS.keys())
    out: dict[str, Any] = {
        d: {"score": 70.0, "explanations": ["No officer notes provided; neutral default"]}
        for d in dims
    }
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