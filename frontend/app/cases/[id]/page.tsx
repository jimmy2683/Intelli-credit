"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  BarChart3,
  FileText,
  Hash,
  ShieldAlert,
  ChevronRight,
  ArrowLeft,
  ArrowRight,
  Download,
  File,
  Loader2,
  X
} from "lucide-react";

import EvidenceDrawer, { type EvidenceItem } from "@/components/EvidenceDrawer";
import FileUpload from "@/components/FileUpload";
import OfficerNotes from "@/components/OfficerNotes";
import SchemaBuilder from "@/components/SchemaBuilder";
import AnimateIn from "@/components/AnimateIn";
import {
  analyzeCase, getCAM, getCase, updateSchema,
  type CAMResult, type CreditCase, type RiskFlag,
  updateOfficerNotes, uploadCaseFiles,
} from "@/lib/api";
import { getSampleCase, type SampleCase } from "@/lib/sampleData";

/* ─── helpers ─── */
function fmtInr(v: number | undefined | null) {
  if (v == null) return "N/A";
  if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return `₹${v.toLocaleString("en-IN")}`;
}

/**
 * Keys that represent monetary amounts (revenues, debts, profits, etc.)
 * Everything else with a numeric value should NOT get the ₹ symbol.
 */
const MONETARY_KEYS = new Set([
  "revenue", "ebitda", "pat", "total_debt", "net_profit",
  "gross_profit", "working_capital", "capex", "cash_and_equivalents",
  "total_assets", "total_liabilities", "net_worth", "borrowings",
  "sales", "turnover", "income", "expenses", "depreciation", "interest_expense",
]);

/**
 * Keys that are dimensionless ratios / scores (display as plain decimal).
 */
const RATIO_KEYS = new Set([
  "current_ratio", "dscr", "debt_to_equity", "interest_coverage",
  "quick_ratio", "asset_turnover", "gross_margin", "net_margin",
  "roe", "roa", "roce",
]);

/** Format a fact value correctly based on what type of metric it is. */
function formatFactValue(key: string, val: unknown): string {
  if (val == null) return "N/A";

  if (Array.isArray(val)) {
    return val.length > 0 ? val.join("; ") : "N/A";
  }

  if (typeof val === "string") return val.trim() || "N/A";

  if (typeof val === "number") {
    const k = key.toLowerCase();
    if (RATIO_KEYS.has(k)) return val.toFixed(2);
    if (MONETARY_KEYS.has(k)) return fmtInr(val);
    // Fallback: if the number looks like a large integer it might be monetary
    if (Number.isInteger(val) && Math.abs(val) >= 10000) return fmtInr(val);
    // Small numbers (like 1.85 for ratios not in our set, or percentages)
    return val % 1 === 0 ? String(val) : val.toFixed(2);
  }

  return String(val);
}

/**
 * Given a flat extracted_facts object and a base key (e.g. "revenue"),
 * return the associated confidence and source_ref from the sibling keys.
 */
function getFlatMeta(facts: Record<string, unknown>, key: string): {
  confidence: number | undefined;
  source_ref: string | undefined;
} {
  const rawConf = facts[`${key}_confidence`];
  const rawSrc = facts[`${key}_source_ref`];
  return {
    confidence: typeof rawConf === "number" ? rawConf : undefined,
    source_ref: typeof rawSrc === "string" && rawSrc.trim() ? rawSrc.trim() : undefined,
  };
}

/** Legacy helper kept for risk-flag evidence that still uses the nested shape. */
function factMeta(f: unknown) {
  if (f && typeof f === "object" && "source_ref" in f)
    return f as { source_ref?: string; page_ref?: string; snippet?: string; confidence?: number };
  return {} as { source_ref?: string; page_ref?: string; snippet?: string; confidence?: number };
}

function scoreColor(v: number) {
  if (v >= 70) return "var(--success)";
  if (v >= 50) return "var(--warning)";
  return "var(--danger)";
}
function dClass(d: string) {
  const l = d.toLowerCase().replace(/_/g, "");
  if (l.includes("approve")) return "approve";
  if (l.includes("review") || l.includes("manual")) return "review";
  return "decline";
}
function dIcon(d: string) {
  const l = d.toLowerCase();
  if (l.includes("approve")) return <CheckCircle2 size={24} />;
  if (l.includes("review") || l.includes("manual")) return <AlertTriangle size={24} />;
  return <XCircle size={24} />;
}
function dLabel(d: string) {
  const l = d.toLowerCase();
  if (l.includes("approve") && !l.includes("condition")) return "Approved";
  if (l.includes("approve")) return "Approved w/ Conditions";
  if (l.includes("review") || l.includes("manual")) return "Manual Review";
  return "Declined";
}

