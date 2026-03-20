"use client";

import { useMemo, useRef, useState } from "react";
import type { UploadedFile } from "@/lib/api";

type Props = {
  uploadedFiles: UploadedFile[]; onUpload: (files: File[]) => Promise<void>;
  loading: boolean; error: string | null; success: string | null;
};

export default function FileUpload({ uploadedFiles, onUpload, loading, error, success }: Props) {
  const [selected, setSelected] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const names = useMemo(() => selected.map(f => f.name), [selected]);

  async function submit() {
    if (!selected.length) return;
    await onUpload(selected);
    setSelected([]);
  }

  return (
    <div className="card card-pad">
      <div style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.015em", color: "var(--text)", marginBottom: 4 }}>
          External Documents
        </h3>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>Annual reports, bank statements, legal filings</p>
      </div>

      {/* Drop zone */}
      <div
        className={`drop-zone${dragging ? " drag-over" : ""}${selected.length > 0 ? " has-files" : ""}`}
        style={{ marginBottom: 16 }}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); setSelected(Array.from(e.dataTransfer.files)); }}
      >
        <div style={{ fontSize: 32, marginBottom: 10, opacity: selected.length > 0 ? 1 : 0.4 }}>
          {selected.length > 0 ? "✅" : dragging ? "📂" : "📁"}
        </div>
        <div style={{ fontSize: 14, color: selected.length > 0 ? "var(--success)" : "var(--text-2)", fontWeight: 600 }}>
          {selected.length > 0 ? `${selected.length} file${selected.length > 1 ? "s" : ""} ready` : "Click or drag & drop files here"}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>PDF, DOCX, XLSX, CSV supported</div>
        <input ref={inputRef} type="file" multiple style={{ display: "none" }} onChange={e => setSelected(Array.from(e.target.files ?? []))} />
      </div>

      {names.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
          {names.map((n,i) => (
            <span key={i} style={{ padding: "3px 10px", background: "var(--success-2)", color: "var(--success)", border: "1px solid var(--success-3)", borderRadius: "var(--r-full)", fontSize: 12, fontWeight: 600 }}>
              📄 {n}
            </span>
          ))}
        </div>
      )}

      {error   && <div className="msg-error"   style={{ marginBottom: 12 }}>{error}</div>}
      {success && <div className="msg-success" style={{ marginBottom: 12 }}>{success}</div>}

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 24 }}>
        <button className="btn btn-primary" disabled={loading || !selected.length} onClick={submit}>
          {loading ? <><span className="spinner" /> Uploading…</> : `Upload ${selected.length > 0 ? selected.length + " " : ""}File${selected.length !== 1 ? "s" : ""}`}
        </button>
      </div>

      {/* Library */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-3)" }}>Document Library</span>
          {uploadedFiles.length > 0 && (
            <span style={{ padding: "2px 9px", background: "var(--primary-2)", color: "var(--primary)", border: "1px solid var(--primary-3)", borderRadius: "var(--r-full)", fontSize: 12, fontWeight: 700 }}>
              {uploadedFiles.length}
            </span>
          )}
        </div>
        {uploadedFiles.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--text-3)", textAlign: "center", padding: "16px 0" }}>No documents uploaded yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <tbody>
                {uploadedFiles.map(f => (
                  <tr key={`${f.file_name}-${f.file_path}`}>
                    <td style={{ fontWeight: 600, color: "var(--text)", fontSize: 13 }}>📄 {f.file_name}</td>
                    <td>
                      <span style={{ padding: "2px 8px", background: "var(--bg-surface)", color: "var(--text-3)", borderRadius: "var(--r-sm)", fontSize: 11, fontWeight: 600, border: "1px solid var(--line)" }}>
                        {f.doc_type || "Generic"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}