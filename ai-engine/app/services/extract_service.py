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
    Saves to data/parsed/{case_id}/. Returns extracted_facts and parsed_text_chunks.
    """
    result = run_extraction_pipeline(payload)
    return {
        "extracted_facts": result["extracted_facts"],
        "parsed_text_chunks": result["parsed_text_chunks"],
        "source": "pipeline",
    }
