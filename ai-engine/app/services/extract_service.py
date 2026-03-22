"""
Extract service: runs document parsing pipeline and returns structured facts.
"""
from __future__ import annotations

from typing import Any

from app.schemas.contracts import PipelineInput

from .pipeline import run_extraction_pipeline


def run_extract(payload: PipelineInput) -> dict[str, Any]:
    """
    Run full extraction pipeline: parse documents, extract facts, detect contradictions, generate flags.
    Saves to data/parsed/{case_id}/. Returns extracted_facts, parsed_text_chunks, and risk_flags.

    FIX: Use .get() with defaults so this never raises KeyError even if pipeline output
    schema changes. Pipeline now always returns 'parsed_text_chunks' but defensive access
    is still best practice.
    """
    result = run_extraction_pipeline(payload)
    return {
        "extracted_facts": result.get("extracted_facts", {}),
        "parsed_text_chunks": result.get("parsed_text_chunks", []),
        "risk_flags": result.get("risk_flags", []),
        "source": "pipeline",
    }