import fitz
from typing import Optional


def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text_parts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            text_parts.append(f"[Page {page_num + 1}]\n{text}")
    
    doc.close()
    return "\n\n".join(text_parts)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            text_parts.append(f"[Page {page_num + 1}]\n{text}")
    
    doc.close()
    return "\n\n".join(text_parts)


def get_pdf_metadata(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)
    metadata = {
        "page_count": len(doc),
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
    }
    doc.close()
    return metadata
