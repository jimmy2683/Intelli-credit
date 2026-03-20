package store_test

import (
	"os"
	"path/filepath"
	"testing"

	"credit-intel/backend-go/internal/model"
	"credit-intel/backend-go/internal/store"
)

func setupTestDB(t *testing.T) *store.DB {
	t.Helper()
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "test.db")
	db, err := store.Open(dbPath)
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestInsertAndGetCase(t *testing.T) {
	db := setupTestDB(t)

	c := &model.CreditCase{
		CaseID:        "test_001",
		CompanyName:   "Test Corp",
		Sector:        "IT",
		PromoterNames: []string{"Alice", "Bob"},
		Status:        "created",
		CreatedAt:     "2025-01-01T00:00:00Z",
	}

	if err := db.InsertCase(c); err != nil {
		t.Fatalf("InsertCase failed: %v", err)
	}

	got, err := db.GetCase("test_001")
	if err != nil {
		t.Fatalf("GetCase failed: %v", err)
	}
	if got == nil {
		t.Fatal("GetCase returned nil")
	}
	if got.CompanyName != "Test Corp" {
		t.Errorf("CompanyName = %q, want %q", got.CompanyName, "Test Corp")
	}
	if got.Sector != "IT" {
		t.Errorf("Sector = %q, want %q", got.Sector, "IT")
	}
	if len(got.PromoterNames) != 2 {
		t.Errorf("PromoterNames len = %d, want 2", len(got.PromoterNames))
	}
}

func TestGetCaseNotFound(t *testing.T) {
	db := setupTestDB(t)
	got, err := db.GetCase("nonexistent")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != nil {
		t.Errorf("expected nil, got %+v", got)
	}
}

func TestUpdateCase(t *testing.T) {
	db := setupTestDB(t)

	c := &model.CreditCase{
		CaseID:      "test_002",
		CompanyName: "Original",
		Status:      "created",
		CreatedAt:   "2025-01-01T00:00:00Z",
	}
	db.InsertCase(c)

	c.CompanyName = "Updated Name"
	c.Status = "ready"
	c.OfficerNotes = "Site visit complete"

	if err := db.UpdateCase(c); err != nil {
		t.Fatalf("UpdateCase failed: %v", err)
	}

	got, _ := db.GetCase("test_002")
	if got.CompanyName != "Updated Name" {
		t.Errorf("CompanyName = %q, want %q", got.CompanyName, "Updated Name")
	}
	if got.Status != "ready" {
		t.Errorf("Status = %q, want %q", got.Status, "ready")
	}
	if got.OfficerNotes != "Site visit complete" {
		t.Errorf("OfficerNotes = %q, want %q", got.OfficerNotes, "Site visit complete")
	}
}

func TestCaseWithComplexFields(t *testing.T) {
	db := setupTestDB(t)

	c := &model.CreditCase{
		CaseID:      "test_003",
		CompanyName: "Complex Corp",
		Status:      "ready",
		CreatedAt:   "2025-01-01T00:00:00Z",
		UploadedFiles: []model.UploadedFile{
			{FileName: "report.pdf", FilePath: "/uploads/report.pdf", DocType: "Annual Report"},
		},
		ExtractedFacts: map[string]any{
			"revenue": 100000000, "PAT": 5000000,
		},
		RiskFlags: []model.RiskFlag{
			{FlagID: "rf_1", FlagType: "liquidity", Severity: "high", Description: "CR<1", Confidence: 0.9},
		},
		CAMResult: &model.CAMResult{
			CaseID:        "test_003",
			FinalDecision: "approve",
			OverallScore:  78.4,
			KeyReasons:    []string{"Strong revenue"},
		},
		ScoreResult: &model.ScoreResult{
			OverallScore:   78.4,
			Decision:       "approve",
			ScoreBreakdown: map[string]any{"financial_strength": 80},
			Reasons:        []string{"Healthy"},
		},
	}

	db.InsertCase(c)
	got, _ := db.GetCase("test_003")

	if len(got.UploadedFiles) != 1 {
		t.Errorf("UploadedFiles len = %d, want 1", len(got.UploadedFiles))
	}
	if got.UploadedFiles[0].FileName != "report.pdf" {
		t.Errorf("UploadedFile name = %q", got.UploadedFiles[0].FileName)
	}
	if len(got.RiskFlags) != 1 {
		t.Errorf("RiskFlags len = %d, want 1", len(got.RiskFlags))
	}
	if got.CAMResult == nil {
		t.Fatal("CAMResult is nil")
	}
	if got.CAMResult.FinalDecision != "approve" {
		t.Errorf("CAMResult.FinalDecision = %q", got.CAMResult.FinalDecision)
	}
	if got.ScoreResult == nil {
		t.Fatal("ScoreResult is nil")
	}
	if got.ScoreResult.OverallScore != 78.4 {
		t.Errorf("ScoreResult.OverallScore = %f", got.ScoreResult.OverallScore)
	}
}

func TestListCaseIDs(t *testing.T) {
	db := setupTestDB(t)

	for _, id := range []string{"case_a", "case_b", "case_c"} {
		db.InsertCase(&model.CreditCase{CaseID: id, CompanyName: id, Status: "created", CreatedAt: "2025-01-01"})
	}

	ids, err := db.ListCaseIDs()
	if err != nil {
		t.Fatalf("ListCaseIDs failed: %v", err)
	}
	if len(ids) != 3 {
		t.Errorf("ListCaseIDs returned %d, want 3", len(ids))
	}
}

func TestCaseExists(t *testing.T) {
	db := setupTestDB(t)
	db.InsertCase(&model.CreditCase{CaseID: "exists_1", CompanyName: "X", Status: "created", CreatedAt: "2025-01-01"})

	exists, _ := db.CaseExists("exists_1")
	if !exists {
		t.Error("CaseExists returned false for existing case")
	}

	exists, _ = db.CaseExists("nope")
	if exists {
		t.Error("CaseExists returned true for non-existing case")
	}
}

func TestSeedSampleData(t *testing.T) {
	db := setupTestDB(t)

	db.SeedSampleData()

	exists1, _ := db.CaseExists("demo_healthy_001")
	exists2, _ := db.CaseExists("demo_risky_002")

	if !exists1 {
		t.Error("demo_healthy_001 not seeded")
	}
	if !exists2 {
		t.Error("demo_risky_002 not seeded")
	}

	// Seed again — should not error (idempotent)
	db.SeedSampleData()
}

func TestPersistenceAcrossReopen(t *testing.T) {
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "persist.db")

	// Open, insert, close
	db1, _ := store.Open(dbPath)
	db1.InsertCase(&model.CreditCase{CaseID: "persist_1", CompanyName: "Persist", Status: "ready", CreatedAt: "2025-01-01"})
	db1.Close()

	// Reopen and verify
	db2, _ := store.Open(dbPath)
	defer db2.Close()

	got, _ := db2.GetCase("persist_1")
	if got == nil {
		t.Fatal("Case not found after reopen")
	}
	if got.CompanyName != "Persist" {
		t.Errorf("CompanyName = %q after reopen", got.CompanyName)
	}
}

func TestDBPathCreation(t *testing.T) {
	dir := t.TempDir()
	nested := filepath.Join(dir, "a", "b", "c")
	dbPath := filepath.Join(nested, "test.db")

	db, err := store.Open(dbPath)
	if err != nil {
		t.Fatalf("Open failed with nested path: %v", err)
	}
	db.Close()

	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		t.Error("DB file not created at nested path")
	}
}
