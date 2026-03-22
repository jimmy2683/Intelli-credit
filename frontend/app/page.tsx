"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Play, 
  ArrowRight, 
  X, 
  Plus, 
  Activity, 
  Clock, 
  Database,
  Sparkles
} from "lucide-react";
import CreateCaseForm from "@/components/CreateCaseForm";
import AnimateIn from "@/components/AnimateIn";
import { createCase, getCases, CreditCase } from "@/lib/api";
import { SAMPLE_CASES } from "@/lib/sampleData";

function fmtInr(v: number | undefined | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return `₹${v.toLocaleString("en-IN")}`;
}

function dClass(d: string) {
  const l = d.toLowerCase().replace(/_/g, "");
  if (l.includes("approve")) return "approve";
  if (l.includes("review") || l.includes("manual")) return "review";
  return "decline";
}

function dIcon(d: string, size = 14) {
  const l = d.toLowerCase();
  if (l.includes("approve")) return <CheckCircle2 size={size} />;
  if (l.includes("review") || l.includes("manual")) return <AlertTriangle size={size} />;
  return <XCircle size={size} />;
}

function scoreColor(v: number) {
  if (v >= 70) return "var(--success)";
  if (v >= 50) return "var(--warning)";
  return "var(--danger)";
}

function ScoreArc({ score }: { score: number | undefined }) {
  const s = score ?? 0;
  const r = 34, cx = 40, cy = 40, circ = 2 * Math.PI * r;
  const color = scoreColor(s);
  return (
    <div style={{ position: "relative", display: "inline-flex" }}>
      <svg width="80" height="80" viewBox="0 0 80 80" style={{ flexShrink: 0 }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--line)" strokeWidth="6" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - Math.min(s / 100, 1))}
          strokeLinecap="round" transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1) 0.2s", filter: `drop-shadow(0 0 6px ${color}60)` }}
        />
        <text x={cx} y={cy - 3} textAnchor="middle" dominantBaseline="central"
          style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 700, fill: color }}>
          {score != null ? s.toFixed(0) : "—"}
        </text>
        <text x={cx} y={cy + 16} textAnchor="middle"
          style={{ fontSize: 9, fill: "var(--text-3)", fontWeight: 700, letterSpacing: "0.05em" }}>
          SCORE
        </text>
      </svg>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [cases, setCases] = React.useState<CreditCase[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]     = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);
  const [showCreate, setShowCreate] = React.useState(false);

  React.useEffect(() => {
    async function load() {
      try {
        const data = await getCases();
        setCases(data);
      } catch (e) {
        console.error("Failed to fetch cases:", e);
        setError("Failed to load cases from backend.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleCreate(payload: {
    company_name: string;
    cin_optional?: string;
    pan?: string;
    sector: string;
    turnover?: number;
    loan_type?: string;
    loan_amount?: number;
    tenure_months?: number;
    interest_rate?: number;
    promoter_names: string[];
    officer_notes: string;
  }) {
    if (!payload.company_name.trim()) { setError("Company name is required."); return; }
    setError(null); setSuccess(null); setLoading(true);
    try {
      const c = await createCase(payload);
      setSuccess(`Case ${c.case_id} created.`);
      router.push(`/cases/${c.case_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setLoading(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 52 }}>

      {/* ═══ HERO ═══ */}
      <AnimateIn>
        <section className="card" style={{
          padding: "68px 72px",
          display: "grid",
          gridTemplateColumns: "1fr auto",
          gap: "40px",
          alignItems: "center",
        }}>
          {/* inner shimmer stripe */}
          <div style={{ position: "absolute", top: "-30%", left: "40%", width: "80px", height: "160%", background: "linear-gradient(180deg, transparent 0%, var(--glass-hi) 40%, transparent 100%)", transform: "rotate(20deg)", pointerEvents: "none", opacity: 0.5 }} />

          <div style={{ position: "relative", maxWidth: 680 }}>
            {/* pill */}
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 26,
              padding: "6px 14px", borderRadius: "var(--r-full)",
              background: "var(--primary-soft)", border: "1px solid var(--primary-border)",
            }}>
              <Sparkles size={14} className="text-primary" />
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                AI-Powered Credit Intelligence
              </span>
            </div>

            <h1 style={{
              fontFamily: "var(--font)", fontSize: "clamp(34px, 4vw, 54px)", fontWeight: 800,
              letterSpacing: "-0.04em", lineHeight: 1.06, color: "var(--text)", marginBottom: 22,
            }}>
              Corporate Credit<br />
              <span style={{ color: "var(--primary)" }}>Appraisal Workbench</span>
            </h1>

            <p style={{ fontSize: 17, color: "var(--text-2)", lineHeight: 1.72, marginBottom: 38, maxWidth: 560 }}>
              Upload borrower documents, run AI‑assisted analysis, and generate Credit Appraisal Memos
              with full evidence traceability — in minutes, not days.
            </p>

            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <Link href="/cases/demo_healthy_001" style={{ textDecoration: "none" }}>
                <button className="btn btn-primary btn-lg" style={{ boxShadow: "0 6px 24px var(--primary-soft)" }}>
                  <Play size={16} fill="currentColor" /> Try Healthy Borrower Demo
                </button>
              </Link>
              <Link href="/cases/demo_risky_002" style={{ textDecoration: "none" }}>
                <button className="btn btn-lg" style={{
                  background: "var(--danger-soft)", color: "var(--danger)", border: "1px solid var(--danger-border)",
                  boxShadow: "0 6px 24px var(--danger-soft)",
                }}>
                  <AlertTriangle size={16} /> Try Risky Borrower Demo
                </button>
              </Link>
            </div>
          </div>

          {/* floating stats */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[
              { val: "94.2%", lbl: "Accuracy", icon: <Activity size={18} /> },
              { val: "< 2min", lbl: "Avg. Time", icon: <Clock size={18} /> },
              { val: "1,200+", lbl: "Cases", icon: <Database size={18} /> },
            ].map((s, i) => (
              <div key={s.lbl} style={{
                background: "var(--glass-light)", border: "1px solid var(--line)",
                backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
                borderRadius: "var(--r-lg)", padding: "16px 24px", minWidth: 160,
                boxShadow: "var(--sh-sm), inset 0 1px 0 var(--glass-hi)",
                display: "flex", alignItems: "center", gap: 16,
                animationDelay: `${i * 0.15}s`,
                animation: "fadeUp 0.6s var(--ease) forwards",
                opacity: 0,
              }}>
                <div style={{ color: "var(--primary)", opacity: 0.8 }}>{s.icon}</div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.03em", lineHeight: 1.1 }}>{s.val}</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.09em", marginTop: 4 }}>{s.lbl}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </AnimateIn>

      {/* ═══ CASES ═══ */}
      <section>
        <AnimateIn stagger={1}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 28 }}>
            <div>
              <h2 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.03em", color: "var(--text)", marginBottom: 5 }}>
                Recent Cases
              </h2>
              <p style={{ fontSize: 14, color: "var(--text-3)" }}>Click any case to open the full analysis dashboard</p>
            </div>
            <span style={{
              padding: "5px 14px", background: "var(--primary-soft)", color: "var(--primary)",
              border: "1px solid var(--primary-border)", borderRadius: "var(--r-full)",
              fontSize: 13, fontWeight: 700, backdropFilter: "blur(8px)",
            }}>{cases.length} cases</span>
          </div>
        </AnimateIn>

        <AnimateIn stagger={2}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 24 }}>
            {loading ? (
              <div style={{ gridColumn: "1/-1", textAlign: "center", padding: "40px", color: "var(--text-3)" }}>
                <Activity size={32} style={{ animation: "spin 2s linear infinite", marginBottom: 12 }} />
                <p>Loading cases...</p>
              </div>
            ) : cases.length === 0 ? (
              <div style={{ gridColumn: "1/-1", textAlign: "center", padding: "40px", color: "var(--text-3)", background: "var(--glass-light)", borderRadius: "var(--r-lg)", border: "1px dashed var(--line)" }}>
                <Database size={32} style={{ marginBottom: 12, opacity: 0.5 }} />
                <p>No cases found. Create a new one below.</p>
              </div>
            ) : (
              cases.map((c) => {
                const score = c.score_result?.overall_score ?? c.cam_result?.overall_score;
                const dec = c.score_result?.decision ?? c.cam_result?.final_decision ?? "pending";
                const flags = c.risk_flags?.length ?? 0;
                const crit = c.risk_flags?.filter(f => (f.severity === "critical" || f.severity === "high")).length ?? 0;
                const dc = dClass(dec);
                const accent = score != null && score >= 70 ? "var(--success)" : score != null && score >= 50 ? "var(--warning)" : "var(--danger)";

                return (
                  <Link key={c.case_id} href={`/cases/${c.case_id}`} style={{ textDecoration: "none", color: "inherit" }}>
                    <div
                      className="card"
                      style={{ padding: "28px", borderTop: `3px solid ${accent}`, cursor: "pointer", display: "flex", flexDirection: "column", height: "100%" }}
                    >
                      <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 24 }}>
                        <ScoreArc score={score} />
                        <div style={{ flex: 1, minWidth: 0, marginTop: 4 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                            <span style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.01em" }}>{c.company_name}</span>
                            <span className={`badge ${dc}`}>
                              {dIcon(dec, 12)} {dec.replace(/_/g, " ").toUpperCase()}
                            </span>
                          </div>
                          <p style={{ fontSize: 13, color: "var(--text-2)", margin: 0, lineHeight: 1.5 }}>
                            {c.sector}{(c.promoter_names ?? []).length > 0 && <> &nbsp;·&nbsp; {c.promoter_names!.join(", ")}</>}
                          </p>
                        </div>
                      </div>

                      <div style={{
                        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0,
                        background: "var(--glass-light)", borderRadius: "var(--r-md)",
                        border: "1px solid var(--line)", overflow: "hidden",
                        backdropFilter: "blur(10px)", marginTop: "auto"
                      }}>
                        {[
                          { l: "Credit Limit", v: fmtInr(c.cam_result?.recommended_limit) },
                          { l: "Risk Flags", v: String(flags) + (crit > 0 ? ` (${crit}⚠)` : "") },
                          { l: "ROI", v: c.cam_result?.recommended_roi ? `${c.cam_result.recommended_roi}%` : "—" },
                        ].map((s, si) => (
                          <div key={s.l} style={{ padding: "14px 16px", borderRight: si < 2 ? "1px solid var(--line)" : "none" }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{s.l}</div>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 600, color: s.l === "Risk Flags" && crit > 0 ? "var(--danger)" : "var(--text)" }}>{s.v}</div>
                          </div>
                        ))}
                      </div>

                      <div style={{ marginTop: 20, textAlign: "right", fontSize: 13, fontWeight: 700, color: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6 }}>
                        Open Analysis <ArrowRight size={14} />
                      </div>
                    </div>
                  </Link>
                );
              })
            )}
          </div>
        </AnimateIn>
      </section>

      {/* ═══ ERROR / SUCCESS ═══ */}
      {error && (
        <div className="toast-error" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <AlertTriangle size={20} />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="toast-dismiss" onClick={() => setError(null)} style={{ display: "flex", background: "transparent", border: "none" }}><X size={18} /></button>
        </div>
      )}
      {success && (
        <div className="msg-success" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}

      {/* ═══ CREATE CASE ═══ */}
      <AnimateIn stagger={3}>
        <section className="card card-pad">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: showCreate ? 28 : 0 }}>
            <div>
              <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.025em", color: "var(--text)", marginBottom: 4 }}>
                Create New Case
              </h2>
              <p style={{ fontSize: 14, color: "var(--text-3)" }}>Start a fresh credit appraisal pipeline</p>
            </div>
            <button
              className="btn"
              style={{
                background: showCreate ? "var(--glass-light)" : "var(--primary-soft)",
                color: showCreate ? "var(--text-2)" : "var(--primary)",
                border: `1px solid ${showCreate ? "var(--line)" : "var(--primary-border)"}`,
                backdropFilter: "blur(12px)",
                fontSize: 14, fontWeight: 700,
                transition: "all 0.25s var(--ease)",
              }}
              onClick={() => setShowCreate(!showCreate)}
            >
              {showCreate ? <><X size={16} /> Cancel</> : <><Plus size={16} /> New Case</>}
            </button>
          </div>

          <div style={{
            maxHeight: showCreate ? "800px" : "0px",
            overflow: "hidden",
            transition: "max-height 0.45s var(--ease), opacity 0.35s var(--ease)",
            opacity: showCreate ? 1 : 0,
          }}>
            <div style={{ height: 1, background: "var(--line)", marginBottom: 28 }} />
            <CreateCaseForm onCreate={handleCreate} loading={loading} error={error} success={success} />
          </div>
        </section>
      </AnimateIn>

    </div>
  );
}