"""
Schema-based extraction: structured financial facts, confidence scores, and source references.
"""
from __future__ import annotations

import re
from typing import Any

EXTRACTED_FIELDS = [
    "revenue",
    "EBITDA",
    "PAT",
    "total_debt",
    "working_capital",
    "current_ratio",
    "dscr",
    "contingent_liabilities",
    "related_party_transactions",
    "auditor_remarks",
    "director_promoter_mentions",
    "legal_mentions",
    "bank_gst_mismatch_clues",
]

NUMERIC_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "revenue": [
        (r"revenue[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)\s*(?:cr|crore|lakh|million|mn|m)?", 0.85),
        (r"total\s+revenue[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.9),
        (r"sales\s+(?:revenue|turnover)[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.8),
        (r"turnover[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.75),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+revenue", 0.7),
        (r"revenue:\s*Rs\s+([\d,]+(?:\.\d+)?)", 0.9),
    ],
    "EBITDA": [
        (r"EBITDA[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.9),
        (r"earnings\s+before\s+interest[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.85),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+EBITDA", 0.7),
    ],
    "PAT": [
        (r"PAT[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.9),
        (r"profit\s+after\s+tax[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.9),
        (r"net\s+profit[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.8),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+PAT", 0.65),
    ],
    "total_debt": [
        (r"total\s+debt[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.9),
        (r"debt[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.7),
        (r"borrowings[:\s]*[\$₹Rs\.\s]*([\d,]+(?:\.\d+)?)", 0.85),
        (r"([\d,]+(?:\.\d+)?)\s*(?:cr|crore)\s+debt", 0.65),
    ],
    "working_capital": [
        (r"working\s+capital[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.9),
        (r"net\s+working\s+capital[:\s]*[\$₹Rs\.\s]*(-?[\d,]+(?:\.\d+)?)", 0.9),
    ],
    "current_ratio": [
        (r"current\s+ratio[:\s]*([\d.]+)", 0.95),
        (r"current\s+assets\s*/\s*current\s+liabilities[:\s]*([\d.]+)", 0.9),
    ],
    "dscr": [
        (r"DSCR[:\s]*([\d.]+)", 0.95),
        (r"debt\s+service\s+coverage[:\s]*([\d.]+)", 0.9),
    ],
}

QUALITATIVE_KEYWORDS: dict[str, list[tuple[list[str], float]]] = {
    "contingent_liabilities": [
        (["contingent liability", "corporate guarantee", "bank guarantee", "indemnity"], 0.8),
        (["counter guarantee", "performance guarantee", "bid bond"], 0.75),
    ],
    "related_party_transactions": [
        (["related party", "RPT", "intercompany", "promoter entity", "associate"], 0.85),
        (["key management", "director remuneration", "loans to promoters"], 0.8),
    ],
    "auditor_remarks": [
        (["qualification", "adverse", "disclaimer", "material uncertainty"], 0.9),
        (["emphasis of matter", "key audit matter", "going concern"], 0.8),
        (["unmodified", "clean report", "no qualification"], 0.75),
    ],
    "legal_mentions": [
        (["litigation", "lawsuit", "legal notice", "arbitration", "dispute"], 0.9),
        (["court order", "pending case", "contingent on outcome"], 0.85),
    ],
    "director_promoter_mentions": [
        (["director", "promoter", "managing director", "chairman", "board"], 0.7),
        (["KMP", "key managerial personnel", "CFO", "CEO"], 0.75),
    ],
    "bank_gst_mismatch_clues": [
        (["GST mismatch", "sales mismatch", "credit mismatch", "reconciliation"], 0.85),
        (["bank credits", "GST turnover", "declared sales", "actual receipts"], 0.7),
    ],
}


def _parse_number(s: str) -> float | None:
    s = re.sub(r"[, ]", "", str(s))
    try:
        return float(s)
    except ValueError:
        return None


def _extract_numeric(chunks: list[dict], field: str) -> dict[str, Any]:
    patterns = NUMERIC_PATTERNS.get(field, [])
    for pattern, base_conf in patterns:
        for ch in chunks:
            m = re.search(pattern, ch.get("text", ""), re.IGNORECASE)
            if m:
                val = _parse_number(m.group(1))
                if val is not None:
                    return {
                        "value": val,
                        "confidence": base_conf,
                        "source_ref": ch.get("chunk_id", ""),
                    }
    return {"value": None, "confidence": 0.1, "source_ref": ""}


def _extract_qualitative(chunks: list[dict], field: str) -> dict[str, Any]:
    matches: list[tuple[str, float]] = []
    rules = QUALITATIVE_KEYWORDS.get(field, [])
    for keywords, base_conf in rules:
        for ch in chunks:
            text = (ch.get("text") or "").lower()
            for kw in keywords:
                if kw.lower() in text:
                    snippet = text[max(0, text.find(kw) - 20) : text.find(kw) + len(kw) + 80]
                    matches.append((snippet.strip(), base_conf))
                    break
    if not matches:
        return {"value": None, "confidence": 0.1, "source_ref": ""}
    best = max(matches, key=lambda x: x[1])
    chunk_id = ""
    for ch in chunks:
        if best[0][:50] in (ch.get("text") or "").lower():
            chunk_id = ch.get("chunk_id", "")
            break
    return {
        "value": [m[0][:200] for m in matches[:5]],
        "confidence": min(0.95, best[1] + 0.05 * (len(matches) - 1)),
        "source_ref": chunk_id,
    }


def extract_structured(chunks: list[dict]) -> dict[str, Any]:
    """
    Run schema-based extraction. Each field has value, confidence, source_ref.
    Null + low confidence when not extractable.
    """
    result: dict[str, Any] = {}
    doc_sources: list[dict[str, str]] = []
    seen: set[str] = set()

    for ch in chunks:
        ref = ch.get("chunk_id", "")
        fn = ch.get("file_name", "")
        if ref and ref not in seen:
            seen.add(ref)
            doc_sources.append({
                "doc_id": ref,
                "file_name": fn,
                "section": ch.get("doc_type", "unknown"),
                "page_ref": ch.get("page_ref", ""),
            })

    for field in ["revenue", "EBITDA", "PAT", "total_debt", "working_capital", "current_ratio", "dscr"]:
        r = _extract_numeric(chunks, field)
        result[field] = {
            "value": r["value"],
            "confidence": r["confidence"],
            "source_ref": r["source_ref"],
        }

    for field in [
        "contingent_liabilities",
        "related_party_transactions",
        "auditor_remarks",
        "legal_mentions",
        "director_promoter_mentions",
        "bank_gst_mismatch_clues",
    ]:
        r = _extract_qualitative(chunks, field)
        result[field] = {
            "value": r["value"],
            "confidence": r["confidence"],
            "source_ref": r["source_ref"],
        }

    result["document_sources"] = doc_sources

    extracted_entities: list[dict[str, str]] = []
    for ch in chunks:
        for m in re.finditer(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:director|promoter|MD|CEO|CFO)", ch.get("text", "")):
            name = m.group(1).strip()
            if len(name) > 3 and name not in {"The", "A", "An"}:
                extracted_entities.append({
                    "name": name,
                    "type": "person",
                    "role": "director/promoter",
                    "source_ref": ch.get("chunk_id", ""),
                })
    if extracted_entities:
        result["extracted_entities"] = extracted_entities[:20]
    else:
        result["extracted_entities"] = []

    return result
