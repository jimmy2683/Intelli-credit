import type { CreditCase, CAMResult } from "./api";

export type SampleCase = CreditCase & {
  cam_result: CAMResult;
  score_result: {
    overall_score: number;
    score_breakdown: Record<string, number>;
    decision: string;
    decision_explanation: string;
    recommended_limit: number;
    recommended_roi: number;
    reasons: string[];
    hard_override_applied: boolean;
    hard_override_reason: string;
    officer_note_signals: {
      capacity_utilization: { score: number; explanations: string[] };
      management_quality: { score: number; explanations: string[] };
      operational_health: { score: number; explanations: string[] };
      collection_risk: { score: number; explanations: string[] };
      site_visit_risk: { score: number; explanations: string[] };
      promoter_behavior_score: { score: number; explanations: string[] };
      composite_score: number;
      all_explanations: string[];
    };
  };
};

// ── Case 1: Healthy Borrower ──
const healthyCase: SampleCase = {
  case_id: "demo_healthy_001",
  company_name: "Pranav Textiles Pvt Ltd",
  cin_optional: "U17120MH2015PTC123456",
  sector: "Textiles & Apparel",
  promoter_names: ["Rajesh Mehta", "Sunita Mehta"],
  officer_notes:
    "Factory operating at 85% capacity. Plant expansion visible — new weaving unit being set up. " +
    "Management was cooperative and transparent during site visit. Inventory tallied with books. " +
    "Debtor collection appears healthy with low aging. Promoter track record is strong with 15+ years " +
    "in the textile industry. Clean premises, modern machinery, well-maintained.",
  created_at: "2026-03-18T10:30:00Z",
  status: "ready",
  uploaded_files: [
    { file_name: "AnnualReport_FY2025.pdf", file_path: "/data/uploads/demo_healthy_001/AnnualReport_FY2025.pdf", doc_type: "Annual Report", uploaded_at: "2026-03-18T10:32:00Z" },
    { file_name: "BankStatement_Q4FY25.pdf", file_path: "/data/uploads/demo_healthy_001/BankStatement_Q4FY25.pdf", doc_type: "Bank Statement", uploaded_at: "2026-03-18T10:33:00Z" },
    { file_name: "GST_Returns_FY25.pdf", file_path: "/data/uploads/demo_healthy_001/GST_Returns_FY25.pdf", doc_type: "GST Returns", uploaded_at: "2026-03-18T10:34:00Z" },
    { file_name: "AuditReport_FY2025.pdf", file_path: "/data/uploads/demo_healthy_001/AuditReport_FY2025.pdf", doc_type: "Audit Report", uploaded_at: "2026-03-18T10:35:00Z" },
  ],
  extracted_facts: {
    revenue: { value: 42_00_00_000, source_ref: "AnnualReport_FY2025.pdf", page_ref: "P&L Statement, Page 12", confidence: 0.95, snippet: "Total revenue from operations stood at ₹42.00 Crore for the financial year ending March 2025." },
    EBITDA: { value: 7_56_00_000, source_ref: "AnnualReport_FY2025.pdf", page_ref: "P&L Statement, Page 12", confidence: 0.92, snippet: "EBITDA of ₹7.56 Crore represents an 18% margin improvement over the previous fiscal." },
    PAT: { value: 3_78_00_000, source_ref: "AnnualReport_FY2025.pdf", page_ref: "P&L Statement, Page 13", confidence: 0.93, snippet: "Profit After Tax was ₹3.78 Crore, aided by operational efficiency and lower raw material costs." },
    total_debt: { value: 12_60_00_000, source_ref: "AuditReport_FY2025.pdf", page_ref: "Balance Sheet, Page 8", confidence: 0.91, snippet: "Total borrowings including term loans and working capital facilities aggregated to ₹12.60 Crore." },
    current_ratio: { value: 1.65, source_ref: "AuditReport_FY2025.pdf", page_ref: "Schedule of Assets, Page 9", confidence: 0.88, snippet: "Current assets of ₹18.50 Cr against current liabilities of ₹11.21 Cr, yielding a current ratio of 1.65." },
    dscr: { value: 1.45, source_ref: "AnnualReport_FY2025.pdf", page_ref: "Notes to Accounts, Page 22", confidence: 0.85, snippet: "Debt Service Coverage Ratio computed at 1.45x indicates adequate servicing capacity." },
    working_capital: { value: 7_29_00_000, source_ref: "BankStatement_Q4FY25.pdf", page_ref: "Summary Page 1", confidence: 0.82, snippet: "Net working capital position of ₹7.29 Crore as per bank statement analysis." },
    gst_turnover: { value: 40_50_00_000, source_ref: "GST_Returns_FY25.pdf", page_ref: "GSTR-3B Summary", confidence: 0.90, snippet: "GST turnover of ₹40.50 Crore, closely aligned with reported revenue, indicating minimal variance." },
    bank_credit_turnover: { value: 39_80_00_000, source_ref: "BankStatement_Q4FY25.pdf", page_ref: "Credit Turnover Summary", confidence: 0.87, snippet: "Annual credit turnover of ₹39.80 Crore through the primary banking channel." },
  },
  risk_flags: [
    {
      flag_id: "rf_h_01", flag_type: "revenue_gst_variance", severity: "low",
      description: "Minor variance of 3.6% between reported revenue (₹42 Cr) and GST turnover (₹40.5 Cr). Within acceptable threshold.",
      evidence_refs: ["AnnualReport_FY2025.pdf:P12", "GST_Returns_FY25.pdf:Summary"],
      confidence: 0.72, impact_on_score: "Minimal — variance within normal operating range."
    },
    {
      flag_id: "rf_h_02", flag_type: "sector_outlook", severity: "low",
      description: "Textile sector facing moderate headwinds from imported competition, but domestic demand remains stable.",
      evidence_refs: ["Secondary Research: Industry Reports"],
      confidence: 0.65, impact_on_score: "Low — company shows resilience through product diversification."
    },
    {
      flag_id: "rf_h_03", flag_type: "concentration_risk", severity: "medium",
      description: "Top 3 customers account for 45% of revenue. Loss of a major client could impact cash flows.",
      evidence_refs: ["AnnualReport_FY2025.pdf:P18", "Notes to Accounts"],
      confidence: 0.78, impact_on_score: "Moderate — revenue concentration requires monitoring."
    },
  ],
  cam_result: {
    case_id: "demo_healthy_001",
    final_decision: "approve",
    recommended_limit: 6_30_00_000,
    recommended_roi: 12.5,
    overall_score: 78.4,
    score_breakdown: { financial_strength: 82, cash_flow: 80, governance: 72, contradiction_severity: 88, secondary_research: 75, officer_note: 84 },
    key_reasons: [
      "Financial: Strong revenue growth with healthy 18% EBITDA margin",
      "Cash flow: DSCR of 1.45x indicates adequate debt servicing capacity",
      "Governance: Clean audit report with no material qualifications",
      "Officer: Plant expansion visible; management cooperative and transparent",
      "Research: Stable domestic demand despite sector headwinds",
    ],
    evidence_summary: "Overall score 78.4 meets approve threshold (≥70). Borrower demonstrates solid financial health with consistent revenue growth and strong cash flows. Minor revenue-GST variance and customer concentration are noted but manageable.",
    cam_doc_path: "/data/evidence/demo_healthy_001/cam.docx",
    generated_at: "2026-03-18T10:40:00Z",
  },
  score_result: {
    overall_score: 78.4,
    score_breakdown: { financial_strength: 82, cash_flow: 80, governance: 72, contradiction_severity: 88, secondary_research: 75, officer_note: 84 },
    decision: "approve",
    decision_explanation: "Overall score 78.4 meets approve threshold (≥70). Borrower demonstrates solid financial health.",
    recommended_limit: 6_30_00_000,
    recommended_roi: 12.5,
    reasons: [
      "Financial: Strong revenue growth with healthy 18% EBITDA margin",
      "Cash flow: DSCR of 1.45x indicates adequate debt servicing capacity",
      "Governance: Clean audit report with no material qualifications",
      "Officer: Plant expansion visible; management cooperative and transparent",
      "Research: Stable domestic demand despite sector headwinds",
    ],
    hard_override_applied: false,
    hard_override_reason: "",
    officer_note_signals: {
      capacity_utilization: { score: 85, explanations: ["Running at 85% capacity", "Positive signal: 'plant expansion'"] },
      management_quality: { score: 88, explanations: ["Positive signal: 'cooperative'", "Positive signal: 'transparent'"] },
      operational_health: { score: 86, explanations: ["Positive signal: 'modern machinery'", "Positive signal: 'well-maintained'"] },
      collection_risk: { score: 80, explanations: ["Positive signal: 'healthy receivable'"] },
      site_visit_risk: { score: 85, explanations: ["Positive signal: 'inventory tallied'"] },
      promoter_behavior_score: { score: 82, explanations: ["Positive signal: 'strong promoter'"] },
      composite_score: 84.3,
      all_explanations: ["Running at 85% capacity", "Management cooperative and transparent", "Modern machinery, well-maintained", "Healthy receivables", "Inventory verified", "Strong promoter track record"],
    },
  },
};

