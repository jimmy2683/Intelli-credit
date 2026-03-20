package store

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"

	"credit-intel/backend-go/internal/model"
)

// DB wraps the SQLite connection.
type DB struct {
	conn *sql.DB
}

// Open creates or opens the SQLite database at the given path and runs migrations.
func Open(dbPath string) (*DB, error) {
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, fmt.Errorf("create db dir: %w", err)
	}

	conn, err := sql.Open("sqlite", dbPath+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	conn.SetMaxOpenConns(1) // SQLite single-writer

	db := &DB{conn: conn}
	if err := db.migrate(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("migrate: %w", err)
	}
	return db, nil
}

// Close shuts down the db connection.
func (db *DB) Close() error { return db.conn.Close() }

// ── Schema ──

func (db *DB) migrate() error {
	schema := `
	CREATE TABLE IF NOT EXISTS cases (
		case_id            TEXT PRIMARY KEY,
		company_name       TEXT NOT NULL,
		cin_optional       TEXT DEFAULT '',
		sector             TEXT DEFAULT '',
		promoter_names     TEXT DEFAULT '[]',
		officer_notes      TEXT DEFAULT '',
		created_at         TEXT NOT NULL,
		status             TEXT NOT NULL DEFAULT 'created',
		uploaded_files     TEXT DEFAULT '[]',
		extracted_facts    TEXT DEFAULT '{}',
		risk_flags         TEXT DEFAULT '[]',
		cam_result         TEXT DEFAULT 'null',
		score_result       TEXT DEFAULT 'null',
		officer_note_signals TEXT DEFAULT 'null'
	);`
	_, err := db.conn.Exec(schema)
	return err
}

// ── CRUD ──

