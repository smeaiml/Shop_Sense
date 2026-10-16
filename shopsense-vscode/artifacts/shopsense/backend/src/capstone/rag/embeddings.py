"""FastEmbed sentence vectors with a deterministic local fallback."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Iterable

from capstone.settings import load_config

logger = logging.getLogger(__name__)


class PolicyEmbedder:
    def __init__(self) -> None:
        config = load_config("retrieval").get("embeddings", {})
        self.model_name = str(config.get("model", "BAAI/bge-small-en-v1.5"))
        self.dimensions = int(config.get("dimensions", 384))
        self._model = None
        self.mode = "fastembed"

    def _load_model(self):
        if self._model is not None:
            return self._model
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        values = [str(text) for text in texts]
        if not values:
            return []
        try:
            model = self._load_model()
            return [vector.tolist() for vector in model.embed(values)]
        except Exception as exc:
            logger.warning("policy_embedding_fallback", extra={"error_type": type(exc).__name__})
            self.mode = "deterministic-hash"
            return [self._fallback(text) for text in values]

    def _fallback(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.casefold())
        aliases = {
            "refund": "reimbursement", "reimburse": "refund", "repayment": "refund",
            "return": "sendback", "returns": "sendback", "send": "sendback",
            "broken": "damaged", "defective": "damaged", "cracked": "damaged",
            "delivery": "shipping", "shipment": "shipping", "tracking": "shipping",
        }
        normalized = [aliases.get(token, token) for token in tokens]
        for token in normalized:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        norm = sum(item * item for item in vector) ** 0.5
        return [item / norm for item in vector] if norm else vector
