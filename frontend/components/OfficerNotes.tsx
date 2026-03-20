"use client";

import { useEffect, useState } from "react";

type Props = {
  initialValue: string; onSave: (v: string) => Promise<void>;
  loading: boolean; error: string | null; success: string | null;
};

const CHIPS = ["Capacity utilization", "Management quality", "Site condition", "Promoter intent", "Repayment track record"];

export default function OfficerNotes({ initialValue, onSave, loading, error, success }: Props) {
  const [value, setValue]   = useState(initialValue);
  const [dirty, setDirty]   = useState(false);

  useEffect(() => { setValue(initialValue); setDirty(false); }, [initialValue]);

  function change(v: string) { setValue(v); setDirty(v !== initialValue); }

  const words = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <div className="card card-pad">
      <div style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.015em", color: "var(--text)", marginBottom: 4 }}>
          Officer Observations
        </h3>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>Qualitative insights from site visits and management meetings</p>
      </div>

      {/* Quick-insert chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 14 }}>
        {CHIPS.map(chip => (
          <button key={chip} type="button"
            onClick={() => change(value + (value ? "\n" : "") + chip + ": ")}
            style={{
              padding: "4px 11px", background: "var(--bg-raised)", color: "var(--text-2)",
              border: "1px solid var(--line-mid)", borderRadius: "var(--r-full)",
              fontSize: 12, cursor: "pointer", fontFamily: "var(--font)", fontWeight: 600,
              transition: "all 0.15s",
            }}
            onMouseEnter={e => { const el=e.currentTarget; el.style.borderColor="var(--primary)"; el.style.color="var(--primary)"; el.style.background="var(--primary-2)"; }}
            onMouseLeave={e => { const el=e.currentTarget; el.style.borderColor="var(--line-mid)"; el.style.color="var(--text-2)"; el.style.background="var(--bg-raised)"; }}
          >+ {chip}</button>
        ))}
      </div>

      {/* Textarea */}
      <div style={{ position: "relative", marginBottom: 12 }}>
        <textarea value={value} onChange={e=>change(e.target.value)}
          placeholder="Factory running at ~85% capacity, management cooperative during site visit..."
          style={{ minHeight: 150, paddingBottom: 36 }}
        />
        <div style={{
          position: "absolute", bottom: 12, right: 14,
          fontSize: 11, color: "var(--text-3)", fontFamily: "var(--font-mono)",
          background: "var(--bg-raised)", padding: "2px 8px", borderRadius: "var(--r-sm)",
          border: "1px solid var(--line)", pointerEvents: "none",
        }}>
          {words} words
        </div>
      </div>

      {error   && <div className="msg-error"   style={{ marginBottom: 12 }}>{error}</div>}
      {success && <div className="msg-success" style={{ marginBottom: 12 }}>{success}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {dirty
          ? <span style={{ fontSize: 13, color: "var(--warn)", fontWeight: 600 }}>● Unsaved changes</span>
          : <span />
        }
        <button className="btn btn-secondary" onClick={() => onSave(value)} disabled={loading || !dirty}>
          {loading ? <><span className="spinner spinner-dark" /> Saving…</> : "Save Observations"}
        </button>
      </div>
    </div>
  );
}