# Credit Intel: Technical Flow & Architecture

This document describes the end-to-end data flow of the **Credit Intel** platform, from document upload to the generation of the Credit Appraisal Memo (CAM).

## 🏗️ System Architecture Overview

The system consists of three main components sharing a unified data volume:
1.  **Frontend (Next.js/React)**: User dashboard for case management and document uploads.
2.  **Backend (Go)**: Orchestrates storage, case persistence (SQLite), and communication with the AI engine.
3.  **AI Engine (Python/FastAPI)**: Heavy-lifting pipeline for OCR, LLM-based extraction, and scoring.

## 🔄 End-to-End Flow (Mermaid)

```mermaid
sequenceDiagram
    participant U as User (Frontend)
    participant B as Go Backend
    participant S as Shared Data Root
    participant AE as AI Engine (Python)
    participant M as Mistral AI (Large)

    U->>B: 1. Upload PDF/DOCX (Case Creation)
    B->>S: 2. Save file to data/uploads/{case_id}/
    B->>U: 3. Return Case ID
    U->>B: 4. Trigger Analysis ("Run" button)
    B->>AE: 5. POST /extract (Case Metadata)
    
    rect rgb(240, 240, 240)
        Note right of AE: AI Processing Pipeline
        AE->>S: 6. Load files from data/uploads/
        AE->>AE: 7. Parse (PDFPlumber/OCR) -> All Text Chunks
        AE->>AE: 8. Smart Selection (Financial Keywords)
        AE->>M: 9. Call Mistral (Structured Extraction)
        M-->>AE: 10. Return JSON: Facts, Risks, Entities
        AE->>AE: 11. Run Scoring Engine (Multi-factor)
        AE->>AE: 12. Generate Word CAM (python-docx)
        AE->>S: 13. Save CAM to data/evidence/{case_id}/
    end

    AE-->>B: 14. Return Structured Analysis
    B->>B: 15. Persist to SQLite
    B->>U: 16. Push Live Updates (Dashboard)
    U->>B: 17. Download CAM.docx
```

## 🛠️ Detailed Component Breakdown

### 1. Document Parsing & OCR
- **PDFPlumber**: Direct text extraction for digital PDFs.
- **Tesseract OCR**: Fallback for scanned documents or images.
- **Chunking**: Text is split into logical segments with metadata (page number, chunk ID) to maintain source traceability.

### 2. Mistral AI Extraction Layer
- **Smart Chunk Selection**: To handle 100+ page annual reports, the system scans all chunks for financial keywords (Balance Sheet, P&L, Audit) and prioritizes the most relevant context for the LLM.
- **Structured Prompts**: We use Mistral's JSON mode to extract key financial metrics (EBITDA, PAT, Revenue) and identify qualitative risks (Auditor remarks, Related Party Transactions).
- **Normalizer**: Converts extracted strings into normalized numbers while preserving high-confidence source references.

### 3. Credit Scoring Engine
Combines multiple signals into a weighted final score:
- **Financial Strength**: Based on PAT, Revenue, and Debt levels.
- **Governance**: Derived from auditor remarks and promoter behavior.
- **Contradiction Detection**: Flags mismatches between GST filings and bank statements.
- **Officer Notes**: Qualitative insights from field visits integrated via Sentiment Analysis.

### 4. Shared Data Strategy
- **`DATA_ROOT`**: Both Go and Python services point to a project-level `data/` folder.
- **Zero-Latency Handover**: The Go backend writes the file once; the Python engine reads it directly from the same path, avoiding expensive base64 transfers or repeated network hops.
