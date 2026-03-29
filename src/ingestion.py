"""Deck ingestion: PDF parsing and text extraction."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: str) -> tuple[str, list[str]]:
    """Extract text from a PDF file.

    Returns:
        (full_text, page_texts) where page_texts[i] is the text of page i.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Deck file not found: {pdf_path}")

    if path.suffix.lower() != ".pdf":
        # For non-PDF files, try reading as plain text
        text = path.read_text(encoding="utf-8", errors="replace")
        return text, [text]

    doc = fitz.open(str(path))
    page_texts = []
    for page in doc:
        page_texts.append(page.get_text("text"))
    doc.close()

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(page_texts)
    return full_text, page_texts


def extract_metadata(pdf_path: str) -> dict:
    """Extract PDF metadata (title, author, page count, etc.)."""
    path = Path(pdf_path)
    if not path.exists() or path.suffix.lower() != ".pdf":
        return {"page_count": 0, "title": None, "author": None}

    doc = fitz.open(str(path))
    meta = doc.metadata or {}
    info = {
        "page_count": len(doc),
        "title": meta.get("title") or None,
        "author": meta.get("author") or None,
        "creation_date": meta.get("creationDate") or None,
    }
    doc.close()
    return info
