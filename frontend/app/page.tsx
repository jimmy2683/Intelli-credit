"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import CreateCaseForm from "@/components/CreateCaseForm";
import AnimateIn from "@/components/AnimateIn";
import { createCase } from "@/lib/api";
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
function dIcon(d: string) {
  if (d.toLowerCase().includes("approve")) return "✅";
  if (d.toLowerCase().includes("review") || d.toLowerCase().includes("manual")) return "⚠️";
  return "❌";
}
function scoreColor(v: number) {
  if (v >= 70) return "var(--success)";
  if (v >= 50) return "var(--warn)";
  return "var(--danger)";
}

function ScoreArc({ score }: { score: number | undefined }) {
  const s = score ?? 0;
  const r = 34, cx = 40, cy = 40, circ = 2 * Math.PI * r;
  const color = scoreColor(s);
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" style={{ flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6"/>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={circ} strokeDashoffset={circ * (1 - Math.min(s / 100, 1))}
        strokeLinecap="round" transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition:"stroke-dashoffset 1s ease", filter:`drop-shadow(0 0 5px ${color}80)` }}
      />
      <text x={cx} y={cy-3} textAnchor="middle" dominantBaseline="central"
        style={{ fontFamily:"var(--font-mono)", fontSize:17, fontWeight:700, fill:color }}>
        {score != null ? s.toFixed(0) : "—"}
      </text>
      <text x={cx} y={cy+14} textAnchor="middle"
        style={{ fontSize:8, fill:"var(--text-3)", fontWeight:600, letterSpacing:"0.05em" }}>
        SCORE
      </text>
    </svg>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function handleCreate(payload: { company_name: string; sector: string; promoter_names: string[]; officer_notes: string }) {
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
    <div style={{ display:"flex", flexDirection:"column", gap:52 }}>

      {/* ═══ HERO ═══ */}
      <AnimateIn>
        <section style={{
          position:"relative",
          background:"var(--glass-bg)",
          border:"1px solid var(--glass-border)",
          borderTopColor:"var(--glass-top)",
          borderRadius:"var(--r-xl)",
          padding:"68px 72px",
          overflow:"hidden",
          backdropFilter:"blur(24px) saturate(160%)",
          WebkitBackdropFilter:"blur(24px) saturate(160%)",
          boxShadow:"var(--shadow), inset 0 1px 0 var(--glass-shine)",
        }}>
          {/* ambient glow blobs */}
          <div style={{ position:"absolute",top:-100,left:-100,width:500,height:500,borderRadius:"50%", background:"radial-gradient(circle,rgba(79,142,247,0.09) 0%,transparent 70%)", pointerEvents:"none" }}/>
          <div style={{ position:"absolute",bottom:-80,right:-60,width:400,height:400,borderRadius:"50%", background:"radial-gradient(circle,rgba(155,127,238,0.08) 0%,transparent 70%)", pointerEvents:"none" }}/>

          {/* inner shimmer stripe */}
          <div style={{ position:"absolute",top:"-30%",left:"40%",width:"80px",height:"160%", background:"linear-gradient(180deg,transparent 0%,var(--glass-shine) 40%,transparent 100%)", transform:"rotate(20deg)",pointerEvents:"none" }}/>

          <div style={{ position:"relative", maxWidth:680 }}>
            {/* pill */}
            <div style={{
              display:"inline-flex",alignItems:"center",gap:8,marginBottom:26,
              padding:"6px 14px",borderRadius:"var(--r-full)",
              background:"var(--primary-2)",border:"1px solid var(--primary-3)",
              backdropFilter:"blur(8px)",
            }}>
              <span style={{ width:7,height:7,borderRadius:"50%",background:"var(--primary)",display:"inline-block",animation:"blink 2s infinite" }}/>
              <span style={{ fontSize:12,fontWeight:700,color:"var(--primary)",textTransform:"uppercase",letterSpacing:"0.08em" }}>
                AI-Powered Credit Intelligence
              </span>
            </div>

            <h1 style={{
              fontFamily:"var(--font)", fontSize:"clamp(34px,4vw,54px)", fontWeight:800,
              letterSpacing:"-0.04em", lineHeight:1.06, color:"var(--text)", marginBottom:22,
            }}>
              Corporate Credit<br/>
              <span style={{
                background:"linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%)",
                WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent", backgroundClip:"text",
              }}>Appraisal Workbench</span>
            </h1>

            <p style={{ fontSize:17, color:"var(--text-2)", lineHeight:1.72, marginBottom:38, maxWidth:560 }}>
              Upload borrower documents, run AI‑assisted analysis, and generate Credit Appraisal Memos
              with full evidence traceability — in minutes, not days.
            </p>

            <div style={{ display:"flex", gap:14, flexWrap:"wrap" }}>
              <Link href="/cases/demo_healthy_001" style={{ textDecoration:"none" }}>
                <button className="btn btn-primary btn-lg" style={{ boxShadow:"0 6px 28px var(--primary-3)" }}>
                  ▶ Try Healthy Borrower Demo
                </button>
              </Link>
              <Link href="/cases/demo_risky_002" style={{ textDecoration:"none" }}>
                <button className="btn btn-lg" style={{
                  background:"linear-gradient(135deg,#7f1d1d,#b91c1c)",
                  color:"#fff",border:"none",
                  boxShadow:"0 6px 28px rgba(185,28,28,0.35), inset 0 1px 0 rgba(255,255,255,0.1)",
                }}>⚠ Try Risky Borrower Demo</button>
              </Link>
            </div>
          </div>

          {/* floating stats */}
          <div style={{ position:"absolute", right:72, top:"50%", transform:"translateY(-50%)", display:"flex", flexDirection:"column", gap:16 }}>
            {[
              { val:"94.2%", lbl:"Accuracy" },
              { val:"< 3min", lbl:"Avg. Time" },
              { val:"1,200+", lbl:"Cases" },
            ].map((s,i) => (
              <div key={s.lbl} className="float-anim" style={{
                background:"var(--glass-bg-2)", border:"1px solid var(--glass-border)",
                borderTopColor:"var(--glass-top)",
                backdropFilter:"blur(20px)",
                WebkitBackdropFilter:"blur(20px)",
                borderRadius:"var(--r-lg)",
                padding:"16px 24px", textAlign:"center", minWidth:130,
                boxShadow:"var(--shadow-sm), inset 0 1px 0 var(--glass-shine)",
                animationDelay:`${i * 0.5}s`,
              }}>
                <div style={{ fontFamily:"var(--font-mono)", fontSize:22, fontWeight:700, color:"var(--text)", letterSpacing:"-0.03em" }}>{s.val}</div>
                <div style={{ fontSize:11, fontWeight:700, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.09em", marginTop:3 }}>{s.lbl}</div>
              </div>
            ))}
          </div>
        </section>
      </AnimateIn>

      {/* ═══ CASES ═══ */}
      <section>
        <AnimateIn>
          <div style={{ display:"flex", alignItems:"baseline", justifyContent:"space-between", marginBottom:28 }}>
            <div>
              <h2 style={{ fontSize:26, fontWeight:800, letterSpacing:"-0.03em", color:"var(--text)", marginBottom:5 }}>
                Preloaded Cases
              </h2>
              <p style={{ fontSize:14, color:"var(--text-3)" }}>Click any case to open the full analysis dashboard</p>
            </div>
            <span style={{
              padding:"5px 14px", background:"var(--primary-2)", color:"var(--primary)",
              border:"1px solid var(--primary-3)", borderRadius:"var(--r-full)",
              fontSize:13, fontWeight:700, backdropFilter:"blur(8px)",
            }}>{SAMPLE_CASES.length} cases</span>
          </div>
        </AnimateIn>

        <AnimateIn>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(420px,1fr))", gap:20 }}>
            {SAMPLE_CASES.map((c) => {
              const score  = c.score_result?.overall_score ?? c.cam_result?.overall_score;
              const dec    = c.score_result?.decision ?? c.cam_result?.final_decision ?? "pending";
              const flags  = c.risk_flags?.length ?? 0;
              const crit   = c.risk_flags?.filter(f => f.severity==="critical"||f.severity==="high").length ?? 0;
              const dc     = dClass(dec);
              const accent = score != null && score >= 70 ? "var(--success)" : score != null && score >= 50 ? "var(--warn)" : "var(--danger)";

              return (
                <Link key={c.case_id} href={`/cases/${c.case_id}`} style={{ textDecoration:"none" }}>
                  <div
                    className="card card-interactive"
                    style={{ padding:"24px 28px", borderTop:`3px solid ${accent}` }}
                  >
                    {/* card inner shine */}
                    <div style={{ display:"flex", alignItems:"flex-start", gap:16, marginBottom:20 }}>
                      <ScoreArc score={score}/>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:6, flexWrap:"wrap" }}>
                          <span style={{ fontSize:17, fontWeight:700, color:"var(--text)", letterSpacing:"-0.01em" }}>{c.company_name}</span>
                          <span className={`badge ${dc}`}>{dIcon(dec)} {dec.replace(/_/g," ").toUpperCase()}</span>
                        </div>
                        <p style={{ fontSize:13, color:"var(--text-3)", margin:0 }}>
                          {c.sector}{(c.promoter_names ?? []).length > 0 && <> &nbsp;·&nbsp; {c.promoter_names!.join(", ")}</>}
                        </p>
                      </div>
                    </div>

                    <div style={{
                      display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:0,
                      background:"var(--glass-bg-2)", borderRadius:"var(--r-md)",
                      border:"1px solid var(--glass-border)", overflow:"hidden",
                      backdropFilter:"blur(10px)",
                    }}>
                      {[
                        { l:"Credit Limit", v:fmtInr(c.cam_result?.recommended_limit) },
                        { l:"Risk Flags",   v:String(flags) + (crit>0 ? ` (${crit}⚠)` : "") },
                        { l:"ROI",          v:c.cam_result?.recommended_roi ? `${c.cam_result.recommended_roi}%` : "—" },
                      ].map((s,si) => (
                        <div key={s.l} style={{ padding:"12px 16px", borderRight:si<2?"1px solid var(--glass-border)":"none" }}>
                          <div style={{ fontSize:10, fontWeight:700, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:4 }}>{s.l}</div>
                          <div style={{ fontFamily:"var(--font-mono)", fontSize:14, fontWeight:600, color:s.l==="Risk Flags"&&crit>0?"var(--danger)":"var(--text)" }}>{s.v}</div>
                        </div>
                      ))}
                    </div>

                    <div style={{ marginTop:14, textAlign:"right", fontSize:12, fontWeight:700, color:"var(--primary)" }}>
                      Open Analysis →
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </AnimateIn>
      </section>

      {/* ═══ ERROR / SUCCESS ═══ */}
      {error && (
        <div className="toast-error">
          <span style={{ fontSize:18 }}>⚠️</span>
          <span style={{ flex:1 }}>{error}</span>
          <button className="toast-dismiss" onClick={()=>setError(null)}>✕</button>
        </div>
      )}
      {success && <div className="msg-success">{success}</div>}

      {/* ═══ CREATE CASE ═══ */}
      <AnimateIn>
        <section className="card card-pad">
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:showCreate?28:0 }}>
            <div>
              <h2 style={{ fontSize:22, fontWeight:800, letterSpacing:"-0.025em", color:"var(--text)", marginBottom:4 }}>
                Create New Case
              </h2>
              <p style={{ fontSize:14, color:"var(--text-3)" }}>Start a fresh credit appraisal pipeline</p>
            </div>
            <button
              className="btn"
              style={{
                background:showCreate?"var(--glass-bg-2)":"var(--primary-2)",
                color:showCreate?"var(--text-3)":"var(--primary)",
                borderColor:showCreate?"var(--glass-border)":"var(--primary-3)",
                backdropFilter:"blur(12px)",
                fontSize:14, fontWeight:700,
                transition:"all 0.25s var(--ease-spring)",
              }}
              onClick={() => setShowCreate(!showCreate)}
            >
              {showCreate ? "✕ Cancel" : "+ New Case"}
            </button>
          </div>

          <div style={{
            maxHeight: showCreate ? "800px" : "0px",
            overflow:"hidden",
            transition:"max-height 0.45s var(--ease-smooth), opacity 0.35s",
            opacity: showCreate ? 1 : 0,
          }}>
            <div style={{ height:1, background:"var(--line)", marginBottom:28 }}/>
            <CreateCaseForm onCreate={handleCreate} loading={loading} error={error} success={success} />
          </div>
        </section>
      </AnimateIn>

    </div>
  );
}