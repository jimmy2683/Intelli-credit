"""
Schema-based extraction: structured financial facts, confidence scores, and source references.
"""
from __future__ import annotations

import re
from typing import Any

EXTRACTED_FIELDS = [
    "revenue", "EBITDA", "PAT", "total_debt", "working_capital",
    "current_ratio", "dscr", "contingent_liabilities",
    "related_party_transactions", "auditor_remarks",
    "director_promoter_mentions", "legal_mentions", "bank_gst_mismatch_clues",
]

NUMERIC_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "revenue": [
        # FIX E1: Added "revenue from operations" — standard Indian P&L line item
        (r"revenue\s+from\s+operations[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh|mn|million)?", 0.95),
        (r"total\s+revenue[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh|mn|million)?", 0.90),
        (r"revenue[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh|mn|million)?", 0.85),
        (r"sales\s+(?:revenue|turnover)[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.80),
        (r"turnover[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.75),
        (r"revenue:\s*Rs\s+([\d,]+(?:\.\d+)?)", 0.90),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+revenue", 0.70),
    ],
    "EBITDA": [
        (r"EBITDA[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh|mn|million)?", 0.90),
        (r"earnings\s+before\s+interest[,\s]+taxes?[,\s]+depreciation[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.85),
        (r"earnings\s+before\s+interest[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.80),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+EBITDA", 0.70),
    ],
    "PAT": [
        (r"PAT[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh|mn|million)?", 0.90),
        (r"profit\s+after\s+tax[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.90),
        (r"net\s+profit[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.80),
        (r"profit\s+for\s+the\s+(?:year|period)[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.85),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+PAT", 0.65),
    ],
    "total_debt": [
        (r"total\s+(?:outstanding\s+)?(?:borrowings?|debt)[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.90),
        # FIX E2: Bare "debt" pattern had no word-boundary — could match "bad debt", "indebtedness" etc.
        # Added word boundary \b and negative lookbehind for "bad"
        (r"(?<!bad\s)\bdebt\b[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.70),
        (r"borrowings?[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.85),
        (r"total\s+liabilities[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.65),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+(?:total\s+)?(?:debt|borrowing)", 0.65),
    ],
    "working_capital": [
        (r"(?:net\s+)?working\s+capital[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.90),
    ],
    "current_ratio": [
        (r"current\s+ratio[:\s]*([\d.]+)", 0.95),
        (r"current\s+assets\s*/\s*current\s+liabilities[:\s]*([\d.]+)", 0.90),
    ],
    "dscr": [
        (r"DSCR[:\s]*([\d.]+)", 0.95),
        (r"debt\s+service\s+coverage\s+ratio[:\s]*([\d.]+)", 0.90),
        (r"debt\s+service\s+coverage[:\s]*([\d.]+)", 0.85),
    ],
}

QUALITATIVE_KEYWORDS: dict[str, list[tuple[list[str], float]]] = {
    "contingent_liabilities": [
        (["contingent liability", "corporate guarantee", "bank guarantee", "indemnity"], 0.80),
        (["counter guarantee", "performance guarantee", "bid bond"], 0.75),
        (["letter of credit", "comfort letter", "deed of guarantee"], 0.72),
    ],
    "related_party_transactions": [
        (["related party", "RPT", "intercompany", "promoter entity", "associate"], 0.85),
        (["key management", "director remuneration", "loans to promoters"], 0.80),
        (["holding company", "subsidiary transaction", "group company transaction"], 0.75),
    ],
    "auditor_remarks": [
        # FIX E3: "qualification" alone is too broad — matches "educational qualification",
        # "professional qualifications of directors", etc.
        # Replaced with the actual audit-opinion phrases used in Indian financial statements.
        (["qualified opinion", "adverse opinion", "disclaimer of opinion"], 0.95),
        (["material uncertainty", "going concern", "emphasis of matter"], 0.90),
        (["key audit matter", "significant risk", "material misstatement"], 0.85),
        (["unmodified opinion", "clean report", "no qualification", "unqualified"], 0.75),
    ],
    "legal_mentions": [
        (["litigation", "lawsuit", "legal notice", "arbitration", "dispute"], 0.90),
        (["court order", "pending case", "contingent on outcome", "writ petition"], 0.85),
        (["FIR", "criminal complaint", "SEBI action", "RBI penalty"], 0.90),
    ],
    "director_promoter_mentions": [
        (["managing director", "chairperson", "board of directors"], 0.75),
        (["KMP", "key managerial personnel", "CFO", "CEO", "promoter"], 0.75),
        (["director", "chairman", "independent director"], 0.65),
    ],
    "bank_gst_mismatch_clues": [
        (["GST reconciliation", "sales reconciliation", "credit reconciliation", "GST mismatch"], 0.85),
        (["bank credits vs GST", "declared sales mismatch", "unreconciled GST"], 0.90),
    ],
}

# FIX E4: Plausible value ranges for sanity-checking extracted numbers.
# Prevents page numbers, footnote references, and percentages from being
# accepted as financial metrics.
_NUMERIC_RANGES: dict[str, tuple[float, float]] = {
    "current_ratio": (0.1, 20.0),     # ratios above 20 are almost certainly wrong
    "dscr":          (0.0, 30.0),     # DSCR above 30 is implausible
}


def _parse_number(s: str, unit: str = "") -> float | None:
    """Parse a number string and apply unit multiplier.

    FIX E5: `"l" == unit` and `"m" == unit` were effectively dead code —
    unit_str is always set to one of "cr", "lakh", or "mn" by the caller.
    Cleaned up. Added explicit "l" → lakh check for completeness.
    """
    s = re.sub(r"[, ]", "", str(s))
    try:
        val = float(s)
        unit = unit.lower().strip()
        if "cr" in unit or "crore" in unit:
            val *= 10_000_000
        elif "lakh" in unit:
            val *= 100_000
        elif unit == "l":
            val *= 100_000
        elif "mn" in unit or "million" in unit:
            val *= 1_000_000
        return val
    except ValueError:
        return None


def _detect_unit(full_match_lower: str) -> str:
    """Extract the unit string from a full regex match string."""
    if "crore" in full_match_lower or " cr" in full_match_lower:
        return "cr"
    if "lakh" in full_match_lower:
        return "lakh"
    if "million" in full_match_lower or " mn" in full_match_lower:
        return "mn"
    return ""


def _extract_numeric(chunks: list[dict], field: str) -> dict[str, Any]:
    """Extract a numeric field from chunks.

    FIX E4: Added range validation to reject implausible values (e.g. DSCR=52).
    """
    patterns = NUMERIC_PATTERNS.get(field, [])
    range_min, range_max = _NUMERIC_RANGES.get(field, (None, None))

    for pattern, base_conf in patterns:
        for ch in chunks:
            m = re.search(pattern, ch.get("text", ""), re.IGNORECASE)
            if not m:
                continue
            val_str = m.group(1)
            unit_str = _detect_unit(m.group(0).lower())
            val = _parse_number(val_str, unit_str)
            if val is None:
                continue
            # Range check — reject implausible values for ratio fields
            if range_min is not None and not (range_min <= val <= range_max):
                continue
            return {
                "value": val,
                "confidence": base_conf,
                "source_ref": ch.get("chunk_id", ""),
            }

    return {"value": None, "confidence": 0.1, "source_ref": ""}


def _extract_qualitative(chunks: list[dict], field: str) -> dict[str, Any]:
    """Extract qualitative mentions for a field.

    FIX E6: `text.find(kw)` was called twice with no guarantee the same index
    was returned (if kw appears multiple times). Store position from first call.

    FIX E7: Snippet extraction used case-lowered text index but original text
    for display — mixed-case. Now consistently lowercase for matching; display
    shows the actual snippet.
    """
    matches: list[tuple[str, float, str]] = []  # (snippet, confidence, chunk_id)
    rules = QUALITATIVE_KEYWORDS.get(field, [])

    for keywords, base_conf in rules:
        for ch in chunks:
            raw_text = ch.get("text") or ""
            text_lower = raw_text.lower()
            chunk_id = ch.get("chunk_id", "")

            for kw in keywords:
                kw_lower = kw.lower()
                pos = text_lower.find(kw_lower)    # FIX E6: single find() call
                if pos == -1:
                    continue

                # GST mismatch filter
                if field == "bank_gst_mismatch_clues" and "reconciliation of" in text_lower:
                    if "reconciliation of gst" not in text_lower and "reconciliation of sales" not in text_lower:
                        continue

                # FIX E6: use stored pos for snippet, not a second find()
                start = max(0, pos - 20)
                end = pos + len(kw_lower) + 80
                snippet = raw_text[start:end].strip()
                matches.append((snippet, base_conf, chunk_id))
                break  # one keyword per chunk per rule group

    if not matches:
        return {"value": None, "confidence": 0.1, "source_ref": ""}

    best = max(matches, key=lambda x: x[1])
    confidence = min(0.95, best[1] + 0.05 * (len(matches) - 1))

    return {
        "value": [m[0][:200] for m in matches[:5]],
        "confidence": confidence,
        "source_ref": best[2],   # FIX E7: chunk_id stored directly, no re-search needed
    }


def extract_structured(chunks: list[dict]) -> dict[str, Any]:
    """
    Run schema-based regex extraction. Each field has value, confidence, source_ref.
    Returns null + low confidence when a field cannot be extracted.
    """
    result: dict[str, Any] = {}

    for field in ["revenue", "EBITDA", "PAT", "total_debt", "working_capital", "current_ratio", "dscr"]:
        r = _extract_numeric(chunks, field)
        result[field] = {
            "value": r["value"],
            "confidence": r["confidence"],
            "source_ref": r["source_ref"],
        }

    for field in [
        "contingent_liabilities", "related_party_transactions", "auditor_remarks",
        "legal_mentions", "director_promoter_mentions", "bank_gst_mismatch_clues",
    ]:
        r = _extract_qualitative(chunks, field)
        result[field] = {
            "value": r["value"],
            "confidence": r["confidence"],
            "source_ref": r["source_ref"],
        }

    return result