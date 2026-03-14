# Lease Document AI Analyzer

A production-ready AI-powered system for analyzing lease documents. Upload a PDF, and the system automatically extracts key information like tenant names, rent amounts, lease dates, and more — then lets you chat with your document to ask follow-up questions.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## What It Does

This tool helps you quickly understand lease agreements by:

1. **Extracting Key Information** — Automatically pulls out 9 essential fields (tenant, landlord, dates, rent, etc.)
2. **Enabling Document Chat** — Ask questions in plain English and get accurate answers with citations
3. **Exporting Results** — Download extracted data as CSV or Markdown reports

Perfect for property managers, legal teams, real estate professionals, or anyone who deals with lease documents regularly.

---

## Features

### Automatic Field Extraction
The system extracts these priority fields from any lease document:

| Field | Description |
|-------|-------------|
| **Tenant** | Full legal name of the tenant/lessee |
| **Landlord** | Full legal name of the landlord/lessor |
| **Lease Start Date** | When the lease begins |
| **Lease End Date** | When the lease expires |
| **Rent Amount** | Monthly or annual rent payment |
| **Security Deposit** | Required deposit amount |
| **Renewal Options** | Terms for lease renewal |
| **Termination Clauses** | Early termination conditions |
| **Special Provisions** | Any unique terms or addendums |

### Smart Document Chat (RAG)
- Ask questions in natural language
- Get answers with page/section citations
- Context-aware responses based on your specific document

### Flexible PDF Processing
- **Text-based PDFs** — Fast extraction using PyMuPDF
- **Scanned PDFs** — OCR support using EasyOCR

### Custom Schema Support
Upload a CSV file to define additional fields you want to extract beyond the default 9.

### Export Options
- **CSV Download** — Spreadsheet-ready data
- **Markdown Report** — Formatted summary document

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI (Python) |
| **Frontend** | Vanilla HTML/CSS/JavaScript |
| **Vector Search** | FAISS + SentenceTransformers |
| **LLM** | OpenRouter API (supports multiple models) |
| **PDF Processing** | PyMuPDF (text) / EasyOCR (scanned) |

---

## Quick Start

