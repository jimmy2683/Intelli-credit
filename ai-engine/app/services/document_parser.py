"""
Document parsing: text extraction from PDFs and text files, OCR fallback for scanned PDFs, chunking.

FIX: The original code mutated chunk dicts after appending them to chunks_out via
current_doc_chunks references — this worked by accident (same objects) but was
fragile and hard to reason about. Now the classification step is explicit and the
mutation is clearly documented.

FIX: `print("file_meta_list", ...)` replaced with `logger.info(...)`.
"""
from __future__ import annotations

import logging
import os
import re
import csv
from pathlib import Path
from typing import Any
from .s3_service import download_from_s3
from .mistral_service import call_mistral
from .ai_extraction import extract_json_safely

logger = logging.getLogger(__name__)

DATA_ROOT = os.environ.get("DATA_ROOT", "../data")
MIN_TEXT_FOR_OCR = 50
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

SUPPORTED_DOC_TYPES = [
    "annual_report",
    "financial_statement",
    "bank_statement",
    "gst_summary",
    "sanction_letter",
    "board_note",
    "legal_notice",
    "shareholding_pattern",
    "borrowing_profile",
    "portfolio_cuts",
    "alm",
]


def resolve_path(file_path: str | None, case_id: str | None) -> Path | None:
    """Resolve file path relative to DATA_ROOT if needed."""
    if not file_path:
        return None
    p = Path(file_path)
    if p.is_absolute() and p.exists():
        return p
    root = Path(DATA_ROOT)
    candidates = [
        root / file_path.lstrip("./"),
        root / file_path.replace("./", ""),
        root / "uploads" / (case_id or "") / Path(file_path).name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _extract_text_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        # Limit to the first 20 pages
        pages_to_read = reader.pages[:20]
        return "\n\n".join(page.extract_text() or "" for page in pages_to_read)
    except Exception as e:
        logger.warning("pypdf extraction failed for %s: %s", path, e)
        return ""


def _extract_text_pdfplumber(path: Path) -> str:
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(path) as pdf:
            # Limit to the first 20 pages
            for page in pdf.pages[:20]:
                parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning("pdfplumber extraction failed for %s: %s", path, e)
        return ""


def _extract_text_ocr(path: Path) -> str:
    try:
        import pdf2image
        import pytesseract
        # Use last_page=20 to prevent converting the entire PDF into images in memory
        images = pdf2image.convert_from_path(str(path), dpi=150, last_page=20)
        return "\n\n".join(pytesseract.image_to_string(img, lang="eng") or "" for img in images)
    except ImportError as e:
        logger.warning("OCR dependencies missing: %s", e)
        return ""
    except Exception as e:
        logger.warning("OCR failed for %s: %s", path, e)
        return ""

def extract_text_from_pdf(path: Path) -> tuple[str, bool]:
    """
    Extract text from PDF. Try pdfplumber first (better tables), then pypdf, then OCR.
    Returns (text, used_ocr).
    """
    text = _extract_text_pdfplumber(path)
    if not text.strip():
        text = _extract_text_pypdf(path)
    if len(text.strip()) < MIN_TEXT_FOR_OCR:
        ocr_text = _extract_text_ocr(path)
        if ocr_text.strip():
            return (ocr_text, True)
    return (text, False)


def extract_text_from_file(path: Path) -> tuple[str, bool]:
    """Extract text from file based on extension."""
    suf = path.suffix.lower()
    if suf == ".txt":
        try:
            return (path.read_text(encoding="utf-8", errors="replace"), False)
        except Exception as e:
            logger.warning("Failed to read txt %s: %s", path, e)
            return ("", False)
    elif suf == ".csv":
        return (_extract_text_csv(path), False)
    elif suf == ".pdf":
        return extract_text_from_pdf(path)
    logger.warning("Unsupported file extension '%s' for %s", suf, path)
    return ("", False)


CLASSIFY_PROMPT = """
You are a financial document classification expert. Determine the document type from the provided filename and content chunks.

Filename: {file_name}

Valid Types:
- annual_report
- financial_statement (standalone P&L, Balance Sheet)
- bank_statement
- gst_summary
- sanction_letter
- board_note
- legal_notice
- shareholding_pattern
- borrowing_profile
- portfolio_cuts
- alm
- unknown

Criteria:
Look for specific headers, table titles, or standard vocabulary
(e.g., "Maturity Profile" -> alm, "Sanction" -> sanction_letter, "Directors Report" -> annual_report,
"Shareholding" -> shareholding_pattern, "Borrowing" -> borrowing_profile, "GNPA/NNPA" -> portfolio_cuts).

Output JSON:
{{
  "predicted_type": "string (must be from Valid Types)",
  "classification_confidence": 0.0,
  "reason": "short explanation"
}}

--- TEXT CHUNKS ---
{chunks_text}

Return ONLY valid JSON.
"""


def classify_document_by_content(chunks: list[dict[str, Any]], file_name: str) -> dict[str, Any]:
    """Classify document using LLM on the first few chunks."""
    if not chunks:
        return {
            "predicted_type": infer_doc_type(file_name, ""),
            "classification_confidence": 0.4,
            "status": "requires_confirmation",
        }

    preview = "\n\n".join([str(c.get("text", ""))[:800] for c in chunks[:5]])
    prompt = CLASSIFY_PROMPT.format(file_name=file_name, chunks_text=preview)
    try:
        resp = call_mistral(prompt, response_format={"type": "json_object"})
        result = extract_json_safely(resp)
        conf = result.get("classification_confidence", 0.0)
        result["status"] = "confirmed" if conf >= 0.85 else "requires_confirmation"
        return result
    except Exception as e:
        logger.warning("Classification failed for %s: %s", file_name, e)
        return {
            "predicted_type": infer_doc_type(file_name, ""),
            "classification_confidence": 0.1,
            "status": "requires_confirmation",
        }


def infer_doc_type(file_name: str, file_path: str) -> str:
    """Fallback: Infer document type from filename."""
    name = (file_name or file_path or "").lower()
    if "annual" in name or "ar " in name or "annual_report" in name:
        return "annual_report"
    if "financial" in name or "fs " in name or "p&l" in name or "profit" in name or "balance" in name:
        return "financial_statement"
    if "bank" in name or "statement" in name or "bs " in name:
        return "bank_statement"
    if "gst" in name or "tax" in name:
        return "gst_summary"
    if "sanction" in name or "facility" in name or "limit" in name:
        return "sanction_letter"
    if "board" in name or "minutes" in name or "mou" in name:
        return "board_note"
    if "legal" in name or "notice" in name or "suit" in name or "litigation" in name:
        return "legal_notice"
    if "shareholding" in name or "pattern" in name:
        return "shareholding_pattern"
    if "borrowing" in name or "borrow" in name:
        return "borrowing_profile"
    if "portfolio" in name or "gnpa" in name or "nnpa" in name:
        return "portfolio_cuts"
    if "alm" in name or "maturity" in name or "asset.liab" in name:
        return "alm"
    return "unknown"


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if not text or not text.strip():
        return []
    text = text.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap if end < len(text) else len(text)
    return chunks


def parse_documents(
    file_metadata: list[dict[str, Any]],
    case_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Parse uploaded documents: extract text, chunk, attach source refs.
    Returns (parsed_chunks, errors).

    FIX: Added explicit classification update loop that is clearly documented.
         The mutation of chunk dicts in-place (via current_doc_chunks) works because
         chunks_out holds references to the same objects. This is now intentional
         rather than accidental.
    """
    chunks_out: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, meta in enumerate(file_metadata):
        file_path_raw = meta.get("file_path") or meta.get("file_name")
        file_name = meta.get("file_name", str(file_path_raw))
        doc_type = meta.get("doc_type") or infer_doc_type(file_name, str(file_path_raw or ""))

        path: Path | None = None
        if file_path_raw and str(file_path_raw).startswith("s3://"):
            local_path_str = download_from_s3(str(file_path_raw))
            path = Path(local_path_str)
        else:
            path = resolve_path(str(file_path_raw) if file_path_raw else None, case_id)

        if path is None or not path.exists():
            errors.append(f"File not found: {file_name} ({file_path_raw})")
            continue

        text, used_ocr = extract_text_from_file(path)
        if not text.strip():
            errors.append(f"No text extracted from {file_name}")
            continue

        text_chunks = chunk_text(text)

        # Build chunk dicts for this document
        current_doc_chunks: list[dict[str, Any]] = []
        for j, ch in enumerate(text_chunks):
            chunk_id = f"doc{i}_chunk{j}"
            ch_dict: dict[str, Any] = {
                "chunk_id": chunk_id,
                "text": ch,
                "file_name": file_name,
                "file_path": str(path),
                "doc_type": doc_type,         # provisional — may be overwritten below
                "page_ref": f"p{1 + j // 3}",
                "used_ocr": used_ocr,
                "classification_confidence": None,
                "classification_status": "pending",
            }
            current_doc_chunks.append(ch_dict)
            chunks_out.append(ch_dict)  # same object reference — mutations below propagate here

        # LLM-based classification (overrides filename-based doc_type when confident)
        classification = classify_document_by_content(current_doc_chunks, file_name)
        predicted_type = classification.get("predicted_type", "unknown")
        predicted_conf = classification.get("classification_confidence", 0.0)

        if predicted_type and predicted_type != "unknown":
            # FIX: Update via the current_doc_chunks references so that chunks_out
            # (which holds the same objects) reflects the improved classification.
            for ch_dict in current_doc_chunks:
                ch_dict["doc_type"] = predicted_type
                ch_dict["classification_confidence"] = predicted_conf
                ch_dict["classification_status"] = classification.get("status", "requires_confirmation")

            logger.info(
                "Classified '%s' as '%s' (confidence=%.2f, status=%s)",
                file_name, predicted_type, predicted_conf, classification.get("status"),
            )
        else:
            logger.warning(
                "Classification inconclusive for '%s' — keeping filename-inferred type '%s'",
                file_name, doc_type,
            )

    return chunks_out, errors


def _extract_text_csv(path: Path) -> str:
    """Extract and format text from a CSV file for better LLM comprehension."""
    try:
        text_parts = []
        with open(path, mode="r", encoding="utf-8", errors="replace") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                text_parts.append(" | ".join(row))
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning("CSV extraction failed for %s: %s", path, e)
        return ""