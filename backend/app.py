import os
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import DATA_DIR
from models import (
    ChatRequest, ChatResponse, LeaseSummary, 
    ProcessRequest, ProcessResponse, SchemaField
)
from pdf_loader import extract_text_from_pdf_bytes
from docling_loader import extract_text_with_docling_bytes
from schema_loader import load_schema
from chunker import chunk_text
from embedding_index import EmbeddingIndex
from extractor import extract_priority_only, extract_remaining_fields
from chat_engine import chat

BACKEND_DIR = Path(__file__).parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

app = FastAPI(title="Lease Document Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
embedding_index = EmbeddingIndex()
lease_summary: Optional[LeaseSummary] = None
schema_fields: list[SchemaField] = []
document_loaded = False
schema_loaded = False
current_filename = ""
extracted_text = ""
pdf_bytes_cache: Optional[bytes] = None

# Background processing state
background_processing = False
background_complete = False
background_error: Optional[str] = None


async def process_remaining_in_background(
    index: EmbeddingIndex,
    schema_fields: Optional[list[SchemaField]],
    priority_fields: list
):
    """Background task to extract remaining schema fields."""
    global lease_summary, background_processing, background_complete, background_error
    
    try:
        print("Background: Starting extraction of remaining fields...")
        background_processing = True
        background_error = None
        
        # Extract remaining fields
        full_summary = await extract_remaining_fields(index, schema_fields, priority_fields)
        
        # Update global lease summary
        lease_summary = full_summary
        
        background_complete = True
        background_processing = False
        print(f"Background: Complete! Extracted {len(full_summary.fields)} total fields")
        
    except Exception as e:
        print(f"Background: Error - {e}")
        background_error = str(e)
        background_processing = False


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handle PDF or CSV file upload."""
    global current_filename, pdf_bytes_cache, schema_fields, schema_loaded
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext == ".pdf":
        try:
            content = await file.read()
            pdf_bytes_cache = content
            current_filename = file.filename
            
            os.makedirs(DATA_DIR, exist_ok=True)
            pdf_path = os.path.join(DATA_DIR, "lease.pdf")
            with open(pdf_path, "wb") as f:
                f.write(content)
            
            return {
                "status": "success",
                "filename": file.filename,
                "file_type": "pdf",
                "size_bytes": len(content),
                "message": "PDF uploaded successfully"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploading PDF: {str(e)}")
    
    elif file_ext == ".csv":
        try:
            content = await file.read()
            os.makedirs(DATA_DIR, exist_ok=True)
            csv_path = os.path.join(DATA_DIR, "schema.csv")
            with open(csv_path, "wb") as f:
                f.write(content)
            
            schema_fields = load_schema(csv_path)
            schema_loaded = True
            
            return {
                "status": "success",
                "filename": file.filename,
                "file_type": "csv",
                "fields_count": len(schema_fields),
                "fields": [{"name": f.display_name, "type": f.field_type} for f in schema_fields[:20]],
                "message": f"Schema loaded with {len(schema_fields)} fields"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading schema: {str(e)}")
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type '{file_ext}'. Allowed: .pdf, .csv"
        )


@app.post("/api/process")
async def process_document(pdf_type: str = Form("text")):
    """
    Process the uploaded PDF - extracts priority fields immediately,
    then processes remaining fields in background.
    """
    global lease_summary, document_loaded, extracted_text, pdf_bytes_cache, schema_fields
    global background_processing, background_complete, background_error
    
    pdf_path = os.path.join(DATA_DIR, "lease.pdf")
    schema_path = os.path.join(DATA_DIR, "schema.csv")
    
    if pdf_bytes_cache is None and not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="No PDF uploaded. Please upload a PDF first.")
    
    # Schema is optional
    if schema_fields or os.path.exists(schema_path):
        if not schema_fields:
            try:
                schema_fields = load_schema(schema_path)
            except:
                pass
    
    try:
        # Reset background state
        background_processing = False
        background_complete = False
        background_error = None
        
        # Load PDF if not cached
        if pdf_bytes_cache is None:
            with open(pdf_path, "rb") as f:
                pdf_bytes_cache = f.read()
        
        # Extract text based on PDF type
        if pdf_type == "scan":
            print("Processing as scanned PDF with OCR...")
            extracted_text = extract_text_with_docling_bytes(pdf_bytes_cache)
        else:
            print("Processing as text-based PDF with PyMuPDF...")
            extracted_text = extract_text_from_pdf_bytes(pdf_bytes_cache)
        
        # Check if we got any text
        if not extracted_text or len(extracted_text.strip()) < 50:
            error_msg = "Could not extract text from PDF. "
            if pdf_type == "text":
                error_msg += "This might be a scanned document - try selecting 'Scanned' PDF type."
            else:
                error_msg += "The OCR could not read the document."
            raise HTTPException(status_code=400, detail=error_msg)
        
        print(f"Extracted {len(extracted_text)} characters from PDF")
        
        # Save extracted text
        text_path = os.path.join(DATA_DIR, "lease.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        
        # Chunk the text
        chunks = chunk_text(extracted_text)
        print(f"Created {len(chunks)} chunks")
        
        if not chunks:
            raise HTTPException(
                status_code=400, 
                detail="Could not create text chunks. The PDF may not contain valid content."
            )
        
        # Build search index
        embedding_index.build_index(chunks)
        
        if embedding_index.index is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to build search index."
            )
        
        # FAST PATH: Extract priority fields only
        print("Extracting priority fields (fast path)...")
        lease_summary = await extract_priority_only(embedding_index)
        document_loaded = True
        
        priority_count = lease_summary.get_priority_count()
        
        # Start background processing for remaining fields
        if schema_fields:
            print("Starting background extraction for schema fields...")
            asyncio.create_task(
                process_remaining_in_background(
                    embedding_index,
                    schema_fields,
                    lease_summary.priority_fields
                )
            )
        else:
            background_complete = True
        
        # Return immediately with priority fields
        return {
            "status": "success",
            "chunks_created": len(chunks),
            "fields_extracted": priority_count,
            "priority_fields_extracted": priority_count,
            "background_processing": bool(schema_fields),
            "summary": lease_summary.model_dump(),
            "markdown_output": lease_summary.markdown_summary,
            "full_markdown": lease_summary.full_markdown
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/api/background_status")
async def get_background_status():
    """Check status of background processing."""
    global lease_summary, background_processing, background_complete, background_error
    
    total_fields = len(lease_summary.fields) if lease_summary else 0
    total_with_values = len([f for f in lease_summary.fields if f.value]) if lease_summary else 0
    
    return {
        "processing": background_processing,
        "complete": background_complete,
        "error": background_error,
        "total_fields": total_fields,
        "fields_with_values": total_with_values,
        "full_markdown": lease_summary.full_markdown if lease_summary and background_complete else None
    }


@app.get("/api/lease_summary")
async def get_lease_summary():
    """Get the extracted lease summary."""
    if not document_loaded or lease_summary is None:
        raise HTTPException(status_code=400, detail="No document processed yet.")
    
    return {
        "priority_fields": [f.model_dump() for f in lease_summary.priority_fields],
        "all_fields": [f.model_dump() for f in lease_summary.fields],
        "markdown": lease_summary.markdown_summary,
        "full_markdown": lease_summary.full_markdown,
        "priority_count": lease_summary.get_priority_count(),
        "total_count": lease_summary.get_total_count(),
        "background_complete": background_complete
    }


@app.get("/api/download/csv")
async def download_csv():
    """Download the extracted lease details as CSV."""
    csv_path = os.path.join(DATA_DIR, "lease_details.csv")
    
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found. Process a document first.")
    
    return FileResponse(
        path=csv_path,
        filename="lease_details.csv",
        media_type="text/csv"
    )


@app.get("/api/download/markdown")
async def download_markdown(full: bool = False):
    """Download the lease summary as Markdown."""
    if not lease_summary:
        raise HTTPException(status_code=404, detail="No summary available. Process a document first.")
    
    content = lease_summary.full_markdown if full else lease_summary.markdown_summary
    filename = "lease_full_report.md" if full else "lease_summary.md"
    
    # Save to file
    md_path = os.path.join(DATA_DIR, filename)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return FileResponse(
        path=md_path,
        filename=filename,
        media_type="text/markdown"
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with the lease document."""
    if not document_loaded:
        raise HTTPException(status_code=400, detail="No document processed yet.")
    
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    response = await chat(request.question, embedding_index, lease_summary)
    return response


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", 
        "document_loaded": document_loaded,
        "schema_loaded": schema_loaded,
        "fields_count": len(schema_fields),
        "current_file": current_filename if current_filename else None,
        "background_processing": background_processing
    }


@app.get("/api/status")
async def get_status():
    pdf_path = os.path.join(DATA_DIR, "lease.pdf")
    schema_path = os.path.join(DATA_DIR, "schema.csv")
    csv_exists = os.path.exists(os.path.join(DATA_DIR, "lease_details.csv"))
    
    return {
        "pdf_uploaded": os.path.exists(pdf_path) or pdf_bytes_cache is not None,
        "schema_uploaded": os.path.exists(schema_path) or schema_loaded,
        "document_processed": document_loaded,
        "current_file": current_filename,
        "fields_count": len(schema_fields),
        "csv_available": csv_exists,
        "background_processing": background_processing,
        "background_complete": background_complete
    }


@app.get("/")
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/{filename:path}")
async def serve_static(filename: str):
    if filename.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn
    print(f"\n  Lease Document Analysis")
    print(f"  Frontend: http://localhost:3000")
    print(f"  API:      http://localhost:3000/api/\n")
    uvicorn.run(app, host="0.0.0.0", port=3000)