/* ─── Score gauge with animated fill ─── */
function ScoreGauge({ score }: { score: number | undefined }) {
  const [animated, setAnimated] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setAnimated(true); obs.disconnect(); } },
      { threshold: 0.3 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  const s = score ?? 0;
  const r = 54, circ = 2 * Math.PI * r;
  const color = scoreColor(s);
  const offset = animated ? circ * (1 - Math.min(s / 100, 1)) : circ;

  return (
    <div ref={ref} style={{ textAlign: "center", position: "relative", display: "inline-block" }}>
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={r} fill="none" stroke="var(--line-subtle)" strokeWidth="9" />
        <circle cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="9"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 70 70)"
          style={{ filter: `drop-shadow(0 0 10px ${color}70)`, transition: "stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1) 0.2s" }}
        />
        <text x="70" y="64" textAnchor="middle" dominantBaseline="central"
          style={{ fontFamily: "var(--font-mono)", fontSize: 30, fontWeight: 700, fill: color }}>
          {score != null ? s.toFixed(0) : "—"}
        </text>
        <text x="70" y="84" textAnchor="middle"
          style={{ fontSize: 10, fill: "var(--text-3)", fontWeight: 700, letterSpacing: "0.07em" }}>
          OUT OF 100
        </text>
      </svg>
    </div>
  );
}

/* ─── Sidebar KPI row ─── */
function SideKpi({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: "15px 20px", borderBottom: "1px solid var(--line)" }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--text-3)", marginBottom: 5 }}>{label}</div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 600, letterSpacing: "-0.03em", color: color ?? "var(--text)", lineHeight: 1 }}>{value}</div>
    </div>
  );
}

/* ─── Section wrapper ─── */
function Section({ title, sub, action, children, stagger = 0 }: {
  title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode; stagger?: number;
}) {
  return (
    <div data-animate style={{ "--stagger": stagger } as React.CSSProperties}>
      <div className="card glass" style={{ padding: "28px 32px", borderRadius: "var(--r-xl)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--text)", marginBottom: 3 }}>{title}</h3>
            {sub && <p style={{ fontSize: 13, color: "var(--text-3)" }}>{sub}</p>}
          </div>
          {action}
        </div>
        {children}
      </div>
    </div>
  );
}

function Empty({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="empty-state" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "40px 20px" }}>
      <div className="empty-icon" style={{ color: "var(--text-3)", opacity: 0.5 }}>{icon}</div>
      <p className="empty-text" style={{ fontSize: 14, color: "var(--text-3)", margin: 0 }}>{text}</p>
    </div>
  );
}

/** Inline confidence pill with a bar + percentage label. */
function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.85 ? "var(--success)" : value >= 0.7 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: "var(--bg-inset)", borderRadius: 4, overflow: "hidden", minWidth: 60 }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 4, background: color, transition: "width 0.8s ease" }} />
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-3)", fontWeight: 600, flexShrink: 0 }}>
        {pct}%
      </span>
    </div>
  );
}

