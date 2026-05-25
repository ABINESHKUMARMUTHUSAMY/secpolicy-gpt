# SecPolicy GPT — Compliance Framework Assistant

An AI-powered RAG system for querying and cross-mapping security compliance frameworks: NIST 800-53, NIST CSF, ISO 27001, SOC 2, PCI-DSS, and CIS Controls.

## Features

- **Natural language Q&A** — Ask questions in plain English, get answers with cited controls
- **Cross-framework mapping** — Map controls between any two frameworks (e.g., "What ISO 27001 controls map to NIST 800-53 AC-2?")
- **Streaming responses** — Real-time token streaming with Claude
- **Semantic + static mapping** — Combines a curated 40+ mapping database with vector-similarity fallback
- **Source citations** — Every answer shows which controls it drew from, with relevance scores
- **Framework filtering** — Scope queries to one or more specific frameworks
- **Drag-and-drop PDF ingestion** — Upload any framework PDF directly from the browser

## Quick Start

### 1. Set up environment

```bash
cd secpolicy-gpt
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 2. Create a virtual environment (use Python 3.12 — required for ChromaDB/sentence-transformers)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
make run
# Open http://localhost:8000
```

### Or with Docker

```bash
docker compose up -d
```

## Getting Framework PDFs

| Framework | Source |
|-----------|--------|
| NIST SP 800-53 Rev 5 | https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final |
| NIST CSF 2.0 | https://www.nist.gov/cyberframework |
| PCI-DSS v4.0 | https://www.pcisecuritystandards.org/document_library |
| CIS Controls v8 | https://www.cisecurity.org/controls/downloads |
| ISO 27001 | Purchase from ISO or use publicly available summaries |
| SOC 2 | https://www.aicpa.org/resources/landing/system-and-organization-controls-soc-suite-of-services |

Once downloaded, upload them via the **Ingest PDFs** tab in the UI.

## Architecture

```
secpolicy-gpt/
├── backend/
│   ├── main.py              # FastAPI app + endpoints
│   ├── config.py            # Settings (env vars)
│   ├── ingestion/
│   │   ├── pdf_parser.py    # PyMuPDF parsing + framework detection
│   │   └── chunker.py       # Control-boundary-aware chunking
│   ├── rag/
│   │   ├── vector_store.py  # ChromaDB with sentence-transformers
│   │   └── retriever.py     # RAG pipeline + Claude streaming
│   ├── mapping/
│   │   ├── cross_framework.py      # Mapping logic (static + semantic)
│   │   └── framework_mappings.json # 40+ curated control mappings
│   └── models/schemas.py    # Pydantic models
├── frontend/
│   ├── index.html           # UI shell
│   ├── style.css            # Dark cybersecurity theme
│   └── app.js               # Vanilla JS (no framework)
└── docker-compose.yml
```

### Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.11 |
| LLM | Claude (claude-sonnet-4-6) via Anthropic SDK |
| Vector DB | ChromaDB (persistent, local) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| PDF Parsing | PyMuPDF (fitz) |
| Frontend | Vanilla HTML/CSS/JS |

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check + index stats |
| `/api/frameworks` | GET | List loaded frameworks |
| `/api/ingest` | POST | Ingest a PDF (multipart/form-data) |
| `/api/query` | POST | RAG query (non-streaming) |
| `/api/query/stream` | POST | RAG query (SSE streaming) |
| `/api/map` | POST | Cross-framework control mapping |

### Example queries

```bash
# Query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What controls does NIST 800-53 require for vendor risk management?"}'

# Map controls
curl -X POST http://localhost:8000/api/map \
  -H "Content-Type: application/json" \
  -d '{
    "source_framework": "NIST_800_53",
    "control_id": "AC-2",
    "target_frameworks": ["ISO_27001", "SOC2"]
  }'
```

## Extending the Mapping Database

Edit `backend/mapping/framework_mappings.json` to add mappings:

```json
{
  "source_framework": "NIST_800_53",
  "source_id": "NEW-1",
  "source_name": "Control Name",
  "targets": [
    {
      "framework": "ISO_27001",
      "id": "A.X.X",
      "name": "ISO Control Name",
      "strength": "strong"
    }
  ]
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model to use |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `MAX_TOKENS` | `2048` | Max tokens for Claude responses |