### Prerequisites
- Python 3.10 or higher
- OpenRouter API key ([get one free](https://openrouter.ai/))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/lease-analyzer.git
   cd lease-analyzer
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure environment**
   
   Create `backend/.env` file:
   ```env
   OPENROUTER_API_KEY=your_api_key_here
   OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   ```

5. **Run the application**
   ```bash
   python backend/app.py
   ```

6. **Open in browser**
   ```
   http://localhost:3000
   ```

---

## How to Use

### Step 1: Upload Your Lease PDF
- Click the upload area or drag-and-drop your PDF
- Select PDF type: **Text-based** (standard) or **Scanned** (for image PDFs)

### Step 2: Process the Document
- Click **"Process Document"**
- Wait for extraction (typically 5-10 seconds)
- View the extracted fields in the summary panel

### Step 3: Chat with Your Document
- Type questions in the chat box
- Examples:
  - "What is the monthly rent?"
  - "When does the lease expire?"
  - "Are pets allowed?"
  - "What happens if I break the lease early?"

### Step 4: Export Results
- Click **"Download CSV"** for spreadsheet format
- Click **"View Summary"** for markdown report

---

## API Reference

All endpoints are available at `http://localhost:3000/api/`

### Upload File
```http
POST /api/upload
Content-Type: multipart/form-data

file: <PDF or CSV file>
```

### Process Document
```http
POST /api/process
Content-Type: application/x-www-form-urlencoded

pdf_type: "text" | "scan"
```

### Chat with Document
```http
POST /api/chat
Content-Type: application/json

{
  "question": "What is the rent amount?"
}
```

### Get Extraction Status
```http
GET /api/background_status
```

### Download CSV
```http
GET /api/download/csv
```

### Health Check
```http
GET /api/health
```

---

## Project Structure

```
lease-analyzer/
├── backend/
│   ├── app.py              # FastAPI application & routes
│   ├── config.py           # Environment configuration
│   ├── models.py           # Pydantic data models
│   ├── extractor.py        # Field extraction logic
│   ├── chat_engine.py      # RAG chat implementation
│   ├── embedding_index.py  # FAISS vector search
│   ├── chunker.py          # Text chunking logic
│   ├── pdf_loader.py       # PyMuPDF text extraction
│   ├── docling_loader.py   # EasyOCR for scanned PDFs
│   ├── schema_loader.py    # Custom CSV schema parser
│   ├── requirements.txt    # Python dependencies
│   ├── .env                # API keys (create this)
│   └── data/               # Uploaded files & outputs
│
├── frontend/
│   ├── index.html          # Main UI
│   ├── styles.css          # Styling
│   └── app.js              # Frontend logic
│
└── README.md
```

---

## How It Works

### 1. Document Processing Pipeline

```
PDF Upload → Text Extraction → Chunking → Embedding → Vector Index
```

- **Text Extraction**: PyMuPDF extracts text while preserving page numbers
- **Chunking**: Text is split into ~1000 character chunks with overlap
- **Embedding**: SentenceTransformers creates vector representations
- **Indexing**: FAISS enables fast similarity search

### 2. Field Extraction (Smart Batching)

```
Document Context → Single LLM Call → Parse 9 Fields → Validate & Clean
```

- All 9 priority fields extracted in ONE API call (fast!)
- Fallback to individual calls if batch fails
- Robust parsing handles various response formats

### 3. RAG Chat

```
User Question → Semantic Search → Retrieve Chunks → LLM + Context → Answer
```

- Questions are embedded and matched against document chunks
- Top 5 most relevant chunks form the context
- LLM generates answer with citations

---

## Custom Schema

Want to extract additional fields? Create a CSV file:

```csv
name,display_name,field_type,description
property_address,Property Address,text,The address of the leased property
parking_spaces,Parking Spaces,number,Number of parking spaces included
pet_policy,Pet Policy,text,Rules regarding pets
```

Upload this CSV before processing your PDF, and the system will extract these fields too.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | Required |
| `OPENROUTER_MODEL` | LLM model to use | `google/gemini-2.0-flash-exp:free` |
| `OPENROUTER_BASE_URL` | API base URL | `https://openrouter.ai/api/v1` |

### Recommended Free Models

| Model | Best For |
|-------|----------|
| `google/gemini-2.0-flash-exp:free` | Best overall performance |
| `meta-llama/llama-3.3-8b-instruct:free` | Good alternative |
| `qwen/qwen-2.5-7b-instruct:free` | Fast responses |

---

## Troubleshooting

### "No text extracted from PDF"
- Try switching to **Scanned** PDF type
- Ensure the PDF isn't password-protected
- Check if the PDF contains actual text (not just images)

### "API returned empty response"
- Verify your OpenRouter API key is correct
- Try a different model in `.env`
- Check your API rate limits

### "Port 3000 already in use"
```bash
# Windows
netstat -ano | findstr :3000
taskkill /F /PID <PID>

# macOS/Linux
lsof -i :3000
kill -9 <PID>
```

### Slow extraction
- This is normal for free API tiers
- Consider using a paid model for production use

---

## Performance Tips

1. **Use text-based PDFs** when possible (faster than OCR)
2. **Keep PDFs under 50 pages** for best performance
3. **Use specific questions** in chat for better answers
4. **Check the console** for detailed extraction logs

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [FAISS](https://github.com/facebookresearch/faiss) - Efficient similarity search
- [SentenceTransformers](https://www.sbert.net/) - Text embeddings
- [OpenRouter](https://openrouter.ai/) - LLM API access
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing

---

## Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Search existing [Issues](https://github.com/yourusername/lease-analyzer/issues)
3. Create a new issue with:
   - Description of the problem
   - Steps to reproduce
   - Console output/error messages
   - PDF type (text/scanned)

---

**Built with purpose. Made simple.**
