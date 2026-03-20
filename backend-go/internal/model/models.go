package model

type CreateCaseRequest struct {
	CompanyName   string   `json:"company_name"`
	CINOptional   string   `json:"cin_optional,omitempty"`
	Sector        string   `json:"sector"`
	PromoterNames []string `json:"promoter_names,omitempty"`
	OfficerNotes  string   `json:"officer_notes,omitempty"`
}

type UpdateNotesRequest struct {
	OfficerNotes string `json:"officer_notes"`
}

type UploadedFile struct {
	FileName   string `json:"file_name"`
	FilePath   string `json:"file_path"`
	DocType    string `json:"doc_type,omitempty"`
	UploadedAt string `json:"uploaded_at"`
}

type ExtractedFacts map[string]any

type RiskFlag struct {
	FlagID        string   `json:"flag_id,omitempty"`
	FlagType      string   `json:"flag_type,omitempty"`
	Severity      string   `json:"severity,omitempty"`
	Description   string   `json:"description,omitempty"`
	EvidenceRefs  []string `json:"evidence_refs,omitempty"`
	Confidence    float64  `json:"confidence,omitempty"`
	ImpactOnScore string   `json:"impact_on_score,omitempty"`
}

type OfficerNoteSignals struct {
	CapacityUtilization  map[string]any `json:"capacity_utilization,omitempty"`
	ManagementQuality    map[string]any `json:"management_quality,omitempty"`
	OperationalHealth    map[string]any `json:"operational_health,omitempty"`
	CollectionRisk       map[string]any `json:"collection_risk,omitempty"`
	SiteVisitRisk        map[string]any `json:"site_visit_risk,omitempty"`
	PromoterBehavior     map[string]any `json:"promoter_behavior_score,omitempty"`
	CompositeScore       float64        `json:"composite_score,omitempty"`
	AllExplanations      []string       `json:"all_explanations,omitempty"`
}

type ScoreResult struct {
	OverallScore        float64            `json:"overall_score,omitempty"`
	ScoreBreakdown      map[string]any     `json:"score_breakdown,omitempty"`
	Decision            string             `json:"decision,omitempty"`
	DecisionExplanation string             `json:"decision_explanation,omitempty"`
	RecommendedLimit    float64            `json:"recommended_limit,omitempty"`
	RecommendedROI      float64            `json:"recommended_roi,omitempty"`
	Reasons             []string           `json:"reasons,omitempty"`
	HardOverrideApplied bool               `json:"hard_override_applied,omitempty"`
	HardOverrideReason  string             `json:"hard_override_reason,omitempty"`
	OfficerNoteSignals  *OfficerNoteSignals `json:"officer_note_signals,omitempty"`
}

type CAMResult struct {
	CaseID           string         `json:"case_id,omitempty"`
	FinalDecision    string         `json:"final_decision,omitempty"`
	RecommendedLimit float64        `json:"recommended_limit,omitempty"`
	RecommendedROI   float64        `json:"recommended_roi,omitempty"`
	OverallScore     float64        `json:"overall_score,omitempty"`
	ScoreBreakdown   map[string]any `json:"score_breakdown,omitempty"`
	KeyReasons       []string       `json:"key_reasons,omitempty"`
	EvidenceSummary  string         `json:"evidence_summary,omitempty"`
	CAMDocPath       string         `json:"cam_doc_path,omitempty"`
	GeneratedAt      string         `json:"generated_at,omitempty"`
}

type CreditCase struct {
	CaseID             string              `json:"case_id"`
	CompanyName        string              `json:"company_name"`
	CINOptional        string              `json:"cin_optional,omitempty"`
	Sector             string              `json:"sector,omitempty"`
	PromoterNames      []string            `json:"promoter_names,omitempty"`
	UploadedFiles      []UploadedFile      `json:"uploaded_files,omitempty"`
	OfficerNotes       string              `json:"officer_notes,omitempty"`
	CreatedAt          string              `json:"created_at"`
	Status             string              `json:"status"`
	ExtractedFacts     ExtractedFacts      `json:"extracted_facts,omitempty"`
	RiskFlags          []RiskFlag          `json:"risk_flags,omitempty"`
	CAMResult          *CAMResult          `json:"cam_result,omitempty"`
	ScoreResult        *ScoreResult        `json:"score_result,omitempty"`
	OfficerNoteSignals *OfficerNoteSignals `json:"officer_note_signals,omitempty"`
}
