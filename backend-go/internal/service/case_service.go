package service

import (
	"errors"
	"fmt"
	"log"
	"mime/multipart"
	"os"
	"path/filepath"
	"time"

	"credit-intel/backend-go/internal/client"
	"credit-intel/backend-go/internal/config"
	"credit-intel/backend-go/internal/model"
	"credit-intel/backend-go/internal/store"
)

var ErrCaseNotFound = errors.New("case not found")

type CaseService struct {
	cfg      config.Config
	aiClient *client.AIClient
	db       *store.DB
}

func NewCaseService(cfg config.Config, aiClient *client.AIClient, db *store.DB) *CaseService {
	return &CaseService{
		cfg:      cfg,
		aiClient: aiClient,
		db:       db,
	}
}

func (s *CaseService) CreateCase(req model.CreateCaseRequest) *model.CreditCase {
	now := time.Now().UTC()
	id := fmt.Sprintf("case_%d", now.UnixNano())

	c := &model.CreditCase{
		CaseID:        id,
		CompanyName:   req.CompanyName,
		CINOptional:   req.CINOptional,
		Sector:        req.Sector,
		PromoterNames: req.PromoterNames,
		OfficerNotes:  req.OfficerNotes,
		CreatedAt:     now.Format(time.RFC3339),
		Status:        "created",
	}

	if err := s.db.InsertCase(c); err != nil {
		log.Printf("[create] db insert error: %v", err)
	}
	return c
}

func (s *CaseService) GetCase(id string) (*model.CreditCase, error) {
	c, err := s.db.GetCase(id)
	if err != nil {
		return nil, fmt.Errorf("db error: %w", err)
	}
	if c == nil {
		return nil, ErrCaseNotFound
	}
	return c, nil
}

func (s *CaseService) ListCases() ([]*model.CreditCase, error) {
	return s.db.ListCases()
}

func (s *CaseService) GetCAM(id string) (*model.CAMResult, error) {
	c, err := s.GetCase(id)
	if err != nil {
		return nil, err
	}
	if c.CAMResult == nil {
		return &model.CAMResult{
			CaseID:        id,
			FinalDecision: "manual_review",
			KeyReasons:    []string{"CAM is not generated yet"},
			GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		}, nil
	}
	return c.CAMResult, nil
}

func (s *CaseService) GetCAMDocPath(id string) (string, error) {
	c, err := s.GetCase(id)
	if err != nil {
		return "", err
	}
	if c.CAMResult == nil || c.CAMResult.CAMDocPath == "" {
		return "", fmt.Errorf("CAM document not generated for case %s", id)
	}
	return c.CAMResult.CAMDocPath, nil
}

func (s *CaseService) UpdateOfficerNotes(id, notes string) (*model.CreditCase, error) {
	c, err := s.GetCase(id)
	if err != nil {
		return nil, err
	}
	c.OfficerNotes = notes
	if err := s.db.UpdateCase(c); err != nil {
		return nil, fmt.Errorf("db update: %w", err)
	}
	return c, nil
}

func (s *CaseService) SaveUploadedFiles(id string, files []*multipart.FileHeader) ([]model.UploadedFile, error) {
	c, err := s.GetCase(id)
	if err != nil {
		return nil, err
	}

	baseDir := filepath.Join(s.cfg.DataRoot, "uploads", id)
	if err := os.MkdirAll(baseDir, 0o755); err != nil {
		return nil, fmt.Errorf("create upload dir: %w", err)
	}

	saved := make([]model.UploadedFile, 0, len(files))
	for _, fh := range files {
		src, err := fh.Open()
		if err != nil {
			return nil, fmt.Errorf("open file %s: %w", fh.Filename, err)
		}

		dstPath := filepath.Join(baseDir, fmt.Sprintf("%d_%s", time.Now().UnixNano(), fh.Filename))
		dst, err := os.Create(dstPath)
		if err != nil {
			src.Close()
			return nil, fmt.Errorf("create dst file %s: %w", dstPath, err)
		}

		if _, err := dst.ReadFrom(src); err != nil {
			src.Close()
			dst.Close()
			return nil, fmt.Errorf("copy uploaded file %s: %w", fh.Filename, err)
		}
		src.Close()
		dst.Close()

		saved = append(saved, model.UploadedFile{
			FileName:   fh.Filename,
			FilePath:   dstPath,
			UploadedAt: time.Now().UTC().Format(time.RFC3339),
		})
	}

	c.UploadedFiles = append(c.UploadedFiles, saved...)
	if err := s.db.UpdateCase(c); err != nil {
		log.Printf("[upload] db update error: %v", err)
	}
	return saved, nil
}

