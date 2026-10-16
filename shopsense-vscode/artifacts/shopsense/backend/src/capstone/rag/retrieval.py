"""Hybrid lexical + Qdrant retrieval with a category-aware reranking pass."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from capstone.settings import load_config

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "is", "it", "of", "on", "or", "the", "to", "what", "when",
    "which", "with", "you", "your", "my", "do", "does", "can", "will",
}
_CATEGORY_MARKERS = (
    "electronics", "furniture", "home & kitchen", "toys", "apparel",
    "beauty", "groceries", "sports & outdoors",
)


def _tokens(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9]+", text.casefold())
        if token not in _STOPWORDS
    ]


def _target_category(query: str) -> str | None:
    lower = query.casefold()
    for category in _CATEGORY_MARKERS:
        if category in lower:
            return category
    aliases = (
        (("headphones", "television", "television", "tv", "power bank"), "electronics"),
        (("sofa", "couch", "wardrobe"), "furniture"),
        (("kitchen", "blender", "mixer", "cookware", "appliance"), "home & kitchen"),
        (("clothing", "shirt", "dress"), "apparel"),
        (("grocery", "groceries", "food"), "groceries"),
        (("toy", "toys"), "toys"),
        (("football", "camping", "sports gear"), "sports & outdoors"),
    )
    for terms, category in aliases:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lower) for term in terms):
            return category
    return None


def _lexical_score(query_tokens: list[str], text: str) -> float:
    document_tokens = _tokens(text)
    if not document_tokens:
        return 0.0
    counts = Counter(document_tokens)
    score = 0.0
    for token in set(query_tokens):
        if token in counts:
            score += 1.0 + math.log1p(counts[token])
    return score


def _policy_sources_to_keep(query: str, target_category: str | None) -> set[str]:
    lower = query.casefold()
    sources: set[str] = set()
    category_sources = {
        "electronics": "category-electronics.md",
        "furniture": "category-furniture.md",
        "home & kitchen": "category-home-kitchen.md",
        "toys": "category-toys.md",
        "apparel": "category-apparel.md",
        "beauty": "category-beauty.md",
        "groceries": "category-groceries.md",
        "sports & outdoors": "category-sports-outdoors.md",
    }
    if target_category in category_sources:
        sources.add(category_sources[target_category])
    if any(term in lower for term in ("return", "refund", "restocking", "pickup fee", "upi")):
        sources.add("returns-policy.md")
    if any(term in lower for term in (
        "refund authorisation", "refund authority", "approval tier",
        "automated cap", "goodwill credit", "approval limit",
    )):
        sources.add("refund-authority.md")
    if any(term in lower for term in ("fraud", "flag", "account-risk")):
        sources.add("fraud-abuse.md")
    if any(term in lower for term in (
        "escalation triggers", "safety incident", "consumer forum",
        "legal notice", "third contact",
    )):
        sources.add("escalation-tone.md")
    if any(term in lower for term in ("shipping", "delivery promise", "tracking", "shipment", "lost parcel", "delay")):
        sources.add("shipping-policy.md")
    return sources


def retrieve(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 5,
    *,
    index: Any = None,
) -> list[dict[str, Any]]:
    if not query or top_k < 1:
        return []
    config = load_config("retrieval").get("hybrid", {})
    lexical_weight = float(config.get("lexical_weight", 0.62))
    vector_weight = float(config.get("vector_weight", 0.38))
    category_boost = float(config.get("category_match_boost", 3.0))
    target_category = _target_category(query)
    query_tokens = _tokens(query)
    vector_scores: dict[str, float] = {}
    if index is not None:
        try:
            vector_scores = index.search(query, limit=max(top_k * 5, 20))
        except Exception:
            vector_scores = {}
    max_lexical = max(
        (_lexical_score(query_tokens, str(chunk.get("text", ""))) for chunk in chunks),
        default=0.0,
    )
    results = []
    for chunk in chunks:
        lexical = _lexical_score(query_tokens, str(chunk.get("text", "")))
        vector = vector_scores.get(str(chunk.get("chunk_id", "")), 0.0)
        score = lexical_weight * lexical + vector_weight * vector * 5
        chunk_category = str(chunk.get("category") or "").casefold()
        title = str(chunk.get("title", "")).casefold()
        if target_category:
            if target_category == chunk_category or target_category in title:
                score += category_boost
            elif "category policy addendum" in title:
                score -= category_boost * 1.4
        exact_phrase = " ".join(query_tokens[:4])
        if exact_phrase and exact_phrase in str(chunk.get("text", "")).casefold():
            score += 1.25
        if lexical <= 0 and vector <= 0:
            continue
        item = dict(chunk)
        item["retrieval_score"] = round(score, 4)
        item["lexical_score"] = round(lexical / max(max_lexical, 1.0), 4)
        item["vector_score"] = round(vector, 4)
        results.append(item)
    ranked = sorted(results, key=lambda item: item["retrieval_score"], reverse=True)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for source in sorted(_policy_sources_to_keep(query, target_category)):
        candidates = [item for item in ranked if str(item.get("source", "")).casefold() == source]
        if candidates:
            item = candidates[0]
            chunk_id = str(item.get("chunk_id", ""))
            if chunk_id not in selected_ids:
                selected.append(item)
                selected_ids.add(chunk_id)
    selected.extend(
        item for item in ranked
        if str(item.get("chunk_id", "")) not in selected_ids
    )
    return selected[:top_k]
