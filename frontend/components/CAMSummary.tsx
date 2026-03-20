import type { CAMResult } from "@/lib/api";

type Props = { cam: CAMResult | null; };

function fmtInr(v: number | undefined | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return `₹${v.toLocaleString("en-IN")}`;
}

function decisionColor(d: string) {
  const l = d.toLowerCase();
  if (l.includes("approve")) return "var(--success)";
  if (l.includes("review") || l.includes("manual")) return "var(--warning)";
  return "var(--danger)";
}

export default function CAMSummary({ cam }: Props) {
  return (
    <section className="panel">
      <h2 className="section-title">CAM Preview</h2>

      {!cam ? (
        <div style={{
          textAlign: "center", padding: "32px 16px",
          background: "var(--bg-raised)", borderRadius: "var(--radius-sm)",
          border: "1px solid var(--line)",
        }}>
          <div style={{ fontSize: 28, marginBottom: 10, opacity: 0.4 }}>📄</div>
          <p className="muted">CAM is not available yet. Run analysis to generate preview.</p>
        </div>
      ) : (
        <>
          <div className="grid two" style={{ marginBottom: 16 }}>
            <div className="kpi" style={{ borderLeftColor: decisionColor(cam.final_decision ?? "") }}>
              <span className="label">Decision</span>
              <span className="value" style={{
                fontFamily: "var(--font-display)",
                fontSize: 15,
                color: decisionColor(cam.final_decision ?? ""),
              }}>{(cam.final_decision ?? "—").replace(/_/g, " ").toUpperCase()}</span>
            </div>
            <div className="kpi purple">
              <span className="label">Recommended Limit</span>
              <span className="value" style={{ fontSize: 18 }}>{fmtInr(cam.recommended_limit)}</span>
            </div>
          </div>

          {cam.recommended_roi != null && (
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 14px", background: "var(--bg-raised)",
              border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", marginBottom: 14,
            }}>
              <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Recommended ROI
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 700, color: "var(--text)" }}>
                {cam.recommended_roi}%
              </span>
            </div>
          )}

          {cam.evidence_summary && (
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 16 }}>
              {cam.evidence_summary}
            </p>
          )}

          {(cam.key_reasons ?? []).length > 0 && (
            <>
              <h3 className="section-title" style={{ fontSize: 11, marginBottom: 10 }}>Key Reasons</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {cam.key_reasons!.map((reason, i) => (
                  <div key={i} style={{
                    display: "flex", gap: 8, padding: "7px 11px",
                    background: "var(--bg-raised)", border: "1px solid var(--line)",
                    borderRadius: "var(--radius-xs)", fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5,
                  }}>
                    <span style={{ color: "var(--primary)", flexShrink: 0 }}>›</span>
                    {reason}
                  </div>
                ))}
              </div>
            </>
          )}

          {cam.cam_doc_path && (
            <div style={{ marginTop: 16, fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              📁 {cam.cam_doc_path}
            </div>
          )}
        </>
      )}
    </section>
  );
}