import type { UploadedFile, RiskFlag } from "@/lib/api";

type Props = {
  uploadedFiles: UploadedFile[];
  riskFlags: RiskFlag[];
};

export default function EvidenceList({ uploadedFiles, riskFlags }: Props) {
  return (
    <section className="panel">
      <h2 className="section-title">Evidence Viewer</h2>
      <p className="section-subtitle">Traceability from uploaded files to flagged findings</p>

      {/* Documents */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <h3 className="section-title" style={{ margin: 0, fontSize: 11, color: "var(--text-muted)" }}>Source Documents</h3>
          {uploadedFiles.length > 0 && (
            <span style={{
              padding: "2px 8px", background: "var(--primary-soft)", color: "var(--primary)",
              borderRadius: 20, fontSize: 10, fontWeight: 700, border: "1px solid rgba(91,142,240,0.2)",
            }}>{uploadedFiles.length}</span>
          )}
        </div>
        {uploadedFiles.length === 0 ? (
          <p className="muted">No documents available.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {uploadedFiles.map((f) => (
              <div key={`${f.file_name}-${f.file_path}`} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "9px 12px",
                background: "var(--bg-raised)",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
              }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>📄 {f.file_name}</span>
                <span style={{
                  fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)",
                  background: "var(--bg)", border: "1px solid var(--line)",
                  padding: "2px 7px", borderRadius: 4, fontWeight: 600,
                }}>{f.file_path}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evidence references */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <h3 className="section-title" style={{ margin: 0, fontSize: 11, color: "var(--text-muted)" }}>Evidence References</h3>
          {riskFlags.length > 0 && (
            <span style={{
              padding: "2px 8px", background: "var(--danger-bg)", color: "var(--danger)",
              borderRadius: 20, fontSize: 10, fontWeight: 700, border: "1px solid var(--danger-border)",
            }}>{riskFlags.length} flags</span>
          )}
        </div>
        {riskFlags.length === 0 ? (
          <p className="muted">No evidence references generated yet.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {riskFlags.map((f) => (
              <div key={f.flag_id || f.description} style={{
                padding: "9px 12px",
                background: "var(--bg-raised)",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
              }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, color: "var(--primary)",
                  }}>{f.flag_id || "flag"}</span>
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  {(f.evidence_refs ?? []).join(" · ") || "N/A"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}