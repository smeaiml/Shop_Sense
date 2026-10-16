"""Stable overlapping policy chunks that preserve their document source."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from capstone.settings import load_config


def chunk_documents(
    documents: list[dict[str, Any]],
    *,
    max_chars: int | None = None,
    overlap_chars: int | None = None,
) -> list[dict[str, Any]]:
    config = load_config("retrieval").get("chunking", {})
    max_chars = max_chars or int(config.get("max_chars", 1100))
    overlap_chars = overlap_chars if overlap_chars is not None else int(config.get("overlap_chars", 140))
    if max_chars < 100 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("Invalid policy chunk size or overlap.")
    chunks = []
    for document in documents:
        text = re.sub(r"\s+", " ", str(document.get("text", ""))).strip()
        if not text:
            continue
        start = 0
        part = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + max_chars // 2, end)
                if boundary > start:
                    end = boundary
            content = text[start:end].strip()
            material = f"{document.get('source','')}|{part}|{content}"
            chunk_id = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
            chunks.append({
                "chunk_id": chunk_id,
                "title": str(document.get("title") or "ShopSense policy"),
                "source": str(document.get("source") or "unknown"),
                "format": str(document.get("format") or "markdown"),
                "category": document.get("category"),
                "text": content,
            })
            if end >= len(text):
                break
            start = max(start + 1, end - overlap_chars)
            part += 1
    return chunks
