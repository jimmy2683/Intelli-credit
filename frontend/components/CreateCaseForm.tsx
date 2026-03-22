"use client";

import { FormEvent, useState } from "react";

type Props = {
  onCreate: (p: {
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
  }) => Promise<void>;
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
  const [cin, setCin]                 = useState("");
  const [pan, setPan]                 = useState("");
  const [sector, setSector]           = useState("");
  const [turnover, setTurnover]       = useState("");

  const [loanType, setLoanType]       = useState("Term Loan");
  const [loanAmount, setLoanAmount]   = useState("");
  const [tenure, setTenure]           = useState("");
  const [interest, setInterest]       = useState("");

  const [promoters, setPromoters]     = useState("");
  const [officerNotes, setOfficerNotes] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await onCreate({
      company_name: companyName.trim(),
      cin_optional: cin.trim(),
      pan: pan.trim(),
      sector: sector.trim(),
      turnover: turnover ? parseFloat(turnover) : undefined,
      loan_type: loanType.trim(),
      loan_amount: loanAmount ? parseFloat(loanAmount) : undefined,
      tenure_months: tenure ? parseInt(tenure, 10) : undefined,
      interest_rate: interest ? parseFloat(interest) : undefined,
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
          <StepChip n={1} label="Entity Details" color="var(--primary)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label htmlFor="cn">Company Name *</label>
              <input id="cn" value={companyName} onChange={e=>setCompanyName(e.target.value)} placeholder="e.g. Acme Manufacturing Ltd" required />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label htmlFor="cin">CIN</label>
                <input id="cin" value={cin} onChange={e=>setCin(e.target.value)} placeholder="e.g. L..." />
              </div>
              <div>
                <label htmlFor="pan">PAN</label>
                <input id="pan" value={pan} onChange={e=>setPan(e.target.value)} placeholder="e.g. ABCDE1234F" />
              </div>
            </div>
            <div>
              <label htmlFor="sec">Sector *</label>
              <input id="sec" value={sector} onChange={e=>setSector(e.target.value)} placeholder="e.g. Pharmaceuticals" list="sectors" required />
              <datalist id="sectors">{SECTORS.map(s=><option key={s} value={s}/>)}</datalist>
            </div>
            <div>
              <label htmlFor="turnover">Turnover (₹)</label>
              <input id="turnover" type="number" step="any" value={turnover} onChange={e=>setTurnover(e.target.value)} placeholder="e.g. 50000000" />
            </div>
            <div>
              <label htmlFor="prm">Promoters (comma-separated)</label>
              <input id="prm" value={promoters} onChange={e=>setPromoters(e.target.value)} placeholder="e.g. John Doe, Jane Smith" />
              {promoterList.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                  {promoterList.map((p,i) => (
                    <span key={i} style={{ padding: "3px 10px", background: "var(--accent-2)", color: "var(--accent)", border: "1px solid var(--accent-2)", borderRadius: "var(--r-full)", fontSize: 12, fontWeight: 600 }}>
                      👤 {p.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Step 2 */}
        <div>
          <StepChip n={2} label="Loan Details" color="var(--accent)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label htmlFor="ltype">Loan Type</label>
              <select id="ltype" value={loanType} onChange={e=>setLoanType(e.target.value)} className="w-full" style={{ padding: "8px 12px", borderRadius: "var(--r-md)", border: "1px solid var(--line)", background: "var(--card)" }}>
                <option value="Term Loan">Term Loan</option>
                <option value="Working Capital">Working Capital</option>
                <option value="Revolving Facility">Revolving Facility</option>
                <option value="Equipment Finance">Equipment Finance</option>
              </select>
            </div>
            <div>
              <label htmlFor="lamt">Loan Amount (₹)</label>
              <input id="lamt" type="number" step="any" value={loanAmount} onChange={e=>setLoanAmount(e.target.value)} placeholder="e.g. 10000000" />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label htmlFor="ltenure">Tenure (Months)</label>
                <input id="ltenure" type="number" value={tenure} onChange={e=>setTenure(e.target.value)} placeholder="e.g. 36" />
              </div>
              <div>
                <label htmlFor="lrate">Interest Rate (%)</label>
                <input id="lrate" type="number" step="0.01" value={interest} onChange={e=>setInterest(e.target.value)} placeholder="e.g. 12.5" />
              </div>
            </div>
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