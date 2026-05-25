from pydantic import BaseModel, Field
from typing import List, Optional


class ControlSource(BaseModel):
    framework: str
    control_id: Optional[str] = None
    control_name: Optional[str] = None
    section: Optional[str] = None
    text: str
    relevance_score: float


class QueryRequest(BaseModel):
    question: str
    frameworks: Optional[List[str]] = None
    top_k: int = Field(default=8, ge=1, le=20)
    stream: bool = False


class QueryResponse(BaseModel):
    answer: str
    sources: List[ControlSource]
    frameworks_queried: List[str]


class MappingRequest(BaseModel):
    source_framework: str
    control_id: Optional[str] = None
    control_description: Optional[str] = None
    target_frameworks: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=10)


class MappingResult(BaseModel):
    source_control_id: Optional[str]
    source_control_name: Optional[str]
    target_framework: str
    target_control_id: Optional[str]
    target_control_name: Optional[str]
    target_text: Optional[str]
    mapping_type: str  # "static" or "semantic"
    confidence: float
    notes: Optional[str]


class MappingResponse(BaseModel):
    source_framework: str
    source_control_id: Optional[str]
    mappings: List[MappingResult]
    summary: str


class IngestResponse(BaseModel):
    framework: str
    chunks_ingested: int
    file_name: str
    status: str
    message: str


class FrameworkInfo(BaseModel):
    id: str
    name: str
    full_name: str
    doc_count: int
    color: str
