"""
Research service: runs contradiction detection, risk flag generation, and secondary research agent.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.contracts import PipelineInput

from .contradiction_detector import detect_contradictions
from .pipeline import run_extraction_pipeline
from .research_agent import run_research_agent
from .risk_flags import generate_additional_flags

logger = logging.getLogger(__name__)

# FIX R3: Minimum confidence to act on a web research risk signal.
# Mock/low-quality research has confidence 0.1 — never promote that to a hard flag.
_MIN_WEB_SIGNAL_CONFIDENCE = 0.45


def _to_dict(m: Any) -> dict:
    if hasattr(m, "model_dump"):
        return m.model_dump()
    if isinstance(m, dict):
        return m
    return {}


def run_research(payload: PipelineInput) -> dict[str, Any]:
    """
    Generate risk flags and secondary research signals.

    Priority:
      1. Use pre-extracted facts + chunks if already provided in payload.
      2. Otherwise run full pipeline from uploaded files.
      3. Always run research agent when company_details are present.

    FIX R1: Missing parsed_text_chunks pass-through. When pipeline is called here,
            its output now includes parsed_text_chunks (fixed in pipeline.py), so
            we surface it in the response for downstream stages that need it.

    FIX R2: research_agent call had no try/except — a failure here would crash
            the entire /research endpoint, losing all the risk flags generated so far.

    FIX R3: Web research flags are only created when confidence >= _MIN_WEB_SIGNAL_CONFIDENCE.
            Previously, mock data (confidence 0.1) could create "undisclosed_litigation"
            flags at severity="critical", which is wrong.
    """
    facts = payload.extracted_facts
    chunks = payload.parsed_text_chunks or []
    file_meta = payload.uploaded_file_metadata or payload.document_references or []
    file_meta_list = [_to_dict(m) for m in (file_meta if isinstance(file_meta, list) else [])]

    # FIX R1: track parsed_text_chunks for pass-through
    parsed_text_chunks: list[dict] = chunks

    if facts and chunks:
        contradiction_flags = detect_contradictions(
            facts,
            payload.officer_notes,
            chunks,
            file_meta_list,
        )
        risk_flags = generate_additional_flags(facts, contradiction_flags)
    elif file_meta_list and payload.case_id:
        pipeline_result = run_extraction_pipeline(payload)
        risk_flags = pipeline_result.get("risk_flags", [])
        # FIX R1: carry parsed chunks forward
        parsed_text_chunks = pipeline_result.get("parsed_text_chunks", [])
        # Also update facts so cross-verification below has data to work with
        if not facts:
            facts = pipeline_result.get("extracted_facts", {})
    else:
        risk_flags = []

    secondary_signals: dict[str, Any] = {}
    if payload.company_details:
        cd = _to_dict(payload.company_details)

        doc_lit = any(
            f.get("flag_type") == "litigation_risk" and f.get("severity") in ("high", "critical")
            for f in risk_flags
        )
        doc_aud = any(
            f.get("flag_type") == "auditor_concern" and f.get("severity") in ("high", "critical")
            for f in risk_flags
        )

        # FIX R2: Wrap research agent in try/except — don't let a search failure
        # kill the risk_flags we've already computed.
        try:
            secondary_signals = run_research_agent(
                company_name=cd.get("company_name", ""),
                sector=cd.get("sector"),
                promoter_names=cd.get("promoter_names") or [],
                document_litigation_hint=doc_lit,
                document_auditor_concern=doc_aud,
            )
        except Exception as e:
            logger.warning("Research agent failed — proceeding with document-only flags: %s", e)
            secondary_signals = {}

        # Cross-verify extracted facts with research signals
        if secondary_signals and facts:
            web_summary = secondary_signals.get("web_research_summary") or {}
            web_lit  = web_summary.get("litigation_risk", {})
            web_sent = web_summary.get("sentiment_risk", {})

            # FIX R3: Only create flags when confidence crosses the threshold.
            # Prevents mock/low-quality research from generating critical flags.
            lit_conf  = float(web_lit.get("confidence",  0.0))
            sent_conf = float(web_sent.get("confidence", 0.0))

            if (
                web_lit.get("level") in ("high", "critical")
                and not doc_lit
                and lit_conf >= _MIN_WEB_SIGNAL_CONFIDENCE
            ):
                risk_flags.append({
                    "flag_type": "undisclosed_litigation",
                    "severity": "critical",
                    "description": "Web research reveals severe litigation risk not found in documents.",
                    "evidence_refs": web_lit.get("citations", []),
                    "confidence": lit_conf,
                    "impact_on_score": "Severe penalty to governance and rating.",
                })
                logger.info("Added undisclosed_litigation flag (web confidence=%.2f)", lit_conf)

            if (
                web_sent.get("level") in ("high", "critical")
                and sent_conf >= _MIN_WEB_SIGNAL_CONFIDENCE
            ):
                risk_flags.append({
                    "flag_type": "adverse_reputation_news",
                    "severity": web_sent.get("level"),
                    "description": "Adverse sentiment or news associated with company or promoters.",
                    "evidence_refs": web_sent.get("citations", []),
                    "confidence": sent_conf,
                    "impact_on_score": "Negative pressure on qualitative assessment.",
                })

    return {
        "risk_flags": risk_flags,
        "secondary_research_signals": secondary_signals,
        # FIX R1: always include parsed_text_chunks so /score and /cam have access
        "parsed_text_chunks": parsed_text_chunks,
        "source": "pipeline",
    }