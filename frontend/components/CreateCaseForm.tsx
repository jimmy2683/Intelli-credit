"use client";

import { FormEvent, useState } from "react";

type Props = {
  onCreate: (p: { company_name: string; sector: string; promoter_names: string[]; officer_notes: string }) => Promise<void>;
  loading: boolean; error: string | null; success: string | null;
};

const SECTORS = ["Pharmaceuticals","Manufacturing","Real Estate","IT Services","Infrastructure","FMCG","Retail","Financial Services","Agriculture","Other"];

function StepChip({ n, label, color }: { n: number; label: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18, paddingBottom: 16, borderBottom: "1px solid var(--line)" }}>
      <div style={{ width: 26, height: 26, borderRadius: "var(--r-sm)", background: color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "#fff", flexShrink: 0 }}>{n}</div>
      <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
    </div>
  );
}

export default function CreateCaseForm({ onCreate, loading, error, success }: Props) {
  const [companyName, setCompanyName] = useState("");
  const [sector, setSector]           = useState("");
  const [promoters, setPromoters]     = useState("");
  const [officerNotes, setOfficerNotes] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await onCreate({
      company_name: companyName.trim(), sector: sector.trim(),
      promoter_names: promoters.split(",").map(p => p.trim()).filter(Boolean),
      officer_notes: officerNotes.trim(),
    });
  }

  const promoterList = promoters.split(",").filter(p => p.trim());

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 32 }}>

        {/* Step 1 */}
        <div>
          <StepChip n={1} label="Company Identity" color="var(--primary)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div>
              <label htmlFor="cn">Company Name *</label>
              <input id="cn" value={companyName} onChange={e=>setCompanyName(e.target.value)} placeholder="e.g. Acme Manufacturing Ltd" required />
            </div>
            <div>
              <label htmlFor="sec">Industrial Sector *</label>
              <input id="sec" value={sector} onChange={e=>setSector(e.target.value)} placeholder="e.g. Pharmaceuticals" list="sectors" required />
              <datalist id="sectors">{SECTORS.map(s=><option key={s} value={s}/>)}</datalist>
            </div>
          </div>
        </div>

        {/* Step 2 */}
        <div>
          <StepChip n={2} label="Promoters & Directors" color="var(--accent)" />
          <div>
            <label htmlFor="prm">Names (comma-separated)</label>
            <input id="prm" value={promoters} onChange={e=>setPromoters(e.target.value)} placeholder="e.g. John Doe, Jane Smith" />
            {promoterList.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                {promoterList.map((p,i) => (
                  <span key={i} style={{ padding: "3px 10px", background: "var(--accent-2)", color: "var(--accent)", border: "1px solid var(--accent-2)", borderRadius: "var(--r-full)", fontSize: 12, fontWeight: 600 }}>
                    👤 {p.trim()}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Step 3 */}
        <div>
          <StepChip n={3} label="Officer Observations" color="var(--success)" />
          <div>
            <label htmlFor="on">Initial Notes <span style={{ color: "var(--text-3)", fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>(optional)</span></label>
            <textarea id="on" value={officerNotes} onChange={e=>setOfficerNotes(e.target.value)}
              placeholder="Site visit observations, management interaction notes..."
              style={{ minHeight: 110 }} />
          </div>
        </div>
      </div>

      {error   && <div className="msg-error"   style={{ marginTop: 20 }}>{error}</div>}
      {success && <div className="msg-success" style={{ marginTop: 20 }}>{success}</div>}

      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 14, marginTop: 24, paddingTop: 24, borderTop: "1px solid var(--line)" }}>
        <span style={{ fontSize: 13, color: "var(--text-3)" }}>Initializes the full AI analysis pipeline</span>
        <button className="btn btn-primary" type="submit" disabled={loading || !companyName.trim()}>
          {loading ? <><span className="spinner" /> Creating…</> : "Create Case & Run Pipeline →"}
        </button>
      </div>
    </form>
  );
}