"""
Document parsing: text extraction from PDFs and text files, OCR fallback for scanned PDFs, chunking.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

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
        parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning("pypdf extraction failed for %s: %s", path, e)
        return ""


def _extract_text_pdfplumber(path: Path) -> str:
    try:
        import pdfplumber

        parts = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                parts.append(t)
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning("pdfplumber extraction failed for %s: %s", path, e)
        return ""


def _extract_text_ocr(path: Path) -> str:
    try:
        import pdf2image
        import pytesseract

        images = pdf2image.convert_from_path(str(path), dpi=150)
        parts = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="eng")
            parts.append(text or "")
        return "\n\n".join(parts)
    except ImportError as e:
        logger.warning("OCR dependencies missing: %s", e)
        return ""
    except Exception as e:
        logger.warning("OCR failed for %s: %s", path, e)
        return ""


def extract_text_from_pdf(path: Path) -> tuple[str, bool]:
    """
    Extract text from PDF. Try pdfplumber first (better tables), then pypdf, then OCR if scant text.
    Returns (text, used_ocr).
    """
    text = _extract_text_pdfplumber(path)
    if not text.strip():
        text = _extract_text_pypdf(path)
    if len(text.strip()) < MIN_TEXT_FOR_OCR:
        ocr_text = _extract_text_ocr(path)
        if ocr_text.strip():
            text = ocr_text
            return (text, True)
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
    if suf == ".pdf":
        return extract_text_from_pdf(path)
    return ("", False)


def infer_doc_type(file_name: str, file_path: str) -> str:
    """Infer document type from filename."""
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
    """
    chunks_out: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, meta in enumerate(file_metadata):
        file_path = meta.get("file_path") or meta.get("file_name")
        file_name = meta.get("file_name", str(file_path))
        doc_type = meta.get("doc_type") or infer_doc_type(file_name, str(file_path or ""))

        path = resolve_path(str(file_path) if file_path else None, case_id)
        if not path or not path.exists():
            errors.append(f"File not found: {file_name} ({file_path})")
            continue

        text, used_ocr = extract_text_from_file(path)
        if not text.strip():
            errors.append(f"No text extracted from {file_name}")
            continue

        text_chunks = chunk_text(text)
        for j, ch in enumerate(text_chunks):
            chunk_id = f"doc{i}_chunk{j}"
            chunks_out.append({
                "chunk_id": chunk_id,
                "text": ch,
                "file_name": file_name,
                "file_path": str(path),
                "doc_type": doc_type,
                "page_ref": f"p{1 + j // 3}",
                "used_ocr": used_ocr,
            })
    return chunks_out, errors
