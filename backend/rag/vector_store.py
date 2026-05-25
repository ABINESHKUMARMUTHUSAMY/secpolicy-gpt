import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from typing import Optional
import logging

from ..config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "secpolicy_controls"


class VectorStore:
    def __init__(self):
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"VectorStore initialized with {self.collection.count()} documents")

    def add_chunks(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0

        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [
            {
                "framework": c.get("framework", "UNKNOWN"),
                "control_id": c.get("control_id") or "",
                "control_name": c.get("control_name") or "",
                "page": str(c.get("page", 0)),
                "source_file": c.get("source_file", ""),
            }
            for c in chunks
        ]

        # Deduplicate by ID
        existing = set(self.collection.get(ids=ids)["ids"])
        new_chunks = [
            (id_, text, meta)
            for id_, text, meta in zip(ids, texts, metadatas)
            if id_ not in existing
        ]

        if not new_chunks:
            return 0

        batch_size = 100
        added = 0
        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i : i + batch_size]
            b_ids, b_texts, b_metas = zip(*batch)
            self.collection.add(ids=list(b_ids), documents=list(b_texts), metadatas=list(b_metas))
            added += len(batch)

        return added

    def query(
        self,
        query_text: str,
        top_k: int = 10,
        frameworks: Optional[list[str]] = None,
    ) -> list[dict]:
        where = None
        if frameworks and len(frameworks) == 1:
            where = {"framework": {"$eq": frameworks[0]}}
        elif frameworks and len(frameworks) > 1:
            where = {"framework": {"$in": frameworks}}

        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(top_k, self.collection.count() or 1),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "framework": meta.get("framework", "UNKNOWN"),
                "control_id": meta.get("control_id") or None,
                "control_name": meta.get("control_name") or None,
                "page": meta.get("page"),
                "source_file": meta.get("source_file"),
                "relevance_score": round(1 - dist, 4),
            })

        return hits

    def get_frameworks(self) -> list[str]:
        if self.collection.count() == 0:
            return []
        results = self.collection.get(include=["metadatas"])
        frameworks = {m.get("framework", "UNKNOWN") for m in results["metadatas"]}
        return sorted(frameworks)

    def count(self) -> int:
        return self.collection.count()
