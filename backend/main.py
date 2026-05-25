import os
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .models.schemas import (
    FrameworkInfo,
    IngestResponse,
    MappingRequest,
    MappingResponse,
    QueryRequest,
    QueryResponse,
)
from .ingestion.pdf_parser import parse_pdf, FRAMEWORK_PATTERNS, FRAMEWORK_COLORS
from .ingestion.chunker import chunk_pages
from .rag.retriever import RAGRetriever
from .mapping.cross_framework import CrossFrameworkMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SecPolicy GPT",
    description="AI-powered Compliance Framework Assistant",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = RAGRetriever()
mapper = CrossFrameworkMapper()


@app.get("/api/health")
async def health():
    doc_count = retriever.vector_store.count()
    return {
        "status": "ok",
        "version": "1.0.0",
        "documents_indexed": doc_count,
        "model": settings.claude_model,
    }


FRAMEWORK_FULL_NAMES = {
    "NIST_800_53": "NIST SP 800-53 Rev 5",
    "NIST_CSF": "NIST Cybersecurity Framework 2.0",
    "ISO_27001": "ISO/IEC 27001:2022",
    "SOC2": "SOC 2 Trust Services Criteria",
    "PCI_DSS": "PCI-DSS v4.0",
    "CIS": "CIS Controls v8",
    "UNKNOWN": "Unknown Framework",
}


@app.get("/api/frameworks", response_model=list[FrameworkInfo])
async def list_frameworks():
    loaded = retriever.get_frameworks()
    infos = []
    for fw_id in loaded:
        info = FRAMEWORK_PATTERNS.get(fw_id, {})
        infos.append(
            FrameworkInfo(
                id=fw_id,
                name=info.get("name", fw_id),
                full_name=FRAMEWORK_FULL_NAMES.get(fw_id, fw_id),
                doc_count=0,
                color=FRAMEWORK_COLORS.get(fw_id, "#6b7280"),
            )
        )
    return infos


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    framework: str = Form(default="auto"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        pages, detected_framework = parse_pdf(tmp_path, framework)
        chunks = chunk_pages(pages, detected_framework, file.filename)
        added = retriever.vector_store.add_chunks(chunks)

        return IngestResponse(
            framework=detected_framework,
            chunks_ingested=added,
            file_name=file.filename,
            status="success",
            message=f"Ingested {added} chunks from {file.filename} as {detected_framework}",
        )
    except Exception as e:
        logger.exception(f"Ingestion error for {file.filename}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    if retriever.vector_store.count() == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents indexed. Please ingest framework PDFs first.",
        )
    try:
        return await retriever.query(request)
    except Exception as e:
        logger.exception("Query error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query/stream")
async def query_stream(request: QueryRequest):
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    async def event_stream():
        async for chunk in retriever.stream_query(request):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/map", response_model=MappingResponse)
async def map_controls(request: MappingRequest):
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    try:
        return await mapper.map(request, retriever.vector_store)
    except Exception as e:
        logger.exception("Mapping error")
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
