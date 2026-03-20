export type CreateCaseRequest = {
  company_name: string;
  sector: string;
  promoter_names: string[];
  officer_notes?: string;
};

export type UploadedFile = {
  file_name: string;
  file_path: string;
  doc_type?: string;
  uploaded_at?: string;
};

export type RiskFlag = {
  flag_id?: string;
  flag_type?: string;
  severity?: string;
  description?: string;
  evidence_refs?: string[];
  confidence?: number;
  impact_on_score?: string;
};

export type CAMResult = {
  case_id?: string;
  final_decision?: string;
  recommended_limit?: number;
  recommended_roi?: number;
  overall_score?: number;
  score_breakdown?: Record<string, number>;
  key_reasons?: string[];
  evidence_summary?: string;
  cam_doc_path?: string;
  generated_at?: string;
};

export type OfficerNoteSignalDetail = {
  score: number;
  explanations: string[];
};

export type OfficerNoteSignals = {
  capacity_utilization: OfficerNoteSignalDetail;
  management_quality: OfficerNoteSignalDetail;
  operational_health: OfficerNoteSignalDetail;
  collection_risk: OfficerNoteSignalDetail;
  site_visit_risk: OfficerNoteSignalDetail;
  promoter_behavior_score: OfficerNoteSignalDetail;
  composite_score: number;
  all_explanations: string[];
};

export type ScoreResult = {
  overall_score: number;
  score_breakdown: Record<string, number>;
  decision: string;
  decision_explanation: string;
  recommended_limit: number;
  recommended_roi: number;
  reasons: string[];
  hard_override_applied: boolean;
  hard_override_reason: string;
  officer_note_signals?: OfficerNoteSignals;
};

export type CreditCase = {
  case_id: string;
  company_name: string;
  cin_optional?: string;
  sector?: string;
  promoter_names?: string[];
  uploaded_files?: UploadedFile[];
  officer_notes?: string;
  created_at: string;
  status: string;
  extracted_facts?: Record<string, unknown>;
  risk_flags?: RiskFlag[];
  cam_result?: CAMResult;
  score_result?: ScoreResult;
  officer_note_signals?: OfficerNoteSignals;
};

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";

async function parseResponse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message = data?.error || `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return data as T;
}

export async function createCase(payload: CreateCaseRequest): Promise<CreditCase> {
  const res = await fetch(`${BASE_URL}/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseResponse<CreditCase>(res);
}

export async function getCases(): Promise<CreditCase[]> {
  const res = await fetch(`${BASE_URL}/cases`, { cache: "no-store" });
  return parseResponse<CreditCase[]>(res);
}

export async function getCase(caseId: string): Promise<CreditCase> {
  const res = await fetch(`${BASE_URL}/cases/${caseId}`, { cache: "no-store" });
  return parseResponse<CreditCase>(res);
}

export async function uploadCaseFiles(caseId: string, files: File[]): Promise<{ files: UploadedFile[] }> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const res = await fetch(`${BASE_URL}/cases/${caseId}/upload`, {
    method: "POST",
    body: formData
  });
  return parseResponse<{ files: UploadedFile[] }>(res);
}

export async function updateOfficerNotes(caseId: string, officerNotes: string): Promise<CreditCase> {
  const res = await fetch(`${BASE_URL}/cases/${caseId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ officer_notes: officerNotes })
  });
  return parseResponse<CreditCase>(res);
}

export async function analyzeCase(caseId: string): Promise<CreditCase> {
  const res = await fetch(`${BASE_URL}/cases/${caseId}/analyze`, { method: "POST" });
  return parseResponse<CreditCase>(res);
}

export async function getCAM(caseId: string): Promise<CAMResult> {
  const res = await fetch(`${BASE_URL}/cases/${caseId}/cam`, { cache: "no-store" });
  return parseResponse<CAMResult>(res);
}