// ── Case 2: Risky Borrower ──
const riskyCase: SampleCase = {
  case_id: "demo_risky_002",
  company_name: "Apex Steel & Alloys Ltd",
  cin_optional: "L27100DL2008PLC198765",
  sector: "Steel & Metals",
  promoter_names: ["Vikram Choudhary", "Deepak Choudhary"],
  officer_notes:
    "Factory operating at 40% capacity. Plant appears aged with outdated equipment. " +
    "Promoter response was evasive when asked about related-party transactions. " +
    "Debtor collection looks weak with significant aging beyond 180 days. " +
    "Stock mismatch observed between physical inventory and book records — inventory concern. " +
    "Promoter lifestyle appears extravagant relative to company earnings. " +
    "There is an ongoing litigation case against the promoter in the Delhi High Court.",
  created_at: "2026-03-19T09:15:00Z",
  status: "ready",
  uploaded_files: [
    { file_name: "AnnualReport_FY2025.pdf", file_path: "/data/uploads/demo_risky_002/AnnualReport_FY2025.pdf", doc_type: "Annual Report", uploaded_at: "2026-03-19T09:18:00Z" },
    { file_name: "BankStatement_FY25.pdf", file_path: "/data/uploads/demo_risky_002/BankStatement_FY25.pdf", doc_type: "Bank Statement", uploaded_at: "2026-03-19T09:19:00Z" },
    { file_name: "GST_GSTR3B_FY25.pdf", file_path: "/data/uploads/demo_risky_002/GST_GSTR3B_FY25.pdf", doc_type: "GST Returns", uploaded_at: "2026-03-19T09:20:00Z" },
    { file_name: "AuditReport_FY2025.pdf", file_path: "/data/uploads/demo_risky_002/AuditReport_FY2025.pdf", doc_type: "Audit Report", uploaded_at: "2026-03-19T09:21:00Z" },
    { file_name: "LegalNotice_Litigation.pdf", file_path: "/data/uploads/demo_risky_002/LegalNotice_Litigation.pdf", doc_type: "Legal Document", uploaded_at: "2026-03-19T09:22:00Z" },
  ],
  extracted_facts: {
    revenue: { value: 28_50_00_000, source_ref: "AnnualReport_FY2025.pdf", page_ref: "P&L Statement, Page 10", confidence: 0.89, snippet: "Revenue from operations declined to ₹28.50 Crore from ₹35.20 Crore in the prior year, a 19% decline." },
    EBITDA: { value: 2_28_00_000, source_ref: "AnnualReport_FY2025.pdf", page_ref: "P&L Statement, Page 10", confidence: 0.86, snippet: "EBITDA of ₹2.28 Crore reflects an 8% margin, significantly compressed versus the sector average of 14%." },
    PAT: { value: -85_00_000, source_ref: "AnnualReport_FY2025.pdf", page_ref: "P&L Statement, Page 11", confidence: 0.91, snippet: "Net loss of ₹0.85 Crore reported due to higher interest costs and one-time write-downs." },
    total_debt: { value: 22_40_00_000, source_ref: "AuditReport_FY2025.pdf", page_ref: "Balance Sheet, Page 7", confidence: 0.93, snippet: "Total outstanding borrowings of ₹22.40 Crore, including ₹8.50 Crore in term loans and ₹13.90 Crore in working capital." },
    current_ratio: { value: 0.82, source_ref: "AuditReport_FY2025.pdf", page_ref: "Schedule of Assets, Page 8", confidence: 0.90, snippet: "Current ratio of 0.82 indicates inability to meet short-term obligations from current assets alone." },
    dscr: { value: 0.65, source_ref: "AnnualReport_FY2025.pdf", page_ref: "Notes to Accounts, Page 20", confidence: 0.87, snippet: "DSCR of 0.65x is well below the covenant threshold of 1.25x, signaling distress." },
    working_capital: { value: -3_20_00_000, source_ref: "BankStatement_FY25.pdf", page_ref: "Summary Page 1", confidence: 0.84, snippet: "Negative working capital of ₹-3.20 Crore with frequent overdraws on sanctioned limits." },
    gst_turnover: { value: 18_90_00_000, source_ref: "GST_GSTR3B_FY25.pdf", page_ref: "GSTR-3B Annual Summary", confidence: 0.92, snippet: "GST filed turnover of ₹18.90 Crore — a 33.7% variance from reported revenue of ₹28.50 Crore." },
    bank_credit_turnover: { value: 15_20_00_000, source_ref: "BankStatement_FY25.pdf", page_ref: "Credit Turnover Summary", confidence: 0.88, snippet: "Bank credit turnover of only ₹15.20 Crore, significantly lower than reported revenue, raising diversion concerns." },
    auditor_remarks: { value: "Qualified opinion due to inability to confirm related-party balances and inventory valuation adjustments.", source_ref: "AuditReport_FY2025.pdf", page_ref: "Auditor's Report, Page 2", confidence: 0.95, snippet: "In our opinion, except for the effects of the matter described in the Basis for Qualified Opinion section, the financial statements give a true and fair view..." },
  },
  risk_flags: [
    {
      flag_id: "rf_r_01", flag_type: "revenue_gst_mismatch", severity: "critical",
      description: "Revenue-GST mismatch of 33.7% (₹28.5 Cr reported vs ₹18.9 Cr GST filed). Indicates potential revenue inflation or diversion of sales off-books.",
      evidence_refs: ["AnnualReport_FY2025.pdf:P10", "GST_GSTR3B_FY25.pdf:Summary"],
      confidence: 0.92, impact_on_score: "Severe — triggers hard override. This level of variance is a major red flag for revenue manipulation."
    },
    {
      flag_id: "rf_r_02", flag_type: "bank_revenue_divergence", severity: "high",
      description: "Bank credit turnover (₹15.2 Cr) is only 53% of reported revenue (₹28.5 Cr). Cash flows do not support reported sales figures.",
      evidence_refs: ["BankStatement_FY25.pdf:CreditSummary", "AnnualReport_FY2025.pdf:P10"],
      confidence: 0.88, impact_on_score: "High — corroborates GST mismatch. Strong indicator of fund diversion."
    },
    {
      flag_id: "rf_r_03", flag_type: "auditor_qualification", severity: "high",
      description: "Auditor issued a qualified opinion citing inability to confirm related-party balances and inventory valuation concerns.",
      evidence_refs: ["AuditReport_FY2025.pdf:P2"],
      confidence: 0.95, impact_on_score: "High — governance concern. Auditor qualification undermines financial statement reliability."
    },
    {
      flag_id: "rf_r_04", flag_type: "liquidity_stress", severity: "high",
      description: "Current ratio of 0.82 and negative working capital of ₹-3.2 Cr indicate severe liquidity pressure.",
      evidence_refs: ["AuditReport_FY2025.pdf:P8", "BankStatement_FY25.pdf:P1"],
      confidence: 0.90, impact_on_score: "High — inability to meet short-term obligations without additional funding."
    },
    {
      flag_id: "rf_r_05", flag_type: "dscr_breach", severity: "critical",
      description: "DSCR of 0.65x is below the 1.0x threshold. Company cannot service its existing debt from operating cash flows.",
      evidence_refs: ["AnnualReport_FY2025.pdf:P20"],
      confidence: 0.87, impact_on_score: "Severe — triggers hard override. DSCR below 1.0x indicates default risk."
    },
    {
      flag_id: "rf_r_06", flag_type: "litigation_risk", severity: "high",
      description: "Ongoing litigation against promoter Vikram Choudhary in Delhi High Court. Nature of dispute involves alleged fund diversion from a previous venture.",
      evidence_refs: ["LegalNotice_Litigation.pdf:P1-3", "Secondary Research: Court Records"],
      confidence: 0.82, impact_on_score: "High — promoter credibility and fund diversion history are material concerns."
    },
    {
      flag_id: "rf_r_07", flag_type: "inventory_mismatch", severity: "medium",
      description: "Physical inventory verification during site visit showed discrepancies with book records. Possible inflation of inventory values.",
      evidence_refs: ["Officer Site Visit Notes"],
      confidence: 0.74, impact_on_score: "Medium — corroborates auditor's inventory valuation concern."
    },
    {
      flag_id: "rf_r_08", flag_type: "promoter_lifestyle", severity: "medium",
      description: "Officer notes indicate promoter lifestyle appears extravagant relative to declared income and company earnings.",
      evidence_refs: ["Officer Notes"],
      confidence: 0.68, impact_on_score: "Medium — raises questions about undisclosed income sources."
    },
  ],
  cam_result: {
    case_id: "demo_risky_002",
    final_decision: "decline",
    recommended_limit: 0,
    recommended_roi: 0,
    overall_score: 31.2,
    score_breakdown: { financial_strength: 25, cash_flow: 18, governance: 30, contradiction_severity: 15, secondary_research: 40, officer_note: 28 },
    key_reasons: [
      "Financial: Net loss reported; EBITDA margin (8%) well below sector average (14%)",
      "Cash flow: DSCR of 0.65x below 1.0x — cannot service existing debt",
      "Contradictions: Revenue-GST mismatch of 33.7% — potential revenue manipulation",
      "Contradictions: Bank credit turnover only 53% of reported revenue",
      "Governance: Auditor qualification on related-party and inventory",
      "Litigation: Ongoing case against promoter for alleged fund diversion",
      "Officer: Low capacity (40%), evasive promoter, inventory mismatch on site",
    ],
    evidence_summary: "HARD OVERRIDE APPLIED: Revenue-GST mismatch exceeds 25% threshold. Overall score 31.2 falls well below review threshold (<50). Multiple critical and high severity flags including DSCR breach, liquidity stress, auditor qualification, and litigation against promoter. Recommendation: Decline.",
    cam_doc_path: "/data/evidence/demo_risky_002/cam.docx",
    generated_at: "2026-03-19T09:35:00Z",
  },
  score_result: {
    overall_score: 31.2,
    score_breakdown: { financial_strength: 25, cash_flow: 18, governance: 30, contradiction_severity: 15, secondary_research: 40, officer_note: 28 },
    decision: "reject",
    decision_explanation: "HARD OVERRIDE: Revenue-GST mismatch exceeds 25% threshold. Overall score 31.2 below review threshold (<50).",
    recommended_limit: 0,
    recommended_roi: 0,
    reasons: [
      "Financial: Net loss reported; EBITDA margin (8%) well below sector average",
      "Cash flow: DSCR of 0.65x signals inability to service debt",
      "Contradictions: Revenue-GST mismatch of 33.7%",
      "Contradictions: Bank turnover vs reported revenue divergence",
      "Governance: Auditor qualified opinion on related-party & inventory",
      "Litigation: Ongoing case against promoter for fund diversion",
      "Officer: Factory at 40% capacity; promoter evasive",
    ],
    hard_override_applied: true,
    hard_override_reason: "Revenue-GST mismatch of 33.7% exceeds 25% threshold; DSCR below 1.0x.",
    officer_note_signals: {
      capacity_utilization: { score: 20, explanations: ["Low capacity utilization (~40%)"] },
      management_quality: { score: 46, explanations: ["Negative signal: 'evasive'"] },
      operational_health: { score: 46, explanations: ["Negative signal: 'outdated equipment'"] },
      collection_risk: { score: 46, explanations: ["Negative signal: 'debtor collection looks weak'"] },
      site_visit_risk: { score: 44, explanations: ["Negative signal: 'stock mismatch'", "Negative signal: 'inventory concern'"] },
      promoter_behavior_score: { score: 22, explanations: ["Negative signal: 'promoter response was evasive'", "Negative signal: 'promoter lifestyle extravagant'", "Negative signal: 'litigation case'"] },
      composite_score: 35.4,
      all_explanations: ["Low capacity (40%)", "Promoter evasive", "Outdated equipment", "Weak debtor collection", "Stock mismatch on site", "Promoter lifestyle extravagant", "Litigation against promoter"],
    },
  },
};

export const SAMPLE_CASES: SampleCase[] = [healthyCase, riskyCase];

export function getSampleCase(id: string): SampleCase | undefined {
  return SAMPLE_CASES.find((c) => c.case_id === id);
}
