import logging

from fastapi import APIRouter

from app.schemas.contracts import (
    CamResponse,
    ExtractResponse,
    OfficerNoteResponse,
    PipelineInput,
    ResearchResponse,
    ScoreResponse,
)
from app.services import mock_pipeline
from app.services.cam_service import run_cam
from app.services.extract_service import run_extract
from app.services.officer_notes import process_notes
from app.services.research_service import run_research
from app.services.score_service import run_score

logger = logging.getLogger(__name__)
router = APIRouter()


def _safe_extract(payload: PipelineInput) -> ExtractResponse:
    try:
        output = run_extract(payload)
        return ExtractResponse(**output)
    except Exception as e:
        logger.warning("Extraction pipeline failed, using mock: %s", e)
        output = mock_pipeline.extract(payload)
        return ExtractResponse(**output, source="mock")


def _safe_research(payload: PipelineInput) -> ResearchResponse:
    try:
        output = run_research(payload)
        return ResearchResponse(**output)
    except Exception as e:
        logger.warning("Research pipeline failed, using mock: %s", e)
        output = mock_pipeline.research(payload)
        return ResearchResponse(**output, source="mock")


def _safe_score(payload: PipelineInput) -> ScoreResponse:
    try:
        output = run_score(payload)
        return ScoreResponse(**output)
    except Exception as e:
        logger.warning("Scoring engine failed, using mock: %s", e)
        output = mock_pipeline.score(payload)
        return ScoreResponse(**output, source="mock")


def _safe_cam(payload: PipelineInput) -> CamResponse:
    try:
        output = run_cam(payload)
        return CamResponse(**output)
    except Exception as e:
        logger.warning("CAM service failed, using mock: %s", e)
        output = mock_pipeline.generate_cam(payload)
        return CamResponse(**output, source="mock")


@router.post("/extract", response_model=ExtractResponse)
def extract(payload: PipelineInput) -> ExtractResponse:
    return _safe_extract(payload)


@router.post("/research", response_model=ResearchResponse)
def research(payload: PipelineInput) -> ResearchResponse:
    return _safe_research(payload)


@router.post("/score", response_model=ScoreResponse)
def score(payload: PipelineInput) -> ScoreResponse:
    return _safe_score(payload)


@router.post("/cam", response_model=CamResponse)
def cam(payload: PipelineInput) -> CamResponse:
    return _safe_cam(payload)


@router.post("/notes", response_model=OfficerNoteResponse)
def notes(payload: PipelineInput) -> OfficerNoteResponse:
    """Process officer notes into structured risk signals."""
    try:
        signals = process_notes(payload.officer_notes)
        return OfficerNoteResponse(officer_note_signals=signals)
    except Exception as e:
        logger.warning("Officer notes processing failed: %s", e)
        signals = process_notes(None)  # Returns neutral defaults
        return OfficerNoteResponse(officer_note_signals=signals, source="fallback")

