"use client";

import React from "react";

type EvidenceItem = {
  source_document: string; page_or_section: string;
  snippet: string; confidence: number; why_it_matters: string;
};
type Props = {
  open: boolean; onClose: () => void; title: string;
  items: EvidenceItem[]; severity?: string;
};
export type { EvidenceItem };

export default function EvidenceDrawer({ open, onClose, title, items, severity }: Props) {
  if (!open) return null;

  const accentColor = severity==="critical"||severity==="high" ? "var(--danger)"
    : severity==="medium" ? "var(--warn)" : "var(--primary)";
  const accentBg    = severity==="critical"||severity==="high" ? "var(--danger-2)"
    : severity==="medium" ? "var(--warn-2)" : "var(--primary-2)";
  const accentBorder = severity==="critical"||severity==="high" ? "var(--danger-3)"
    : severity==="medium" ? "var(--warn-3)" : "var(--primary-3)";

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer-panel" style={{ borderTop: `3px solid ${accentColor}` }}>
        <button className="drawer-close" onClick={onClose}>✕</button>

        {/* Header */}
        <div style={{ marginBottom: 28, paddingRight: 44 }}>
          {severity && (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "4px 12px", marginBottom: 12,
              background: accentBg, border: `1px solid ${accentBorder}`,
              borderRadius: "var(--r-full)", fontSize: 11, fontWeight: 700,
              color: accentColor, textTransform: "uppercase", letterSpacing: "0.08em",
            }}>
              {severity==="critical"?"🔴":severity==="high"?"🟠":severity==="medium"?"🟡":"🔵"} {severity} severity
            </span>
          )}
          <h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-0.025em", color: "var(--text)", lineHeight: 1.25 }}>
            {title}
          </h2>
        </div>

        {items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <p className="empty-text">No evidence references for this item.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {items.map((item, i) => (
              <div key={i} style={{ background: "var(--bg-raised)", border: "1px solid var(--line-mid)", borderRadius: "var(--r-lg)", overflow: "hidden" }}>

                {/* Source header */}
                <div style={{ padding: "14px 18px", background: "var(--bg-surface)", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-3)", marginBottom: 4 }}>Source</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>📄 {item.source_document}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-3)", marginBottom: 4 }}>Location</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "var(--text-2)" }}>{item.page_or_section || "N/A"}</div>
                  </div>
                </div>

                {/* Snippet */}
                <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-3)", marginBottom: 10 }}>Source Text</div>
                  <div className="snippet-box">{item.snippet}</div>
                </div>

                {/* Confidence */}
                <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-3)", marginBottom: 10 }}>Confidence</div>
                  <div className="conf-row">
                    <div className="conf-track">
                      <div className="conf-fill" style={{
                        width: `${Math.round(item.confidence*100)}%`,
                        background: item.confidence>=0.85?"var(--success)":item.confidence>=0.7?"var(--warn)":"var(--danger)",
                      }}/>
                    </div>
                    <span className="conf-val" style={{ color: item.confidence>=0.85?"var(--success)":item.confidence>=0.7?"var(--warn)":"var(--danger)" }}>
                      {Math.round(item.confidence*100)}%
                    </span>
                  </div>
                </div>

                {/* Why it matters */}
                <div style={{ padding: "14px 18px", background: `${accentColor}08`, borderLeft: `3px solid ${accentColor}` }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-3)", marginBottom: 8 }}>Why It Matters</div>
                  <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)", lineHeight: 1.65 }}>{item.why_it_matters}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </aside>
    </>
  );
}