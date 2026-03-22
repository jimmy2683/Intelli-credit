"use client";

import React, { useState } from "react";
import { Copy, Plus, Save, Settings, Trash2, Loader2, RefreshCw } from "lucide-react";

export type SchemaField = {
  key: string;
  type: "number" | "string" | "boolean" | "array" | "object";
  description: string;
};

// A fallback standard schema
const DEFAULT_SCHEMA: SchemaField[] = [
  { key: "revenue", type: "number", description: "Total revenue or sales" },
  { key: "ebitda", type: "number", description: "Earnings before interest, taxes, depreciation, and amortization" },
  { key: "pat", type: "number", description: "Profit after tax" },
  { key: "total_debt", type: "number", description: "Total outstanding debt/borrowings" },
  { key: "net_worth", type: "number", description: "Total equity or net worth" },
  { key: "current_ratio", type: "number", description: "Current assets divided by current liabilities" },
];

type Props = {
  initialSchema?: Record<string, any>;
  onSave: (schema: Record<string, any>) => Promise<void>;
  loading?: boolean;
};

function recordToFields(record?: Record<string, any>): SchemaField[] {
  if (!record) return DEFAULT_SCHEMA;
  // If record was somehow saved as an array
  if (Array.isArray(record)) {
    if (record.length === 0) return DEFAULT_SCHEMA;
    if (record[0] && typeof record[0] === "object" && "key" in record[0]) {
      return record as SchemaField[];
    }
  }
  // Standard object unpacking
  if (Object.keys(record).length === 0) return DEFAULT_SCHEMA;
  return Object.entries(record).map(([k, v]) => ({
    key: k,
    type: (v?.type || "number") as any,
    description: v?.description || ""
  }));
}

function fieldsToRecord(fields: SchemaField[]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const f of fields) {
    if (f.key.trim()) {
      out[f.key.trim()] = { type: f.type, description: f.description };
    }
  }
  return out;
}

export default function SchemaBuilder({ initialSchema, onSave, loading }: Props) {
  const [fields, setFields] = useState<SchemaField[]>(recordToFields(initialSchema));
  const [isEditing, setIsEditing] = useState(false);

  React.useEffect(() => {
    setFields(recordToFields(initialSchema));
  }, [initialSchema]);

  const addField = () => {
    setFields([...fields, { key: "", type: "number", description: "" }]);
  };

  const removeField = (idx: number) => {
    setFields(fields.filter((_, i) => i !== idx));
  };

  const updateField = (idx: number, prop: keyof SchemaField, val: string) => {
    const next = [...fields];
    next[idx] = { ...next[idx], [prop]: val };
    setFields(next);
  };

  const handleSave = async () => {
    await onSave(fieldsToRecord(fields));
    setIsEditing(false);
  };

  const handleReset = () => {
    setFields(DEFAULT_SCHEMA);
  };

  if (!isEditing) {
    return (
      <div className="card card-pad" style={{ animation: "fadeUp 0.3s ease both" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
          <div>
            <h3 style={{ fontSize: 17, fontWeight: 700, color: "var(--text)", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
              <Settings size={18} /> Extraction Schema
            </h3>
            <p style={{ fontSize: 13, color: "var(--text-3)" }}>
              {fields.length} data points configured for AI extraction.
            </p>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setIsEditing(true)}>
            Edit Schema
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {fields.map((f, i) => (
            <span key={f.key || i} style={{ padding: "4px 10px", background: "var(--bg-surface)", border: "1px solid var(--line)", borderRadius: "var(--r-sm)", fontSize: 12, fontWeight: 600, color: "var(--text-2)", display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "var(--primary)" }}>Aa</span> {f.key || "Untitled"}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    // {/* Notice 'both' is now appended to the animation style below */}
    <div className="card glass" style={{ padding: "24px", borderRadius: "var(--r-xl)", animation: "slideInDown 0.3s ease both" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", marginBottom: 4 }}>Dynamic Schema Builder</h3>
          <p style={{ fontSize: 13, color: "var(--text-3)" }}>Define exactly what financial data points the AI should extract from the documents.</p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={handleReset} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <RefreshCw size={14} /> Reset to Default
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24, maxHeight: "400px", overflowY: "auto", paddingRight: 8 }}>
        {fields.map((f, i) => (
          <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "12px", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: "var(--r-md)" }}>
            <div style={{ flex: "0 0 160px" }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", marginBottom: 4, display: "block" }}>Key</label>
              <input 
                className="input" 
                value={f.key} 
                onChange={e => updateField(i, "key", e.target.value)} 
                placeholder="e.g. revenue" 
                style={{ width: "100%" }}
              />
            </div>
            
            <div style={{ flex: "0 0 120px" }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", marginBottom: 4, display: "block" }}>Type</label>
              <select 
                className="input" 
                value={f.type} 
                onChange={e => updateField(i, "type", e.target.value as any)} 
                style={{ width: "100%", padding: "9px" }}
              >
                <option value="number">Number</option>
                <option value="string">String</option>
                <option value="boolean">Boolean</option>
                <option value="array">Array</option>
                <option value="object">Object</option>
              </select>
            </div>

            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)", textTransform: "uppercase", marginBottom: 4, display: "block" }}>Description (Prompt logic)</label>
              <input 
                className="input" 
                value={f.description} 
                onChange={e => updateField(i, "description", e.target.value)} 
                placeholder="How should the AI find or calculate this?" 
                style={{ width: "100%" }}
              />
            </div>

            <button 
              type="button"
              onClick={() => removeField(i)} 
              style={{ padding: "8px", background: "transparent", border: "none", color: "var(--text-3)", cursor: "pointer", marginTop: "20px" }}
              title="Remove Field"
            >
              <Trash2 size={18} />
            </button>
          </div>
        ))}
        
        <button 
          type="button"
          onClick={addField} 
          style={{ padding: "12px", background: "var(--bg-inset)", border: "1px dashed var(--line-subtle)", borderRadius: "var(--r-md)", color: "var(--text-2)", fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, cursor: "pointer" }}
        >
          <Plus size={16} /> Add Field
        </button>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
        <button type="button" className="btn btn-secondary" onClick={() => setIsEditing(false)} disabled={loading}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary" onClick={handleSave} disabled={loading} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          Save Schema
        </button>
      </div>
    </div>
  );
}