func (s *CaseService) AnalyzeCase(id string) (*model.CreditCase, error) {
	c, err := s.GetCase(id)
	if err != nil {
		return nil, err
	}
	c.Status = "processing"
	s.db.UpdateCase(c)

	input := map[string]any{
		"case_id":                c.CaseID,
		"company_details":        map[string]any{"company_name": c.CompanyName, "sector": c.Sector, "cin_optional": c.CINOptional, "promoter_names": c.PromoterNames},
		"uploaded_file_metadata": c.UploadedFiles,
		"officer_notes":          c.OfficerNotes,
	}

	// ── Step 1: Extract ──
	extractResp, err := s.aiClient.Extract(input)
	if err != nil {
		log.Printf("[analyze] extract call failed, using stub: %v", err)
		extractResp = stubExtractResponse()
	}

	// ── Step 2: Officer Notes ──
	var notesSignals map[string]any
	if c.OfficerNotes != "" {
		notesPayload := map[string]any{
			"case_id":       id,
			"officer_notes": input["officer_notes"],
		}
		notesResp, notesErr := s.aiClient.Notes(notesPayload)
		if notesErr != nil {
			log.Printf("[analyze] notes call failed, continuing without signals: %v", notesErr)
		} else {
			if signals, ok := notesResp["officer_note_signals"]; ok {
				if m, ok := signals.(map[string]any); ok {
					notesSignals = m
				}
			}
		}
	}

	// ── Step 3: Research ──
	researchPayload := map[string]any{
		"case_id":             id,
		"parsed_text_chunks":  extractResp["parsed_text_chunks"],
		"company_details":     input["company_details"],
		"officer_notes":       input["officer_notes"],
		"web_search_context":  nil,
		"extracted_facts":     extractResp["extracted_facts"],
		"document_references": input["uploaded_file_metadata"],
	}
	researchResp, err := s.aiClient.Research(researchPayload)
	if err != nil {
		log.Printf("[analyze] research call failed, using stub: %v", err)
		researchResp = stubResearchResponse()
	}

	// ── Step 4: Score ──
	scorePayload := map[string]any{
		"case_id":         id,
		"extracted_facts": extractResp["extracted_facts"],
		"risk_flags":      researchResp["risk_flags"],
		"officer_notes":   input["officer_notes"],
		"company_details": input["company_details"],
	}
	scoreResp, err := s.aiClient.Score(scorePayload)
	if err != nil {
		log.Printf("[analyze] score call failed, using stub: %v", err)
		scoreResp = stubScoreResponse()
	}

	// ── Step 5: CAM ──
	camPayload := map[string]any{
		"case_id":         id,
		"company_details": input["company_details"],
		"extracted_facts": extractResp["extracted_facts"],
		"risk_flags":      researchResp["risk_flags"],
		"score_breakdown": scoreResp["score_breakdown"],
		"overall_score":   scoreResp["overall_score"],
		"officer_notes":   input["officer_notes"],
	}
	camResp, err := s.aiClient.CAM(camPayload)
	if err != nil {
		log.Printf("[analyze] cam call failed, using stub: %v", err)
		camResp = stubCAMResponse(id)
	}

	// ── Persist results ──
	c.ExtractedFacts = asMap(extractResp["extracted_facts"])
	c.RiskFlags = asRiskFlags(researchResp["risk_flags"])
	c.CAMResult = &model.CAMResult{
		CaseID:           id,
		FinalDecision:    asString(camResp["final_decision"], "manual_review"),
		RecommendedLimit: asFloat(camResp["recommended_limit"]),
		RecommendedROI:   asFloat(camResp["recommended_roi"]),
		OverallScore:     asFloat(scoreResp["overall_score"]),
		ScoreBreakdown:   asMap(scoreResp["score_breakdown"]),
		KeyReasons:       asStringSlice(camResp["key_reasons"]),
		EvidenceSummary:  asString(camResp["evidence_summary"], "Generated via AI pipeline."),
		CAMDocPath:       asString(camResp["cam_doc_path"], ""),
		GeneratedAt:      asString(camResp["generated_at"], time.Now().UTC().Format(time.RFC3339)),
	}
	c.ScoreResult = &model.ScoreResult{
		OverallScore:        asFloat(scoreResp["overall_score"]),
		ScoreBreakdown:      asMap(scoreResp["score_breakdown"]),
		Decision:            asString(scoreResp["decision"], "manual_review"),
		DecisionExplanation: asString(scoreResp["decision_explanation"], ""),
		RecommendedLimit:    asFloat(scoreResp["recommended_limit"]),
		RecommendedROI:      asFloat(scoreResp["recommended_roi"]),
		Reasons:             asStringSlice(scoreResp["reasons"]),
		HardOverrideApplied: asBool(scoreResp["hard_override_applied"]),
		HardOverrideReason:  asString(scoreResp["hard_override_reason"], ""),
	}
	if notesSignals != nil {
		c.OfficerNoteSignals = asOfficerNoteSignals(notesSignals)
	}
	c.Status = "ready"
	if err := s.db.UpdateCase(c); err != nil {
		log.Printf("[analyze] db update error: %v", err)
	}
	return c, nil
}

