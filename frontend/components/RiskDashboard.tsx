// RiskDashboard.tsx
import type { RiskFlag } from "@/lib/api";

type RiskDashboardProps = {
  status: string;
  score: number | undefined;
  riskFlags: RiskFlag[];
};

function scoreColor(v: number) {
  if (v >= 70) return "var(--success)";
  if (v >= 50) return "var(--warning)";
  return "var(--danger)";
}

export function RiskDashboard({ status, score, riskFlags }: RiskDashboardProps) {
  const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
  riskFlags.forEach((f) => {
    const s = (f.severity ?? "low") as keyof typeof sevCounts;
    if (s in sevCounts) sevCounts[s]++;
  });

  return (
    <section className="panel">
      <h2 className="section-title">Risk Dashboard</h2>

      <div className="grid two" style={{ marginBottom: 20 }}>
        <div className="kpi">
          <span className="label">Case Status</span>
          <span className="value" style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>
            {status}
          </span>
        </div>
        <div className={`kpi ${score != null ? (score >= 70 ? "green" : score >= 50 ? "amber" : "red") : ""}`}>
          <span className="label">Overall Score</span>
          <span className="value" style={{ color: score != null ? scoreColor(score) : undefined }}>
            {score?.toFixed(1) ?? "—"}
          </span>
          <span className="sub">out of 100</span>
        </div>
      </div>

      {/* Severity summary */}
      {riskFlags.length > 0 && (
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8,
          marginBottom: 20, padding: 14,
          background: "var(--bg-raised)", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)",
        }}>
          {([
            { key: "critical", label: "Critical", color: "var(--danger)" },
            { key: "high",     label: "High",     color: "var(--danger)" },
            { key: "medium",   label: "Medium",   color: "var(--warning)" },
            { key: "low",      label: "Low",      color: "var(--info)" },
          ] as const).map(({ key, label, color }) => (
            <div key={key} style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: sevCounts[key] > 0 ? color : "var(--text-muted)" }}>
                {sevCounts[key]}
              </div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      )}

      <h3 className="section-title" style={{ fontSize: 11, marginBottom: 12 }}>Risk Flags</h3>
      {riskFlags.length === 0 ? (
        <p className="muted">No risk flags generated yet.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {riskFlags.map((flag) => (
            <div
              key={flag.flag_id || `${flag.flag_type}-${flag.description}`}
              style={{
                padding: "10px 14px",
                background: "var(--bg-raised)",
                border: "1px solid var(--line)",
                borderLeft: `3px solid ${flag.severity === "critical" || flag.severity === "high" ? "var(--danger)" : flag.severity === "medium" ? "var(--warning)" : "var(--info)"}`,
                borderRadius: "var(--radius-sm)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{
                  padding: "2px 7px", borderRadius: 20, fontSize: 9, fontWeight: 700,
                  textTransform: "uppercase", letterSpacing: "0.06em",
                  background: flag.severity === "critical" || flag.severity === "high" ? "var(--danger-bg)" : flag.severity === "medium" ? "var(--warning-bg)" : "var(--info-bg)",
                  color: flag.severity === "critical" || flag.severity === "high" ? "var(--danger)" : flag.severity === "medium" ? "var(--warning)" : "var(--info)",
                  border: `1px solid ${flag.severity === "critical" || flag.severity === "high" ? "var(--danger-border)" : flag.severity === "medium" ? "var(--warning-border)" : "var(--info-border)"}`,
                }}>
                  {(flag.severity ?? "N/A").toUpperCase()}
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", fontFamily: "var(--font-display)" }}>
                  {flag.flag_type?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{flag.description}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default RiskDashboard;