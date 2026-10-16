"""Policy specialist agent backed by a persistent hybrid retrieval index."""

from __future__ import annotations

import logging
from typing import Any

from capstone.rag.answer import answer_from_evidence
from capstone.rag.chunking import chunk_documents
from capstone.rag.index import PolicyVectorIndex
from capstone.rag.ingestion import load_documents
from capstone.settings import load_config

logger = logging.getLogger(__name__)


class RAGAgent:
    def __init__(self) -> None:
        self.documents = load_documents()
        self.chunks = chunk_documents(self.documents)
        self._index: PolicyVectorIndex | None = None
        self._index_attempted = False

    def _ensure_index(self) -> PolicyVectorIndex | None:
        if self._index_attempted:
            return self._index
        self._index_attempted = True
        try:
            index = PolicyVectorIndex()
            index.build(self.chunks)
            self._index = index
        except Exception as exc:
            logger.warning("policy_vector_index_unavailable", extra={"error_type": type(exc).__name__})
            self._index = None
        return self._index

    def answer(self, query: str) -> dict[str, Any]:
        config = load_config("retrieval").get("hybrid", {})
        result = answer_from_evidence(
            query,
            self.chunks,
            top_k=int(config.get("top_k", 5)),
            min_score=float(config.get("minimum_answer_score", 2.0)),
            index=self._ensure_index(),
        )
        result["retrieval"] = {
            "mode": "hybrid-qdrant" if self._index else "lexical-fallback",
            "document_count": len(self.documents),
            "chunk_count": len(self.chunks),
            "embedding_mode": self._index.embedding_mode if self._index else "not-available",
        }
        return result