// InsertCase creates a new case row.
func (db *DB) InsertCase(c *model.CreditCase) error {
	promoters, _ := json.Marshal(c.PromoterNames)
	files, _ := json.Marshal(c.UploadedFiles)
	facts, _ := json.Marshal(c.ExtractedFacts)
	flags, _ := json.Marshal(c.RiskFlags)
	cam, _ := json.Marshal(c.CAMResult)
	score, _ := json.Marshal(c.ScoreResult)
	signals, _ := json.Marshal(c.OfficerNoteSignals)

	_, err := db.conn.Exec(`
		INSERT OR REPLACE INTO cases (
			case_id, company_name, cin_optional, sector, promoter_names,
			officer_notes, created_at, status, uploaded_files,
			extracted_facts, risk_flags, cam_result, score_result, officer_note_signals
		) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
		c.CaseID, c.CompanyName, c.CINOptional, c.Sector, string(promoters),
		c.OfficerNotes, c.CreatedAt, c.Status, string(files),
		string(facts), string(flags), string(cam), string(score), string(signals),
	)
	return err
}

// GetCase retrieves a single case by ID.
func (db *DB) GetCase(id string) (*model.CreditCase, error) {
	row := db.conn.QueryRow(`SELECT
		case_id, company_name, cin_optional, sector, promoter_names,
		officer_notes, created_at, status, uploaded_files,
		extracted_facts, risk_flags, cam_result, score_result, officer_note_signals
		FROM cases WHERE case_id = ?`, id)

	var (
		c                                                                 model.CreditCase
		promoters, files, facts, flags, cam, scoreJSON, signalsJSON string
	)
	err := row.Scan(
		&c.CaseID, &c.CompanyName, &c.CINOptional, &c.Sector, &promoters,
		&c.OfficerNotes, &c.CreatedAt, &c.Status, &files,
		&facts, &flags, &cam, &scoreJSON, &signalsJSON,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	json.Unmarshal([]byte(promoters), &c.PromoterNames)
	json.Unmarshal([]byte(files), &c.UploadedFiles)
	json.Unmarshal([]byte(facts), &c.ExtractedFacts)
	json.Unmarshal([]byte(flags), &c.RiskFlags)
	if cam != "null" && cam != "" {
		var camResult model.CAMResult
		if json.Unmarshal([]byte(cam), &camResult) == nil {
			c.CAMResult = &camResult
		}
	}
	if scoreJSON != "null" && scoreJSON != "" {
		var sr model.ScoreResult
		if json.Unmarshal([]byte(scoreJSON), &sr) == nil {
			c.ScoreResult = &sr
		}
	}
	if signalsJSON != "null" && signalsJSON != "" {
		var sig model.OfficerNoteSignals
		if json.Unmarshal([]byte(signalsJSON), &sig) == nil {
			c.OfficerNoteSignals = &sig
		}
	}

	return &c, nil
}

// UpdateCase persists all fields of an existing case.
func (db *DB) UpdateCase(c *model.CreditCase) error {
	return db.InsertCase(c) // INSERT OR REPLACE
}

// ListCaseIDs returns all case IDs in the database.
func (db *DB) ListCaseIDs() ([]string, error) {
	rows, err := db.conn.Query("SELECT case_id FROM cases ORDER BY created_at DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// CaseExists checks if a case with the given ID exists.
func (db *DB) CaseExists(id string) (bool, error) {
	var count int
	err := db.conn.QueryRow("SELECT COUNT(1) FROM cases WHERE case_id = ?", id).Scan(&count)
	return count > 0, err
}

// ── Seeding ──

// SeedSampleData inserts the two demo cases if they don't already exist.
func (db *DB) SeedSampleData() {
	for _, sample := range sampleCases() {
		exists, err := db.CaseExists(sample.CaseID)
		if err != nil {
			log.Printf("[seed] check error for %s: %v", sample.CaseID, err)
			continue
		}
		if exists {
			continue
		}
		if err := db.InsertCase(sample); err != nil {
			log.Printf("[seed] insert error for %s: %v", sample.CaseID, err)
		} else {
			log.Printf("[seed] seeded demo case: %s (%s)", sample.CaseID, sample.CompanyName)
		}
	}
}

func sampleCases() []*model.CreditCase {
	now := time.Now().UTC().Format(time.RFC3339)

	healthy := &model.CreditCase{
		CaseID:        "demo_healthy_001",
		CompanyName:   "Pranav Textiles Pvt Ltd",
		CINOptional:   "U17120MH2015PTC123456",
		Sector:        "Textiles & Apparel",
		PromoterNames: []string{"Rajesh Mehta", "Sunita Mehta"},
		OfficerNotes:  "Factory operating at 85% capacity. Plant expansion visible — new weaving unit. Management cooperative and transparent. Inventory tallied. Debtor collection healthy. Promoter track record strong (15+ yrs).",
		CreatedAt:     now,
		Status:        "ready",
		UploadedFiles: []model.UploadedFile{
			{FileName: "AnnualReport_FY2025.pdf", FilePath: "/data/uploads/demo_healthy_001/AnnualReport_FY2025.pdf", DocType: "Annual Report", UploadedAt: now},
			{FileName: "BankStatement_Q4FY25.pdf", FilePath: "/data/uploads/demo_healthy_001/BankStatement_Q4FY25.pdf", DocType: "Bank Statement", UploadedAt: now},
			{FileName: "GST_Returns_FY25.pdf", FilePath: "/data/uploads/demo_healthy_001/GST_Returns_FY25.pdf", DocType: "GST Returns", UploadedAt: now},
			{FileName: "AuditReport_FY2025.pdf", FilePath: "/data/uploads/demo_healthy_001/AuditReport_FY2025.pdf", DocType: "Audit Report", UploadedAt: now},
		},
		ExtractedFacts: map[string]any{
			"revenue":       map[string]any{"value": 420000000, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "P&L Statement, Page 12", "confidence": 0.95, "snippet": "Total revenue from operations stood at ₹42.00 Crore for the financial year ending March 2025."},
			"EBITDA":        map[string]any{"value": 75600000, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "P&L Statement, Page 12", "confidence": 0.92, "snippet": "EBITDA of ₹7.56 Crore represents an 18% margin improvement."},
			"PAT":           map[string]any{"value": 37800000, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "P&L Statement, Page 13", "confidence": 0.93, "snippet": "Profit After Tax was ₹3.78 Crore."},
			"total_debt":    map[string]any{"value": 126000000, "source_ref": "AuditReport_FY2025.pdf", "page_ref": "Balance Sheet, Page 8", "confidence": 0.91, "snippet": "Total borrowings aggregated to ₹12.60 Crore."},
			"current_ratio": map[string]any{"value": 1.65, "source_ref": "AuditReport_FY2025.pdf", "page_ref": "Schedule of Assets, Page 9", "confidence": 0.88, "snippet": "Current ratio of 1.65."},
			"dscr":          map[string]any{"value": 1.45, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "Notes to Accounts, Page 22", "confidence": 0.85, "snippet": "DSCR computed at 1.45x."},
		},
		RiskFlags: []model.RiskFlag{
			{FlagID: "rf_h_01", FlagType: "revenue_gst_variance", Severity: "low", Description: "Minor variance of 3.6% between reported revenue and GST turnover.", EvidenceRefs: []string{"AnnualReport_FY2025.pdf:P12", "GST_Returns_FY25.pdf:Summary"}, Confidence: 0.72, ImpactOnScore: "Minimal."},
			{FlagID: "rf_h_02", FlagType: "sector_outlook", Severity: "low", Description: "Textile sector facing moderate headwinds but domestic demand stable.", EvidenceRefs: []string{"Secondary Research"}, Confidence: 0.65, ImpactOnScore: "Low."},
			{FlagID: "rf_h_03", FlagType: "concentration_risk", Severity: "medium", Description: "Top 3 customers account for 45% of revenue.", EvidenceRefs: []string{"AnnualReport_FY2025.pdf:P18"}, Confidence: 0.78, ImpactOnScore: "Moderate."},
		},
		CAMResult: &model.CAMResult{
			CaseID: "demo_healthy_001", FinalDecision: "approve", RecommendedLimit: 63000000, RecommendedROI: 12.5, OverallScore: 78.4,
			ScoreBreakdown: map[string]any{"financial_strength": 82, "cash_flow": 80, "governance": 72, "contradiction_severity": 88, "secondary_research": 75, "officer_note": 84},
			KeyReasons:      []string{"Strong revenue growth with 18% EBITDA margin", "DSCR of 1.45x", "Clean audit report", "Plant expansion; management cooperative", "Stable domestic demand"},
			EvidenceSummary: "Overall score 78.4 meets approve threshold (≥70). Solid financial health with consistent revenue growth.",
			GeneratedAt:     now,
		},
		ScoreResult: &model.ScoreResult{
			OverallScore:        78.4,
			ScoreBreakdown:      map[string]any{"financial_strength": 82, "cash_flow": 80, "governance": 72, "contradiction_severity": 88, "secondary_research": 75, "officer_note": 84},
			Decision:            "approve",
			DecisionExplanation: "Overall score 78.4 meets approve threshold (≥70).",
			RecommendedLimit:    63000000, RecommendedROI: 12.5,
			Reasons:             []string{"Financial: Strong revenue growth with healthy 18% EBITDA margin", "Cash flow: DSCR of 1.45x", "Governance: Clean audit report", "Officer: Plant expansion; management cooperative"},
		},
		OfficerNoteSignals: &model.OfficerNoteSignals{
			CapacityUtilization: map[string]any{"score": 85, "explanations": []any{"Running at 85% capacity", "Plant expansion visible"}},
			ManagementQuality:   map[string]any{"score": 88, "explanations": []any{"Cooperative", "Transparent"}},
			OperationalHealth:   map[string]any{"score": 86, "explanations": []any{"Modern machinery", "Well-maintained"}},
			CollectionRisk:      map[string]any{"score": 80, "explanations": []any{"Healthy receivables"}},
			SiteVisitRisk:       map[string]any{"score": 85, "explanations": []any{"Inventory tallied with books"}},
			PromoterBehavior:    map[string]any{"score": 82, "explanations": []any{"Strong promoter track record (15+ years)"}},
			CompositeScore:      84.3,
			AllExplanations:     []string{"85% capacity", "Management cooperative", "Modern machinery", "Healthy receivables", "Inventory verified", "Strong promoter"},
		},
	}

	risky := &model.CreditCase{
		CaseID:        "demo_risky_002",
		CompanyName:   "Apex Steel & Alloys Ltd",
		CINOptional:   "L27100DL2008PLC198765",
		Sector:        "Steel & Metals",
		PromoterNames: []string{"Vikram Choudhary", "Deepak Choudhary"},
		OfficerNotes:  "Factory at 40% capacity. Outdated equipment. Promoter evasive about related-party transactions. Debtor collection weak. Stock mismatch observed. Promoter lifestyle extravagant. Ongoing litigation in Delhi High Court.",
		CreatedAt:     now,
		Status:        "ready",
		UploadedFiles: []model.UploadedFile{
			{FileName: "AnnualReport_FY2025.pdf", FilePath: "/data/uploads/demo_risky_002/AnnualReport_FY2025.pdf", DocType: "Annual Report", UploadedAt: now},
			{FileName: "BankStatement_FY25.pdf", FilePath: "/data/uploads/demo_risky_002/BankStatement_FY25.pdf", DocType: "Bank Statement", UploadedAt: now},
			{FileName: "GST_GSTR3B_FY25.pdf", FilePath: "/data/uploads/demo_risky_002/GST_GSTR3B_FY25.pdf", DocType: "GST Returns", UploadedAt: now},
			{FileName: "AuditReport_FY2025.pdf", FilePath: "/data/uploads/demo_risky_002/AuditReport_FY2025.pdf", DocType: "Audit Report", UploadedAt: now},
			{FileName: "LegalNotice_Litigation.pdf", FilePath: "/data/uploads/demo_risky_002/LegalNotice_Litigation.pdf", DocType: "Legal", UploadedAt: now},
		},
		ExtractedFacts: map[string]any{
			"revenue":       map[string]any{"value": 285000000, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "P&L, Page 10", "confidence": 0.89, "snippet": "Revenue declined to ₹28.50 Crore, a 19% decline."},
			"EBITDA":        map[string]any{"value": 22800000, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "P&L, Page 10", "confidence": 0.86, "snippet": "EBITDA of ₹2.28 Crore, 8% margin vs sector average 14%."},
			"PAT":           map[string]any{"value": -8500000, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "P&L, Page 11", "confidence": 0.91, "snippet": "Net loss of ₹0.85 Crore."},
			"total_debt":    map[string]any{"value": 224000000, "source_ref": "AuditReport_FY2025.pdf", "page_ref": "Balance Sheet, Page 7", "confidence": 0.93, "snippet": "Total borrowings ₹22.40 Crore."},
			"current_ratio": map[string]any{"value": 0.82, "source_ref": "AuditReport_FY2025.pdf", "page_ref": "Schedule, Page 8", "confidence": 0.90, "snippet": "Current ratio 0.82."},
			"dscr":          map[string]any{"value": 0.65, "source_ref": "AnnualReport_FY2025.pdf", "page_ref": "Notes, Page 20", "confidence": 0.87, "snippet": "DSCR of 0.65x, below covenant 1.25x."},
			"gst_turnover":  map[string]any{"value": 189000000, "source_ref": "GST_GSTR3B_FY25.pdf", "page_ref": "Summary", "confidence": 0.92, "snippet": "GST turnover ₹18.90 Crore — 33.7% variance from revenue."},
		},
		RiskFlags: []model.RiskFlag{
			{FlagID: "rf_r_01", FlagType: "revenue_gst_mismatch", Severity: "critical", Description: "Revenue-GST mismatch of 33.7%. Potential revenue inflation.", EvidenceRefs: []string{"AnnualReport_FY2025.pdf:P10", "GST_GSTR3B_FY25.pdf:Summary"}, Confidence: 0.92, ImpactOnScore: "Severe — triggers hard override."},
			{FlagID: "rf_r_02", FlagType: "bank_revenue_divergence", Severity: "high", Description: "Bank credit turnover only 53% of reported revenue.", EvidenceRefs: []string{"BankStatement_FY25.pdf:CreditSummary"}, Confidence: 0.88, ImpactOnScore: "High — corroborates GST mismatch."},
			{FlagID: "rf_r_03", FlagType: "auditor_qualification", Severity: "high", Description: "Qualified opinion on related-party and inventory.", EvidenceRefs: []string{"AuditReport_FY2025.pdf:P2"}, Confidence: 0.95, ImpactOnScore: "High — governance concern."},
			{FlagID: "rf_r_04", FlagType: "liquidity_stress", Severity: "high", Description: "Current ratio 0.82, negative working capital.", EvidenceRefs: []string{"AuditReport_FY2025.pdf:P8"}, Confidence: 0.90, ImpactOnScore: "High."},
			{FlagID: "rf_r_05", FlagType: "dscr_breach", Severity: "critical", Description: "DSCR of 0.65x below 1.0x threshold.", EvidenceRefs: []string{"AnnualReport_FY2025.pdf:P20"}, Confidence: 0.87, ImpactOnScore: "Severe — triggers hard override."},
			{FlagID: "rf_r_06", FlagType: "litigation_risk", Severity: "high", Description: "Ongoing litigation against promoter for alleged fund diversion.", EvidenceRefs: []string{"LegalNotice_Litigation.pdf:P1-3"}, Confidence: 0.82, ImpactOnScore: "High."},
			{FlagID: "rf_r_07", FlagType: "inventory_mismatch", Severity: "medium", Description: "Physical inventory discrepancies vs book records.", EvidenceRefs: []string{"Officer Site Visit Notes"}, Confidence: 0.74, ImpactOnScore: "Medium."},
		},
		CAMResult: &model.CAMResult{
			CaseID: "demo_risky_002", FinalDecision: "decline", RecommendedLimit: 0, RecommendedROI: 0, OverallScore: 31.2,
			ScoreBreakdown: map[string]any{"financial_strength": 25, "cash_flow": 18, "governance": 30, "contradiction_severity": 15, "secondary_research": 40, "officer_note": 28},
			KeyReasons:      []string{"Net loss; EBITDA 8% vs sector 14%", "DSCR 0.65x below 1.0x", "Revenue-GST mismatch 33.7%", "Auditor qualification", "Litigation against promoter", "Factory at 40% capacity"},
			EvidenceSummary: "HARD OVERRIDE: Revenue-GST mismatch >25%. Score 31.2 below review threshold. Multiple critical flags including DSCR breach and litigation.",
			GeneratedAt:     now,
		},
		ScoreResult: &model.ScoreResult{
			OverallScore: 31.2,
			ScoreBreakdown: map[string]any{"financial_strength": 25, "cash_flow": 18, "governance": 30, "contradiction_severity": 15, "secondary_research": 40, "officer_note": 28},
			Decision: "reject", DecisionExplanation: "HARD OVERRIDE: Revenue-GST mismatch >25%. Score 31.2 below review threshold.",
			RecommendedLimit: 0, RecommendedROI: 0,
			Reasons:             []string{"Financial: Net loss", "Cash flow: DSCR 0.65x", "Contradictions: Revenue-GST mismatch 33.7%", "Governance: Auditor qualification", "Litigation: Ongoing case", "Officer: Factory at 40%"},
			HardOverrideApplied: true, HardOverrideReason: "Revenue-GST mismatch 33.7%>25%; DSCR below 1.0x.",
		},
		OfficerNoteSignals: &model.OfficerNoteSignals{
			CapacityUtilization: map[string]any{"score": 20, "explanations": []any{"Low capacity (~40%)"}},
			ManagementQuality:   map[string]any{"score": 46, "explanations": []any{"Evasive"}},
			OperationalHealth:   map[string]any{"score": 46, "explanations": []any{"Outdated equipment"}},
			CollectionRisk:      map[string]any{"score": 46, "explanations": []any{"Weak debtor collection"}},
			SiteVisitRisk:       map[string]any{"score": 44, "explanations": []any{"Stock mismatch", "Inventory concern"}},
			PromoterBehavior:    map[string]any{"score": 22, "explanations": []any{"Evasive", "Extravagant lifestyle", "Litigation"}},
			CompositeScore:      35.4,
			AllExplanations:     []string{"Low capacity 40%", "Evasive promoter", "Outdated equipment", "Weak collection", "Stock mismatch", "Extravagant lifestyle"},
		},
	}

	return []*model.CreditCase{healthy, risky}
}
