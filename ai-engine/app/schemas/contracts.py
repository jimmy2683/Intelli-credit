from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UploadedFileMetadata(BaseModel):
    file_name: str
    file_path: Optional[str] = None
    doc_type: Optional[str] = None
    uploaded_at: Optional[str] = None


class CompanyDetails(BaseModel):
    company_name: str
    cin_optional: Optional[str] = None
    sector: Optional[str] = None
    promoter_names: List[str] = Field(default_factory=list)


class PipelineInput(BaseModel):
    case_id: Optional[str] = None
    uploaded_file_metadata: List[UploadedFileMetadata] = Field(default_factory=list)
    document_references: Optional[List[Dict[str, Any]]] = None
    parsed_text_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    officer_notes: Optional[str] = None
    company_details: Optional[CompanyDetails] = None
    web_search_context: Optional[Dict[str, Any]] = None
    extracted_facts: Optional[Dict[str, Any]] = None
    risk_flags: Optional[List[Dict[str, Any]]] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    overall_score: Optional[float] = None


class ExtractResponse(BaseModel):
    extracted_facts: Dict[str, Any]
    parsed_text_chunks: List[Dict[str, Any]]
    source: str = "mock"


class ResearchResponse(BaseModel):
    risk_flags: List[Dict[str, Any]]
    secondary_research_signals: Optional[Dict[str, Any]] = None
    source: str = "mock"


class OfficerNoteSignalDetail(BaseModel):
    score: float
    explanations: List[str] = Field(default_factory=list)


class OfficerNoteSignals(BaseModel):
    capacity_utilization: OfficerNoteSignalDetail
    management_quality: OfficerNoteSignalDetail
    operational_health: OfficerNoteSignalDetail
    collection_risk: OfficerNoteSignalDetail
    site_visit_risk: OfficerNoteSignalDetail
    promoter_behavior_score: OfficerNoteSignalDetail
    composite_score: float
    all_explanations: List[str] = Field(default_factory=list)


class OfficerNoteResponse(BaseModel):
    officer_note_signals: OfficerNoteSignals
    source: str = "officer_notes_processor"


class ScoreResponse(BaseModel):
    overall_score: float
    score_breakdown: Dict[str, Any]
    decision: Optional[str] = None
    decision_explanation: Optional[str] = None
    recommended_limit: Optional[float] = None
    recommended_roi: Optional[float] = None
    reasons: Optional[List[str]] = None
    hard_override_applied: Optional[bool] = None
    hard_override_reason: Optional[str] = None
    officer_note_signals: Optional[Dict[str, Any]] = None
    source: str = "mock"


class CamResponse(BaseModel):
    case_id: Optional[str]
    final_decision: str
    recommended_limit: float
    recommended_roi: float
    key_reasons: List[str]
    evidence_summary: str
    cam_doc_path: str
    generated_at: str
    source: str = "mock"

