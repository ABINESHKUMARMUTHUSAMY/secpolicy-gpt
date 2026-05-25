import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

import anthropic

from ..config import settings
from ..models.schemas import MappingRequest, MappingResponse, MappingResult

logger = logging.getLogger(__name__)

MAPPINGS_FILE = Path(__file__).parent / "framework_mappings.json"

MAPPING_SYSTEM_PROMPT = """You are a compliance framework expert who specializes in cross-framework control mapping.
Your task is to analyze control mappings between security frameworks (NIST 800-53, ISO 27001, SOC 2, PCI-DSS, NIST CSF, CIS Controls).

When presenting mappings:
1. Explain WHY the controls are equivalent or related
2. Note any important gaps or differences in scope
3. Highlight where one framework goes deeper than another
4. Use precise control IDs (e.g., "NIST 800-53 AC-2", "ISO 27001 A.5.15")
5. Rate confidence: strong/moderate/weak with reasoning"""


class CrossFrameworkMapper:
    def __init__(self):
        self._mappings: list[dict] = []
        self._load_mappings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def _load_mappings(self):
        try:
            data = json.loads(MAPPINGS_FILE.read_text())
            self._mappings = data.get("mappings", [])
            logger.info(f"Loaded {len(self._mappings)} static control mappings")
        except Exception as e:
            logger.warning(f"Could not load mappings file: {e}")
            self._mappings = []

    def _find_static_mappings(
        self,
        source_framework: str,
        control_id: Optional[str],
        target_frameworks: Optional[list[str]],
    ) -> list[dict]:
        results = []
        for mapping in self._mappings:
            if mapping["source_framework"] != source_framework:
                continue
            if control_id and mapping["source_id"].upper() != control_id.upper():
                continue
            for target in mapping.get("targets", []):
                if target_frameworks and target["framework"] not in target_frameworks:
                    continue
                results.append({
                    "source_id": mapping["source_id"],
                    "source_name": mapping["source_name"],
                    "target_framework": target["framework"],
                    "target_id": target["id"],
                    "target_name": target["name"],
                    "strength": target.get("strength", "moderate"),
                })
        return results

    def _strength_to_confidence(self, strength: str) -> float:
        return {"strong": 0.95, "moderate": 0.75, "weak": 0.50}.get(strength, 0.60)

    async def map(self, request: MappingRequest, vector_store=None) -> MappingResponse:
        static_hits = self._find_static_mappings(
            request.source_framework,
            request.control_id,
            request.target_frameworks,
        )

        mapping_results: list[MappingResult] = []

        for hit in static_hits[: request.top_k]:
            mapping_results.append(
                MappingResult(
                    source_control_id=hit["source_id"],
                    source_control_name=hit["source_name"],
                    target_framework=hit["target_framework"],
                    target_control_id=hit["target_id"],
                    target_control_name=hit["target_name"],
                    target_text=None,
                    mapping_type="static",
                    confidence=self._strength_to_confidence(hit["strength"]),
                    notes=f"Mapping strength: {hit['strength']}",
                )
            )

        # Semantic mapping fallback via vector store
        if vector_store and (not mapping_results or request.control_description):
            query_text = (
                request.control_description
                or f"{request.source_framework} {request.control_id} control requirements"
            )
            semantic_hits = await asyncio.to_thread(
                vector_store.query,
                query_text,
                request.top_k * 2,
                request.target_frameworks,
            )
            seen_ids = {(r.target_framework, r.target_control_id) for r in mapping_results}
            for hit in semantic_hits:
                key = (hit["framework"], hit.get("control_id"))
                if key not in seen_ids and hit["framework"] != request.source_framework:
                    mapping_results.append(
                        MappingResult(
                            source_control_id=request.control_id,
                            source_control_name=None,
                            target_framework=hit["framework"],
                            target_control_id=hit.get("control_id"),
                            target_control_name=hit.get("control_name"),
                            target_text=hit["text"][:300],
                            mapping_type="semantic",
                            confidence=round(hit["relevance_score"] * 0.85, 3),
                            notes="Semantically similar control",
                        )
                    )
                    seen_ids.add(key)

        # Generate LLM summary of mappings
        summary = await self._generate_summary(request, mapping_results)

        return MappingResponse(
            source_framework=request.source_framework,
            source_control_id=request.control_id,
            mappings=mapping_results[: request.top_k],
            summary=summary,
        )

    async def _generate_summary(self, request: MappingRequest, mappings: list[MappingResult]) -> str:
        if not mappings:
            return f"No mappings found for {request.source_framework} {request.control_id or ''}. Consider ingesting relevant framework documents."

        mapping_text = "\n".join(
            f"- {m.target_framework} {m.target_control_id or 'N/A'}: {m.target_control_name or 'Unknown'} "
            f"(confidence: {m.confidence:.0%}, type: {m.mapping_type})"
            for m in mappings
        )

        prompt = f"""Source: {request.source_framework} {request.control_id or ''} — {request.control_description or ''}

Mappings found:
{mapping_text}

Provide a concise 2-3 paragraph analysis explaining:
1. Which target controls are the strongest equivalents and why
2. Any important scope differences or gaps
3. Practical compliance advice for teams mapping between these frameworks"""

        response = await asyncio.to_thread(
            self.client.messages.create,
            model=settings.claude_model,
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": MAPPING_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
