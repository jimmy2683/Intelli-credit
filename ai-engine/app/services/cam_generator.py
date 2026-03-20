"""
CAM DOCX generator: produces a professional Credit Appraisal Memo as a .docx file.

Sections:
1. Executive Summary
2. Borrower Profile
3. Business Overview
4. Financial Analysis (table)
5. Risk Analysis
6. Five Cs of Credit
7. Red Flags
8. Final Recommendation
9. Evidence Appendix
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "../data"))

# Try importing python-docx; graceful fallback to markdown if not available
try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    logger.warning("python-docx not installed; CAM will be generated as markdown fallback.")


def _fmt_inr(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1e7:
        return f"₹{value / 1e7:,.2f} Cr"
    if abs(value) >= 1e5:
        return f"₹{value / 1e5:,.2f} L"
    return f"₹{value:,.0f}"


def _get_v(facts: dict, key: str) -> Any:
    v = facts.get(key)
    if isinstance(v, dict):
        return v.get("value")
    return v


def _severity_badge(sev: str) -> str:
    return {"critical": "🔴 CRITICAL", "high": "🟠 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"}.get(sev, sev.upper())


# ---------------------------------------------------------------------------
# DOCX generation
# ---------------------------------------------------------------------------

def _add_styled_heading(doc: "Document", text: str, level: int = 1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1A, 0x23, 0x7E)  # Dark navy


def _add_kv_line(doc: "Document", label: str, value: str):
    p = doc.add_paragraph()
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    run_label.font.size = Pt(10)
    run_val = p.add_run(str(value))
    run_val.font.size = Pt(10)


def _add_financial_table(doc: "Document", facts: dict):
    rows_data = [
        ("Revenue", _fmt_inr(_get_v(facts, "revenue"))),
        ("EBITDA", _fmt_inr(_get_v(facts, "EBITDA"))),
        ("PAT (Profit After Tax)", _fmt_inr(_get_v(facts, "PAT"))),
        ("Total Debt", _fmt_inr(_get_v(facts, "total_debt"))),
        ("Working Capital", _fmt_inr(_get_v(facts, "working_capital"))),
        ("Current Ratio", f"{_get_v(facts, 'current_ratio') or 'N/A'}"),
        ("DSCR", f"{_get_v(facts, 'dscr') or 'N/A'}"),
    ]
    table = doc.add_table(rows=len(rows_data) + 1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Light Grid Accent 1"

    hdr = table.rows[0]
    hdr.cells[0].text = "Metric"
    hdr.cells[1].text = "Value"
    for cell in hdr.cells:
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True

    for i, (metric, val) in enumerate(rows_data, 1):
        table.rows[i].cells[0].text = metric
        table.rows[i].cells[1].text = str(val)


def generate_cam_docx(
    case_id: str,
    company_details: dict | None,
    extracted_facts: dict,
    risk_flags: list[dict],
    score_result: dict,
    officer_notes: str | None = None,
) -> str:
    """Generate a DOCX CAM file. Returns the file path."""

    evidence_dir = DATA_ROOT / "evidence" / case_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if not HAS_DOCX:
        return _generate_cam_markdown(
            case_id, company_details, extracted_facts, risk_flags, score_result, officer_notes, evidence_dir
        )

    doc = Document()

    # --- Style defaults ---
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    cd = company_details or {}
    company = cd.get("company_name", "Unknown Company")
    sector = cd.get("sector", "N/A")
    promoters = ", ".join(cd.get("promoter_names", [])) or "N/A"
    cin = cd.get("cin_optional", "N/A")

    decision = score_result.get("cam_decision", score_result.get("decision", "manual_review"))
    overall_score = score_result.get("overall_score", 0)
    rec_limit = score_result.get("recommended_limit", 0)
    rec_roi = score_result.get("recommended_roi", 0)
    reasons = score_result.get("reasons", [])
    breakdown = score_result.get("score_breakdown", {})

    # ── Title ──
    title = doc.add_heading("Credit Appraisal Memorandum", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = RGBColor(0x1A, 0x23, 0x7E)
    doc.add_paragraph(f"Case ID: {case_id} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("")

    # ── 1. Executive Summary ──
    _add_styled_heading(doc, "1. Executive Summary", 1)
    decision_map = {"approve": "APPROVE", "approve_with_conditions": "APPROVE WITH CONDITIONS", "decline": "DECLINE", "manual_review": "MANUAL REVIEW"}
    _add_kv_line(doc, "Decision", decision_map.get(decision, decision.upper()))
    _add_kv_line(doc, "Overall Score", f"{overall_score}/100")
    _add_kv_line(doc, "Recommended Limit", _fmt_inr(rec_limit))
    _add_kv_line(doc, "Recommended ROI", f"{rec_roi}%")

    if score_result.get("hard_override_applied"):
        p = doc.add_paragraph()
        run = p.add_run(f"⚠️ HARD OVERRIDE: {score_result.get('hard_override_reason', 'Red flag triggered')}")
        run.bold = True
        run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)

    explanation = score_result.get("decision_explanation", "")
    if explanation:
        doc.add_paragraph(explanation)

    # ── 2. Borrower Profile ──
    _add_styled_heading(doc, "2. Borrower Profile", 1)
    _add_kv_line(doc, "Company Name", company)
    _add_kv_line(doc, "CIN", cin)
    _add_kv_line(doc, "Sector", sector)
    _add_kv_line(doc, "Promoter(s)", promoters)

    # ── 3. Business Overview ──
    _add_styled_heading(doc, "3. Business Overview", 1)
    doc.add_paragraph(
        f"{company} operates in the {sector} sector. "
        f"This appraisal is based on uploaded financial statements, regulatory filings, "
        f"and secondary research. The company's financial profile and risk indicators "
        f"are summarized below."
    )

    # ── 4. Financial Analysis ──
    _add_styled_heading(doc, "4. Financial Analysis", 1)
    _add_financial_table(doc, extracted_facts)
    doc.add_paragraph("")

    # Score breakdown table
    if breakdown:
        doc.add_heading("Score Breakdown", level=2)
        tbl = doc.add_table(rows=len(breakdown) + 1, cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.style = "Light Grid Accent 1"
        tbl.rows[0].cells[0].text = "Category"
        tbl.rows[0].cells[1].text = "Score"
        for cell in tbl.rows[0].cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.bold = True
        for i, (cat, val) in enumerate(breakdown.items(), 1):
            tbl.rows[i].cells[0].text = cat.replace("_", " ").title()
            tbl.rows[i].cells[1].text = str(val)

    # ── 5. Risk Analysis ──
    _add_styled_heading(doc, "5. Risk Analysis", 1)
    if risk_flags:
        for flag in risk_flags:
            sev = flag.get("severity", "medium")
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(f"[{_severity_badge(sev)}] ")
            run.bold = True
            p.add_run(f"{flag.get('flag_type', 'unknown')}: {flag.get('description', '')}")
            refs = flag.get("evidence_refs", [])
            if refs:
                p.add_run(f" (Refs: {', '.join(refs[:3])})")
    else:
        doc.add_paragraph("No significant risk flags identified.")

    # ── 6. Five Cs of Credit ──
    _add_styled_heading(doc, "6. Five Cs of Credit", 1)
    five_cs = _compute_five_cs(extracted_facts, risk_flags, score_result, cd)
    for c_name, c_assessment in five_cs.items():
        doc.add_heading(c_name, level=2)
        doc.add_paragraph(c_assessment)

    # ── 7. Red Flags ──
    _add_styled_heading(doc, "7. Red Flags", 1)
    severe = [f for f in risk_flags if f.get("severity") in ("high", "critical")]
    if severe:
        for flag in severe:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(f"[{flag.get('severity', '').upper()}] ")
            run.bold = True
            run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)
            p.add_run(flag.get("description", ""))
    else:
        doc.add_paragraph("No severe red flags identified.")

    if score_result.get("hard_override_applied"):
        p = doc.add_paragraph()
        run = p.add_run(f"Hard Override Active: {score_result.get('hard_override_reason', '')}")
        run.bold = True
        run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)

    # ── 8. Final Recommendation ──
    _add_styled_heading(doc, "8. Final Recommendation", 1)
    _add_kv_line(doc, "Decision", decision_map.get(decision, decision.upper()))
    _add_kv_line(doc, "Overall Score", f"{overall_score}/100")
    _add_kv_line(doc, "Recommended Exposure Limit", _fmt_inr(rec_limit))
    _add_kv_line(doc, "Recommended ROI", f"{rec_roi}%")

    if reasons:
        doc.add_heading("Key Reasons", level=2)
        for r in reasons[:8]:
            doc.add_paragraph(r, style="List Bullet")

    if officer_notes:
        doc.add_heading("Officer Notes", level=2)
        doc.add_paragraph(officer_notes)

    # ── 9. Evidence Appendix ──
    _add_styled_heading(doc, "9. Evidence Appendix", 1)
    doc.add_paragraph("The following evidence sources were referenced in this appraisal:")
    entities = extracted_facts.get("extracted_entities", [])
    if isinstance(entities, list):
        for ent in entities[:10]:
            if isinstance(ent, dict):
                doc.add_paragraph(
                    f"• {ent.get('name', 'N/A')} ({ent.get('type', 'N/A')}) — {ent.get('role', '')} [Source: {ent.get('source_ref', 'N/A')}]"
                )
    doc_sources = extracted_facts.get("document_sources", [])
    if isinstance(doc_sources, list):
        for ds in doc_sources[:10]:
            if isinstance(ds, dict):
                doc.add_paragraph(
                    f"• {ds.get('file_name', 'N/A')} — Section: {ds.get('section', 'N/A')}, Page: {ds.get('page_ref', 'N/A')}"
                )

    # Save
    docx_path = evidence_dir / "cam.docx"
    doc.save(str(docx_path))
    logger.info("CAM DOCX generated: %s", docx_path)
    return str(docx_path)


# ---------------------------------------------------------------------------
# Five Cs computation helper
# ---------------------------------------------------------------------------

def _compute_five_cs(facts: dict, flags: list[dict], score: dict, company: dict) -> dict[str, str]:
    breakdown = score.get("score_breakdown", {})
    revenue = _get_v(facts, "revenue")
    dscr = _get_v(facts, "dscr")
    cr = _get_v(facts, "current_ratio")

    return {
        "Character": (
            f"Promoter(s): {', '.join(company.get('promoter_names', [])) or 'N/A'}. "
            f"Governance score: {breakdown.get('governance', 'N/A')}/100. "
            + ("Governance concerns flagged." if any(f.get("flag_type") in ("governance_instability", "high_related_party_dependency") for f in flags) else "No major governance concerns.")
        ),
        "Capacity": (
            f"DSCR: {dscr or 'N/A'}. Cash flow score: {breakdown.get('cash_flow', 'N/A')}/100. "
            + (f"DSCR is {'adequate' if (dscr and dscr >= 1.0) else 'weak or unavailable'} for debt servicing." )
        ),
        "Capital": (
            f"Revenue: {_fmt_inr(revenue)}. Financial strength score: {breakdown.get('financial_strength', 'N/A')}/100. "
            f"Working capital: {_fmt_inr(_get_v(facts, 'working_capital'))}."
        ),
        "Collateral": (
            "Collateral assessment based on uploaded documentation. "
            "Tangible security details should be verified from sanction letters and valuation reports."
        ),
        "Conditions": (
            f"Sector: {company.get('sector', 'N/A')}. Current ratio: {cr or 'N/A'}. "
            f"Secondary research score: {breakdown.get('secondary_research', 'N/A')}/100. "
            + ("Regulatory/sector headwinds noted." if any(f.get("flag_type") in ("regulatory_risk", "sector_headwind") for f in flags) else "No sector-level concerns flagged.")
        ),
    }


# ---------------------------------------------------------------------------
# Markdown fallback when python-docx is not installed
# ---------------------------------------------------------------------------

def _generate_cam_markdown(
    case_id: str,
    company_details: dict | None,
    extracted_facts: dict,
    risk_flags: list[dict],
    score_result: dict,
    officer_notes: str | None,
    evidence_dir: Path,
) -> str:
    cd = company_details or {}
    company = cd.get("company_name", "Unknown Company")
    decision = score_result.get("cam_decision", score_result.get("decision", "manual_review"))
    overall_score = score_result.get("overall_score", 0)
    rec_limit = score_result.get("recommended_limit", 0)
    rec_roi = score_result.get("recommended_roi", 0)
    reasons = score_result.get("reasons", [])
    breakdown = score_result.get("score_breakdown", {})

    lines = [
        f"# Credit Appraisal Memorandum",
        f"**Case ID:** {case_id} | **Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## 1. Executive Summary",
        f"- **Decision:** {decision.upper()}",
        f"- **Overall Score:** {overall_score}/100",
        f"- **Recommended Limit:** {_fmt_inr(rec_limit)}",
        f"- **Recommended ROI:** {rec_roi}%",
        "",
        "## 2. Borrower Profile",
        f"- **Company:** {company}",
        f"- **CIN:** {cd.get('cin_optional', 'N/A')}",
        f"- **Sector:** {cd.get('sector', 'N/A')}",
        f"- **Promoters:** {', '.join(cd.get('promoter_names', [])) or 'N/A'}",
        "",
        "## 3. Financial Analysis",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Revenue | {_fmt_inr(_get_v(extracted_facts, 'revenue'))} |",
        f"| EBITDA | {_fmt_inr(_get_v(extracted_facts, 'EBITDA'))} |",
        f"| PAT | {_fmt_inr(_get_v(extracted_facts, 'PAT'))} |",
        f"| Total Debt | {_fmt_inr(_get_v(extracted_facts, 'total_debt'))} |",
        f"| Current Ratio | {_get_v(extracted_facts, 'current_ratio') or 'N/A'} |",
        f"| DSCR | {_get_v(extracted_facts, 'dscr') or 'N/A'} |",
        "",
        "## 4. Risk Flags",
    ]
    for flag in risk_flags:
        lines.append(f"- **[{flag.get('severity', 'N/A').upper()}]** {flag.get('flag_type', '')}: {flag.get('description', '')}")
    if not risk_flags:
        lines.append("- No significant risk flags.")

    lines.extend([
        "",
        "## 5. Score Breakdown",
        "| Category | Score |",
        "|----------|-------|",
    ])
    for cat, val in breakdown.items():
        lines.append(f"| {cat.replace('_', ' ').title()} | {val} |")

    lines.extend([
        "",
        "## 6. Recommendation",
        f"**Decision:** {decision.upper()} | **Score:** {overall_score}/100",
    ])
    if reasons:
        lines.append("### Key Reasons")
        for r in reasons[:8]:
            lines.append(f"- {r}")

    md_path = evidence_dir / "cam.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("CAM markdown generated (python-docx fallback): %s", md_path)
    return str(md_path)