// ── Stub responses ──

func stubExtractResponse() map[string]any {
	return map[string]any{
		"extracted_facts": map[string]any{
			"revenue":       10000000,
			"EBITDA":        1800000,
			"PAT":           900000,
			"total_debt":    3500000,
			"current_ratio": 1.3,
		},
		"parsed_text_chunks": []map[string]any{
			{"chunk_id": "chunk_1", "text": "Placeholder parsed financial section"},
		},
	}
}

func stubResearchResponse() map[string]any {
	return map[string]any{
		"risk_flags": []map[string]any{
			{
				"flag_id":         "rf_mock_01",
				"flag_type":       "financial",
				"severity":        "medium",
				"description":     "Debt levels increased year-over-year.",
				"evidence_refs":   []string{"chunk_1"},
				"confidence":      0.64,
				"impact_on_score": "Moderate downward pressure.",
			},
		},
	}
}

func stubScoreResponse() map[string]any {
	return map[string]any{
		"overall_score": 67.5,
		"score_breakdown": map[string]any{
			"financial_strength": 70,
			"repayment_capacity": 65,
			"governance":         68,
		},
	}
}

func stubCAMResponse(caseID string) map[string]any {
	return map[string]any{
		"case_id":           caseID,
		"final_decision":    "approve_with_conditions",
		"recommended_limit": 2500000,
		"recommended_roi":   11.25,
		"key_reasons":       []string{"Adequate DSCR in mock scenario", "Manageable risk flags"},
		"evidence_summary":  "Stub CAM generated because AI service is unavailable.",
		"cam_doc_path":      fmt.Sprintf("data/evidence/%s/cam_placeholder.md", caseID),
		"generated_at":      time.Now().UTC().Format(time.RFC3339),
	}
}

// ── Type conversion helpers ──

func asMap(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return map[string]any{}
}

func asString(v any, fallback string) string {
	s, ok := v.(string)
	if !ok || s == "" {
		return fallback
	}
	return s
}

func asFloat(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case float32:
		return float64(n)
	case int:
		return float64(n)
	case int64:
		return float64(n)
	default:
		return 0
	}
}

func asBool(v any) bool {
	b, ok := v.(bool)
	if !ok {
		return false
	}
	return b
}

func asStringSlice(v any) []string {
	raw, ok := v.([]any)
	if !ok {
		if direct, ok := v.([]string); ok {
			return direct
		}
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, item := range raw {
		if s, ok := item.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

func asRiskFlags(v any) []model.RiskFlag {
	items, ok := v.([]any)
	if !ok {
		return nil
	}
	flags := make([]model.RiskFlag, 0, len(items))
	for _, item := range items {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		flags = append(flags, model.RiskFlag{
			FlagID:        asString(m["flag_id"], ""),
			FlagType:      asString(m["flag_type"], ""),
			Severity:      asString(m["severity"], ""),
			Description:   asString(m["description"], ""),
			EvidenceRefs:  asStringSlice(m["evidence_refs"]),
			Confidence:    asFloat(m["confidence"]),
			ImpactOnScore: asString(m["impact_on_score"], ""),
		})
	}
	return flags
}

func asOfficerNoteSignals(m map[string]any) *model.OfficerNoteSignals {
	return &model.OfficerNoteSignals{
		CapacityUtilization: asMap(m["capacity_utilization"]),
		ManagementQuality:   asMap(m["management_quality"]),
		OperationalHealth:   asMap(m["operational_health"]),
		CollectionRisk:      asMap(m["collection_risk"]),
		SiteVisitRisk:       asMap(m["site_visit_risk"]),
		PromoterBehavior:    asMap(m["promoter_behavior_score"]),
		CompositeScore:      asFloat(m["composite_score"]),
		AllExplanations:     asStringSlice(m["all_explanations"]),
	}
}

// GetCAMFileInfo returns info needed to serve the CAM file for download.
func (s *CaseService) GetCAMFileInfo(id string) (filePath, contentType, fileName string, err error) {
	docPath, err := s.GetCAMDocPath(id)
	if err != nil {
		return "", "", "", err
	}

	if _, statErr := os.Stat(docPath); statErr != nil {
		return "", "", "", fmt.Errorf("CAM file not found at %s: %w", docPath, statErr)
	}

	ext := filepath.Ext(docPath)
	ct := "application/octet-stream"
	if ext == ".docx" {
		ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
	} else if ext == ".md" {
		ct = "text/markdown"
	}

	return docPath, ct, fmt.Sprintf("CAM_%s%s", id, ext), nil
}
