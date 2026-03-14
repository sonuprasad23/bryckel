import os
import tempfile
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF


def extract_text_with_ocr(pdf_bytes: bytes, use_gpu: bool = True) -> str:
    """
    Extract text from scanned PDF using OCR.
    Tries multiple methods in order of speed/reliability.
    """
    # First, check if it's actually a text PDF
    text = try_pymupdf_text(pdf_bytes)
    if text and len(text.strip()) > 100:
        print("PDF has extractable text, using PyMuPDF")
        return text
    
    # Try EasyOCR (fast with GPU)
    try:
        print("Attempting EasyOCR extraction...")
        return extract_with_easyocr(pdf_bytes, use_gpu)
    except ImportError:
        print("EasyOCR not available, trying Docling...")
    except Exception as e:
        print(f"EasyOCR failed: {e}, trying Docling...")
    
    # Fallback to Docling
    try:
        return extract_with_docling(pdf_bytes, use_gpu)
    except Exception as e:
        print(f"Docling failed: {e}")
        raise RuntimeError(f"All OCR methods failed. Last error: {e}")


def try_pymupdf_text(pdf_bytes: bytes) -> str:
    """Try to extract text directly with PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            text_parts.append(f"[Page {page_num + 1}]\n{text}")
    
    doc.close()
    return "\n\n".join(text_parts)


def extract_with_easyocr(pdf_bytes: bytes, use_gpu: bool = True) -> str:
    """Extract text using EasyOCR - fast with CUDA support."""
    import easyocr
    import numpy as np
    from PIL import Image
    import io
    
    # Check CUDA availability
    import torch
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    print(f"EasyOCR using device: {device}")
    
    # Initialize reader (cached after first call)
    reader = easyocr.Reader(['en'], gpu=(device == "cuda"))
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    total_pages = len(doc)
    
    for page_num in range(total_pages):
        print(f"OCR processing page {page_num + 1}/{total_pages}...")
        page = doc[page_num]
        
        # Render page to image (150 DPI for balance of speed/quality)
        mat = fitz.Matrix(150/72, 150/72)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to numpy array
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        img_np = np.array(img)
        
        # Run OCR
        results = reader.readtext(img_np, detail=0, paragraph=True)
        page_text = "\n".join(results)
        
        if page_text.strip():
            text_parts.append(f"[Page {page_num + 1}]\n{page_text}")
    
    doc.close()
    return "\n\n".join(text_parts)


def extract_with_docling(pdf_bytes: bytes, use_gpu: bool = True) -> str:
    """Extract text using Docling OCR."""
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import PdfFormatOption
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        tmp_file.write(pdf_bytes)
        tmp_path = tmp_file.name
    
    try:
        # Simpler config to avoid memory issues
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = False  # Disable for speed
        
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        result = converter.convert(tmp_path)
        return result.document.export_to_markdown()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


# Keep backward compatibility
def extract_text_with_docling_bytes(pdf_bytes: bytes) -> str:
    """Backward compatible function."""
    return extract_text_with_ocr(pdf_bytes, use_gpu=True)


def save_markdown(content: str, output_path: str) -> None:
    """Save extracted content as markdown."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
