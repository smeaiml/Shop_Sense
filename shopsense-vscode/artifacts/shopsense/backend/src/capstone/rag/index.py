"""Persistent local Qdrant policy index."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from capstone.rag.embeddings import PolicyEmbedder
from capstone.settings import RUNTIME_DIR, load_config


class PolicyVectorIndex:
    def __init__(self) -> None:
        retrieval = load_config("retrieval")
        qdrant_config = retrieval.get("qdrant", {})
        self.collection = str(qdrant_config.get("collection", "shopsense_policy"))
        relative = Path(qdrant_config.get("runtime_path", "runtime/qdrant"))
        path = relative if relative.is_absolute() else RUNTIME_DIR.parent / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(path))
        self.embedder = PolicyEmbedder()
        self._indexed_ids: set[str] = set()

    @staticmethod
    def _point_id(chunk_id: str) -> int:
        return int(hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()[:15], 16)

    def build(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        vectors = self.embedder.embed([chunk["text"] for chunk in chunks])
        size = len(vectors[0])
        if self.client.collection_exists(self.collection):
            info = self.client.get_collection(self.collection)
            current_size = info.config.params.vectors.size
            if current_size != size:
                self.client.delete_collection(self.collection)
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE),
            )
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(models.PointStruct(
                id=self._point_id(chunk["chunk_id"]),
                vector=vector,
                payload={key: chunk.get(key) for key in ("chunk_id", "title", "source", "category", "format", "text")},
            ))
        self.client.upsert(collection_name=self.collection, points=points, wait=True)
        self._indexed_ids = {chunk["chunk_id"] for chunk in chunks}

    def search(self, query: str, *, limit: int = 20) -> dict[str, float]:
        if not self._indexed_ids:
            return {}
        vector = self.embedder.embed([query])[0]
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return {
            str(point.payload["chunk_id"]): float(point.score)
            for point in response.points
            if point.payload and point.payload.get("chunk_id")
        }

    @property
    def embedding_mode(self) -> str:
        return self.embedder.mode