/* ═══════════ PAGE ═══════════ */
export default function CasePage() {
  const params = useParams<{ id: string }>();
  const caseId = params.id;

  const [caseData, setCaseData] = useState<CreditCase | null>(null);
  const [sampleData, setSampleData] = useState<SampleCase | undefined>(undefined);
  const [camData, setCamData] = useState<CAMResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const [uploadState, setUploadState] = useState({ loading: false, error: null as string | null, success: null as string | null });
  const [notesState, setNotesState] = useState({ loading: false, error: null as string | null, success: null as string | null });
  const [schemaState, setSchemaState] = useState({ loading: false });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerItems, setDrawerItems] = useState<EvidenceItem[]>([]);
  const [drawerSev, setDrawerSev] = useState<string | undefined>();

  const cc = sampleData ?? caseData;
  const cam = sampleData?.cam_result ?? camData ?? cc?.cam_result ?? null;
  const scoreResult = (sampleData?.score_result ?? (cc as Record<string, unknown>)?.score_result) as SampleCase["score_result"] | undefined;
  const facts = (cc?.extracted_facts ?? {}) as Record<string, unknown>;
  const flags = cc?.risk_flags ?? [];
  const decision = scoreResult?.decision ?? cam?.final_decision ?? "pending";
  const score = scoreResult?.overall_score ?? cam?.overall_score;
  const breakdown = scoreResult?.score_breakdown ?? cam?.score_breakdown ?? {};
  const limit = scoreResult?.recommended_limit ?? cam?.recommended_limit;
  const roi = scoreResult?.recommended_roi ?? cam?.recommended_roi;
  const officerSigs = scoreResult?.officer_note_signals;
  const reasons = scoreResult?.reasons ?? cam?.key_reasons ?? [];

  /**
   * Only include base metric keys — exclude:
   *  • Internal meta arrays/objects (extracted_entities, document_sources, auditor_remarks)
   *  • Sibling "_confidence" and "_source_ref" keys (shown inline in each row instead)
   */
  const factKeys = Object.keys(facts).filter(k =>
    !["extracted_entities", "document_sources", "auditor_remarks"].includes(k) &&
    !k.endsWith("_confidence") &&
    !k.endsWith("_source_ref")
  );

  const fetchCase = useCallback(async () => {
    if (!caseId) return;
    setLoading(true); setError(null);
    const sample = getSampleCase(caseId);
    if (sample) { setSampleData(sample); setLoading(false); return; }
    try {
      const data = await getCase(caseId);
      setCaseData(data);
      if (data.status === "ready") { setCamData(await getCAM(caseId)); }
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to load case"); }
    finally { setLoading(false); }
  }, [caseId]);

  useEffect(() => { fetchCase(); }, [fetchCase]);

  async function onUpload(files: File[]) {
    if (!caseId) return;
    setUploadState({ loading: true, error: null, success: null });
    try { await uploadCaseFiles(caseId, files); await fetchCase(); setUploadState({ loading: false, error: null, success: `Uploaded ${files.length} file(s)` }); }
    catch (e) { setUploadState({ loading: false, error: e instanceof Error ? e.message : "Upload failed", success: null }); }
  }

  async function onConfirmType(fileName: string, type: string) {
    if (!caseId) return;
    try {
      // confirmClassification needs to be imported from "@/lib/api"
      const { confirmClassification } = await import("@/lib/api");
      await confirmClassification(caseId, { file_name: fileName, confirmed_type: type });
      await fetchCase();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to confirm classification");
    }
  }

  async function onSaveNotes(v: string) {
    if (!caseId) return;
    setNotesState({ loading: true, error: null, success: null });
    try { setCaseData(await updateOfficerNotes(caseId, v)); setNotesState({ loading: false, error: null, success: "Saved" }); }
    catch (e) { setNotesState({ loading: false, error: e instanceof Error ? e.message : "Failed", success: null }); }
  }

  async function onSaveSchema(schema: Record<string, any>) {
    if (!caseId) return;
    setSchemaState({ loading: true });
    try {
      setCaseData(await updateSchema(caseId, schema));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save schema");
    } finally {
      setSchemaState({ loading: false });
    }
  }

  const STEPS = ["Extract", "Research", "Score", "CAM", "Done"];
  async function onAnalyze(selectedFileNames?: string[]) {
    if (!caseId) return;
    setAnalyzing(true); setError(null); setAnalysisStep(1);
    try {
      const a = await analyzeCase(caseId, selectedFileNames); setAnalysisStep(3); setCaseData(a);
      setAnalysisStep(4); setCamData(await getCAM(caseId)); setAnalysisStep(5);
    } catch (e) { setError(e instanceof Error ? e.message : "Analysis failed"); }
    finally { setAnalyzing(false); }
  }

  function openFlagEvidence(flag: RiskFlag) {
    setDrawerItems((flag.evidence_refs ?? []).map(r => ({
      source_document: r.split(":")[0] || r, page_or_section: r.split(":")[1] || "N/A",
      snippet: flag.description ?? "", confidence: flag.confidence ?? 0.5,
      why_it_matters: flag.impact_on_score ?? "This finding may materially impact the credit assessment.",
    })));
    setDrawerTitle(flag.flag_type?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) ?? "Risk Flag");
    setDrawerSev(flag.severity); setDrawerOpen(true);
  }

  function openFactEvidence(key: string) {
    const { confidence, source_ref } = getFlatMeta(facts, key);
    const val = facts[key];
    setDrawerItems(source_ref ? [{
      source_document: source_ref,
      page_or_section: "N/A",
      snippet: `Value: ${formatFactValue(key, val)}`,
      confidence: confidence ?? 0.5,
      why_it_matters: `This data point (${key.replace(/_/g, " ")}) directly influences the credit score.`,
    }] : []);
    setDrawerTitle(key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()));
    setDrawerSev(undefined); setDrawerOpen(true);
  }

  /* Loading */
  if (!caseId || loading) return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh", gap: 16, padding: "120px 24px" }}>
      <Loader2 className="animate-spin text-primary" size={32} color="var(--primary)" />
      <span style={{ fontSize: 15, color: "var(--text-3)", fontWeight: 500 }}>Loading case details…</span>
    </div>
  );

  if (!cc) return (
    <div style={{ textAlign: "center", padding: "80px 24px" }}>
      <p style={{ color: "var(--text-3)", marginBottom: 20, fontSize: 15 }}>Case not found.</p>
      <Link href="/" className="btn btn-secondary" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <ArrowLeft size={16} /> Back to Dashboard
      </Link>
    </div>
  );

  const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
  flags.forEach(f => { const s = (f.severity ?? "low") as keyof typeof sevCounts; if (s in sevCounts) sevCounts[s]++; });
  const dc = dClass(decision);

  /* Auditor remarks (special display) */
  const auditorRemarks = Array.isArray(facts.auditor_remarks)
    ? (facts.auditor_remarks as string[])
    : [];

  return (
    <>
      <EvidenceDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={drawerTitle} items={drawerItems} severity={drawerSev} />

      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 28, fontSize: 14, color: "var(--text-3)", animation: "fadeUp 0.3s ease both" }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-3)", textDecoration: "none", transition: "color 0.15s" }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--primary)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--text-3)")}
        >
          <ArrowLeft size={14} /> Dashboard
        </Link>
        <ChevronRight size={14} />
        <span style={{ color: "var(--text-2)", fontWeight: 500 }}>{cc.company_name}</span>
        {cc.sector && <><ChevronRight size={14} /><span>{cc.sector}</span></>}
      </div>

      {/* Analysis progress */}
      {analyzing && (
        <div className="card glass card-pad-sm" style={{ marginBottom: 24, borderRadius: "var(--r-xl)", animation: "slideInDown 0.3s ease" }}>
          <div className="step-progress">
            {STEPS.map((s, i) => (
              <div key={s} className={`step-item ${i + 1 < analysisStep ? "done" : i + 1 === analysisStep ? "active" : ""}`}>
                <div className="step-dot" style={{ display: "flex", alignItems: "center", justifyItems: "center" }}>
                  {i + 1 < analysisStep ? <CheckCircle2 size={14} /> : i + 1}
                </div>
                <span className="step-label">{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error toast */}
      {error && (
        <div className="toast-error" style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, padding: "16px", borderRadius: "var(--r-md)", backgroundColor: "var(--danger-soft)", border: "1px solid var(--danger-border)", color: "var(--danger)" }}>
          <AlertTriangle size={20} />
          <span style={{ flex: 1, fontSize: 14 }}>{error}</span>
          <button className="toast-dismiss" onClick={() => setError(null)} style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", display: "flex" }}>
            <X size={18} />
          </button>
        </div>
      )}

      {/* Decision banner */}
      {score != null && decision !== "pending" && (
        <div className={`decision-banner ${dc}`} style={{ marginBottom: 32, display: "flex", alignItems: "center", gap: 20 }}>
          <span className="db-icon" style={{ display: "flex" }}>{dIcon(decision)}</span>
          <div style={{ flex: 1 }}>
            <div className="db-title" style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>{dLabel(decision)}</div>
            <div className="db-sub" style={{ fontSize: 14, opacity: 0.8 }}>
              {scoreResult?.hard_override_applied ? (
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <AlertTriangle size={14} /> Hard Override: {scoreResult.hard_override_reason ?? "Critical flags triggered"}
                </span>
              ) : scoreResult?.decision_explanation ?? cam?.evidence_summary ?? ""}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="db-score" style={{ fontSize: 36, fontWeight: 800, fontFamily: "var(--font-mono)" }}>{score.toFixed(1)}</div>
            <div className="db-score-sub" style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>
              {[limit && `Limit: ${fmtInr(limit)}`, roi && `ROI: ${roi}%`].filter(Boolean).join("  ·  ")}
            </div>
          </div>
        </div>
      )}

      {/* Identity Mismatch Banner */}
      {(cc?.uploaded_files ?? []).some(f => f.is_mismatch) && (
        <div style={{ padding: "16px 20px", background: "var(--danger-soft)", border: "1px solid var(--danger-border)", borderRadius: "var(--r-lg)", marginBottom: "24px", display: "flex", alignItems: "flex-start", gap: 14 }}>
          <ShieldAlert size={24} color="var(--danger)" style={{ flexShrink: 0 }} />
          <div>
            <h4 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: "var(--danger)" }}>Identity Mismatch Detected</h4>
            <p style={{ margin: 0, fontSize: 13, color: "var(--danger)", opacity: 0.9, lineHeight: 1.5 }}>
              One or more uploaded documents appear to belong to a different entity. The extraction pipeline flagged a <strong>Critical Hard Override</strong>. Please review the documents carefully before proceeding.
            </p>
          </div>
        </div>
      )}

      {/* ══ LAYOUT: sidebar + main ══ */}
      <div style={{ display: "grid", gridTemplateColumns: "290px 1fr", gap: 24, alignItems: "start" }}>

        {/* SIDEBAR */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 18, position: "sticky", top: "calc(var(--topbar-h) + 24px)" }}>
          {/* Identity card */}
          <div className="card glass-sidebar" style={{ borderRadius: "var(--r-xl)", overflow: "hidden", animation: "fadeUp 0.4s ease 0.05s both" }}>
            {/* Header */}
            <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid var(--line)", background: "var(--glass-light)" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
                <h1 style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.025em", color: "var(--text)", lineHeight: 1.2 }}>{cc.company_name}</h1>
                {!sampleData && (
                  <button className="btn btn-primary btn-sm" onClick={() => onAnalyze()} disabled={analyzing} style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}>
                    {analyzing ? <><Loader2 size={14} className="animate-spin" />…</> : "▶ Run"}
                  </button>
                )}
              </div>
              <span className={`badge ${dc}`} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                {React.cloneElement(dIcon(decision) as React.ReactElement)}
                {decision.replace(/_/g, " ").toUpperCase()}
              </span>
            </div>

            {/* Score gauge */}
            <div style={{ padding: "24px 20px", borderBottom: "1px solid var(--line)", textAlign: "center" }}>
              <ScoreGauge score={score} />
            </div>

            <SideKpi label="Recommended Limit" value={fmtInr(limit)} />
            <SideKpi label="ROI" value={roi != null ? `${roi}%` : "—"} color={roi != null ? "var(--primary)" : undefined} />
            <SideKpi label="Risk Flags" value={String(flags.length)}
              color={sevCounts.critical + sevCounts.high > 0 ? "var(--danger)" : sevCounts.medium > 0 ? "var(--warning)" : "var(--success)"} />

            {/* Meta */}
            <div style={{ padding: "14px 20px" }}>
              {cc.sector && (
                <div style={{ display: "flex", gap: 8, marginBottom: 7, fontSize: 13 }}>
                  <span style={{ color: "var(--text-3)", width: 64, flexShrink: 0 }}>Sector</span>
                  <span style={{ color: "var(--text-2)", fontWeight: 500 }}>{cc.sector}</span>
                </div>
              )}
              {(cc.promoter_names ?? []).length > 0 && (
                <div style={{ display: "flex", gap: 8, marginBottom: 7, fontSize: 13 }}>
                  <span style={{ color: "var(--text-3)", width: 64, flexShrink: 0 }}>Promoters</span>
                  <span style={{ color: "var(--text-2)", fontWeight: 500 }}>{cc.promoter_names!.join(", ")}</span>
                </div>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 11 }}>
                <span style={{ color: "var(--text-3)", width: 64, flexShrink: 0 }}>Case ID</span>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-3)" }}>{cc.case_id}</span>
              </div>
            </div>
          </div>

          {/* Severity breakdown */}
          {flags.length > 0 && (
            <div className="card glass" style={{ padding: "18px 20px", borderRadius: "var(--r-xl)", animation: "fadeUp 0.4s ease 0.1s both" }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--text-3)", marginBottom: 14 }}>Flag Severity</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {([
                  { key: "critical", color: "var(--danger)" },
                  { key: "high", color: "var(--danger)" },
                  { key: "medium", color: "var(--warning)" },
                  { key: "low", color: "var(--info)" },
                ] as const).map(({ key, color }) => (
                  <div key={key} style={{ padding: "10px 14px", background: "var(--glass-light)", border: "1px solid var(--line)", borderRadius: "var(--r-md)", textAlign: "center", boxShadow: "inset 0 1px 0 var(--glass-hi)" }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: sevCounts[key] > 0 ? color : "var(--text-3)", marginBottom: 2, transition: "color 0.3s" }}>{sevCounts[key]}</div>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-3)" }}>{key}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Link href="/" className="btn btn-secondary" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, animation: "fadeUp 0.4s ease 0.15s both" }}>
            <ArrowLeft size={16} /> Dashboard
          </Link>
        </aside>

        {/* MAIN */}
        <AnimateIn>
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

            {/* Score Breakdown */}
            <Section title="Score Breakdown" sub="Weighted sub-score contribution to overall rating" stagger={0}>
              {Object.keys(breakdown).length === 0
                ? <Empty icon={<BarChart3 size={32} />} text="Run analysis to see the score breakdown." />
                : <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {Object.entries(breakdown).map(([cat, val], i) => (
                    <div key={cat} className="score-row" style={{ animationDelay: `${i * 0.06}s`, display: "flex", alignItems: "center", gap: 16 }}>
                      <span className="score-row-label" style={{ width: "180px", fontSize: 13, color: "var(--text-2)", textTransform: "capitalize" }}>
                        {cat.replace(/_/g, " ")}
                      </span>
                      <div className="score-row-track" style={{ flex: 1, height: 6, background: "var(--bg-inset)", borderRadius: 6, overflow: "hidden" }}>
                        <div className="score-row-fill" style={{ width: `${val}%`, height: "100%", borderRadius: 6, background: scoreColor(val) }} />
                      </div>
                      <span className="score-row-val" style={{ width: "36px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, color: scoreColor(val) }}>{val}</span>
                    </div>
                  ))}
                </div>
              }
              {scoreResult?.decision_explanation && (
                <p style={{ marginTop: 20, paddingTop: 18, borderTop: "1px solid var(--line)", fontSize: 14, color: "var(--text-2)", lineHeight: 1.7 }}>
                  {scoreResult.decision_explanation}
                </p>
              )}
            </Section>

            {/* CAM */}
            <Section title="Credit Appraisal Memo" sub="AI-generated summary with key decision factors" stagger={1}
              action={cam?.cam_doc_path ? (
                <button className="btn btn-secondary btn-sm" style={{ display: "flex", alignItems: "center", gap: 6 }}
                  onClick={() => window.open(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080"}/cases/${cc.case_id}/cam/download`, "_blank")}>
                  <Download size={14} /> DOCX
                </button>
              ) : undefined}
            >
              {!cam ? <Empty icon={<FileText size={32} />} text="CAM not generated yet. Run analysis to generate." /> : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                  {cam.evidence_summary && (
                    <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.75 }}>{cam.evidence_summary}</p>
                  )}
                  {reasons.length > 0 && (
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--text-3)", marginBottom: 12 }}>Key Reasons</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                        {reasons.slice(0, 8).map((r, i) => (
                          <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "9px 13px", background: "var(--glass-light)", border: "1px solid var(--line)", borderRadius: "var(--r-md)", fontSize: 13, color: "var(--text-2)", lineHeight: 1.5, boxShadow: "inset 0 1px 0 var(--glass-hi)" }}>
                            <span style={{ color: "var(--primary)", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>›</span>{r}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </Section>

            {/* Auditor Remarks (standalone, only when present) */}
            {auditorRemarks.length > 0 && (
              <Section title="Auditor Remarks" sub="Observations from statutory auditors" stagger={2}>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {auditorRemarks.map((remark, i) => (
                    <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "12px 16px", background: "var(--glass-light)", border: "1px solid var(--line)", borderLeft: "3px solid var(--info)", borderRadius: "var(--r-md)", fontSize: 14, color: "var(--text-2)", lineHeight: 1.6 }}>
                      <span style={{ color: "var(--info)", fontWeight: 700, flexShrink: 0 }}>✓</span>
                      {remark}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Financial Facts */}
            <Section title="Extracted Financial Facts"
              sub="AI-extracted metrics from uploaded documents — click any row to view source evidence"
              stagger={3}
              action={
                <span style={{ padding: "5px 13px", background: "var(--primary-soft)", color: "var(--primary)", border: "1px solid var(--primary-border)", borderRadius: "var(--r-full)", fontSize: 13, fontWeight: 700 }}>
                  {factKeys.length} metrics
                </span>
              }
            >
              {factKeys.length === 0
                ? <Empty icon={<Hash size={32} />} text="No financial facts extracted yet." />
                : (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th style={{ width: "28%" }}>Metric</th>
                          <th style={{ width: "18%" }}>Value</th>
                          <th style={{ width: "20%" }}>Source</th>
                          <th style={{ width: "24%" }}>Confidence</th>
                          <th style={{ width: "10%" }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {factKeys.map(key => {
                          const val = facts[key];
                          const { confidence, source_ref } = getFlatMeta(facts, key);
                          const displayValue = formatFactValue(key, val);
                          const isNA = displayValue === "N/A";

                          return (
                            <tr key={key} onClick={() => openFactEvidence(key)} style={{ cursor: "pointer", opacity: isNA ? 0.55 : 1 }}>
                              {/* Metric name */}
                              <td style={{ fontWeight: 600, color: "var(--text)" }}>
                                {key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                              </td>

                              {/* Value — no ₹ for ratios/scores/plain numbers */}
                              <td className="mono" style={{ fontWeight: 600, color: isNA ? "var(--text-3)" : "var(--text)", fontSize: 13 }}>
                                {displayValue}
                              </td>

                              {/* Source reference */}
                              <td style={{ fontSize: 12 }}>
                                {source_ref
                                  ? <span style={{ color: "var(--text-2)", display: "flex", alignItems: "center", gap: 5 }}>
                                    <File size={13} style={{ flexShrink: 0 }} />
                                    <span style={{ wordBreak: "break-all" }}>{source_ref}</span>
                                  </span>
                                  : <span style={{ color: "var(--text-3)" }}>—</span>
                                }
                              </td>

                              {/* Confidence bar — only when a number is available */}
                              <td>
                                {confidence != null
                                  ? <ConfidencePill value={confidence} />
                                  : <span style={{ color: "var(--text-3)", fontSize: 12 }}>—</span>
                                }
                              </td>

                              {/* Action */}
                              <td style={{ textAlign: "right" }}>
                                <span style={{ color: "var(--primary)", fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
                                  View <ArrowRight size={14} />
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )
              }
            </Section>

            {/* Risk Flags */}
            <Section title="Risk Flags" sub="Identified risk factors — click any card to view source evidence" stagger={4}
              action={<div style={{ display: "flex", gap: 6 }}>
                {sevCounts.critical > 0 && <span className="badge badge-red">{sevCounts.critical} critical</span>}
                {sevCounts.high > 0 && <span className="badge badge-red">{sevCounts.high} high</span>}
                {sevCounts.medium > 0 && <span className="badge badge-amber">{sevCounts.medium} medium</span>}
              </div>}
            >
              {flags.length === 0 ? <Empty icon={<ShieldAlert size={32} />} text="No risk flags generated yet." /> : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  {flags.map((flag, fi) => {
                    const sev = flag.severity ?? "low";
                    const sevColor = sev === "critical" || sev === "high" ? "var(--danger)" : sev === "medium" ? "var(--warning)" : "var(--info)";
                    return (
                      // Add the index (-${fi}) to guarantee a unique key
                      <div key={`${flag.flag_id ?? flag.description}-${fi}`}
                        className={`flag-card sev-${sev}`} onClick={() => openFlagEvidence(flag)}
                        style={{ animationDelay: `${fi * 0.05}s`, padding: "16px", background: "var(--glass-light)", border: "1px solid var(--line)", borderRadius: "var(--r-lg)", cursor: "pointer", borderLeft: `3px solid ${sevColor}` }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
                          <span className={`badge ${sev === "critical" || sev === "high" ? "badge-red" : sev === "medium" ? "badge-amber" : "badge-blue"}`}>{sev.toUpperCase()}</span>
                          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>{flag.flag_type?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                        </div>
                        <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-2)", lineHeight: 1.55 }}>{flag.description}</p>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--text-3)", fontWeight: 500 }}>
                            {flag.confidence != null && <span>Conf: {Math.round(flag.confidence * 100)}%</span>}
                            {(flag.evidence_refs ?? []).length > 0 && <span>{flag.evidence_refs!.length} source(s)</span>}
                          </div>
                          <span style={{ fontSize: 12, color: "var(--primary)", fontWeight: 700, display: "flex", alignItems: "center", gap: 4 }}>
                            Evidence <ArrowRight size={14} />
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Section>

            {/* Officer Signal Analysis */}
            {officerSigs && (
              <Section title="Officer Signal Analysis" sub="Structured signals from qualitative field observations" stagger={5}
                action={
                  <div style={{ padding: "8px 18px", background: `${scoreColor(officerSigs.composite_score)}12`, border: `1px solid ${scoreColor(officerSigs.composite_score)}30`, borderRadius: "var(--r-md)", display: "flex", alignItems: "baseline" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: scoreColor(officerSigs.composite_score) }}>{officerSigs.composite_score}</span>
                    <span style={{ fontSize: 12, color: "var(--text-3)", marginLeft: 7 }}>composite</span>
                  </div>
                }
              >
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
                  {(["capacity_utilization", "management_quality", "operational_health", "collection_risk", "site_visit_risk", "promoter_behavior_score"] as const).map(dim => {
                    const sig = officerSigs[dim];
                    if (!sig) return null;
                    const c = scoreColor(sig.score);
                    return (
                      <div key={dim} style={{ padding: "16px", background: "var(--glass)", border: "1px solid var(--line)", borderLeft: `3px solid ${c}`, borderRadius: "var(--r-lg)", boxShadow: "inset 0 1px 0 var(--glass-hi)" }}>
                        <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--text-3)" }}>{dim.replace(/_/g, " ")}</p>
                        <p style={{ margin: "0 0 8px", fontFamily: "var(--font-mono)", fontSize: 28, fontWeight: 700, color: c, lineHeight: 1 }}>{sig.score}</p>
                        {sig.explanations?.length > 0
                          ? sig.explanations.slice(0, 2).map((e, i) => <p key={i} style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-3)", lineHeight: 1.5 }}>· {e}</p>)
                          : <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-3)", lineHeight: 1.5, fontStyle: "italic" }}>No signals detected</p>
                        }
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}

            {/* Live: Docs + Notes + Schema */}
            {!sampleData && (
              <>
                <div data-animate style={{ "--stagger": 6, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 } as React.CSSProperties}>
                  <FileUpload
                    uploadedFiles={cc.uploaded_files ?? []}
                    onUpload={onUpload}
                    onConfirmType={onConfirmType}
                    onAnalyzeFiles={onAnalyze}
                    analyzing={analyzing}
                    loading={uploadState.loading}
                    error={uploadState.error}
                    success={uploadState.success}
                  />
                  <OfficerNotes initialValue={cc.officer_notes ?? ""} onSave={onSaveNotes} loading={notesState.loading} error={notesState.error} success={notesState.success} />
                </div>
                <div data-animate style={{ "--stagger": 7, marginTop: 24 } as React.CSSProperties}>
                  <SchemaBuilder initialSchema={cc.extraction_schema} onSave={onSaveSchema} loading={schemaState.loading} />
                </div>
              </>
            )}

            {/* Sample: Docs */}
            {sampleData && (cc.uploaded_files ?? []).length > 0 && (
              <Section title={`Uploaded Documents (${cc.uploaded_files!.length})`} stagger={7}>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead><tr><th>File Name</th><th>Type</th><th>Date</th></tr></thead>
                    <tbody>
                      {cc.uploaded_files!.map(f => (
                        <tr key={f.file_name}>
                          <td style={{ fontWeight: 600, color: "var(--text)", display: "flex", alignItems: "center", gap: 6 }}>
                            <File size={16} className="text-muted" /> {f.file_name}
                          </td>
                          <td style={{ fontSize: 13 }}>{f.doc_type || "—"}</td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{f.uploaded_at ? new Date(f.uploaded_at).toLocaleDateString() : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            )}

            {/* Sample: Officer Notes */}
            {sampleData && cc.officer_notes && (
              <Section title="Officer Notes" stagger={8}>
                <p style={{ margin: 0, padding: "16px 20px", background: "var(--glass)", border: "1px solid var(--line)", borderLeft: "3px solid var(--primary)", borderRadius: "var(--r-lg)", fontSize: 14, color: "var(--text-2)", lineHeight: 1.8, whiteSpace: "pre-wrap", boxShadow: "inset 0 1px 0 var(--glass-hi)" }}>
                  {cc.officer_notes}
                </p>
              </Section>
            )}

          </div>
        </AnimateIn>
      </div>
    </>
  );
}