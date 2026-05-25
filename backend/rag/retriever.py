import asyncio
import logging
from typing import AsyncIterator, Optional

import anthropic

from ..config import settings
from ..models.schemas import ControlSource, QueryRequest, QueryResponse
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SecPolicy GPT, an expert compliance and cybersecurity policy assistant with deep knowledge of:
- NIST SP 800-53 (Security and Privacy Controls)
- NIST Cybersecurity Framework (CSF)
- ISO/IEC 27001 (Information Security Management)
- SOC 2 Trust Services Criteria
- PCI-DSS (Payment Card Industry Data Security Standard)
- CIS Controls and Benchmarks

Your role is to help security professionals, auditors, and compliance teams understand and work with these frameworks.

When answering questions:
1. Always cite specific control IDs when referencing requirements (e.g., "NIST 800-53 AC-2", "ISO 27001 A.9.2")
2. Be precise and authoritative — this is used for compliance decisions
3. When context is provided from the knowledge base, ground your answer in that context
4. If information is not in the provided context, say so clearly and provide general guidance
5. For cross-framework questions, highlight both similarities and important differences
6. Use structured formatting (headers, bullets) for complex multi-part answers

You have access to ingested compliance framework documents as context."""


def _format_context(hits: list[dict]) -> str:
    if not hits:
        return "No relevant framework content found in the knowledge base."

    parts = []
    for i, hit in enumerate(hits[:8], 1):
        fw = hit["framework"].replace("_", " ")
        ctrl = f" [{hit['control_id']}]" if hit.get("control_id") else ""
        name = f" — {hit['control_name']}" if hit.get("control_name") else ""
        parts.append(
            f"[Source {i}] {fw}{ctrl}{name} (relevance: {hit['relevance_score']:.2f})\n{hit['text']}"
        )

    return "\n\n---\n\n".join(parts)


class RAGRetriever:
    def __init__(self):
        self.vector_store = VectorStore()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def query(self, request: QueryRequest) -> QueryResponse:
        hits = await asyncio.to_thread(
            self.vector_store.query,
            request.question,
            request.top_k,
            request.frameworks,
        )

        context = _format_context(hits)
        frameworks_queried = request.frameworks or self.vector_store.get_frameworks()

        user_message = f"""<context>
{context}
</context>

Question: {request.question}"""

        response = await asyncio.to_thread(
            self.client.messages.create,
            model=settings.claude_model,
            max_tokens=settings.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )

        answer = response.content[0].text

        sources = [
            ControlSource(
                framework=h["framework"],
                control_id=h.get("control_id"),
                control_name=h.get("control_name"),
                text=h["text"][:400],
                relevance_score=h["relevance_score"],
            )
            for h in hits[:6]
        ]

        return QueryResponse(
            answer=answer,
            sources=sources,
            frameworks_queried=frameworks_queried,
        )

    async def stream_query(self, request: QueryRequest) -> AsyncIterator[str]:
        hits = await asyncio.to_thread(
            self.vector_store.query,
            request.question,
            request.top_k,
            request.frameworks,
        )

        context = _format_context(hits)

        user_message = f"""<context>
{context}
</context>

Question: {request.question}"""

        sources = [
            ControlSource(
                framework=h["framework"],
                control_id=h.get("control_id"),
                control_name=h.get("control_name"),
                text=h["text"][:400],
                relevance_score=h["relevance_score"],
            )
            for h in hits[:6]
        ]

        # Yield sources metadata first as JSON event
        import json
        sources_data = [s.model_dump() for s in sources]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources_data})}\n\n"

        with self.client.messages.stream(
            model=settings.claude_model,
            max_tokens=settings.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text_chunk in stream.text_stream:
                yield f"data: {json.dumps({'type': 'token', 'text': text_chunk})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    def get_frameworks(self) -> list[str]:
        return self.vector_store.get_frameworks()
