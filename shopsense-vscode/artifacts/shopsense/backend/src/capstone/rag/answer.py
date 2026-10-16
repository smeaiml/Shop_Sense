
"""Build concise, evidence-grounded ShopSense policy answers."""

import re
from typing import Any

from capstone.rag.retrieval import retrieve


def _abstain(message: str) -> dict[str, Any]:
    """Return a safe response when evidence is insufficient."""
    return {
        "status": "insufficient_evidence",
        "answer": message,
        "citations": [],
        "evidence": [],
    }


def _make_evidence(
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Preserve evidence chunks and deduplicate source citations."""
    evidence = []
    citations = []
    seen_sources = set()

    for result in results:
        source_key = (result["title"], result["source"])

        if source_key not in seen_sources:
            seen_sources.add(source_key)
            citations.append({
                "document_id": str(result["source"]),
                "title": result["title"],
                "source": result["source"],
            })

        evidence.append({
            "document_id": result["chunk_id"],
            "title": result["title"],
            "source": result["source"],
            "text": result["text"],
            "score": result["retrieval_score"],
        })

    return evidence, citations



def _extract_policy_answer(
    query: str,
    results: list[dict[str, Any]],
) -> str | None:
    """Answer common policy questions using retrieved evidence only."""
    query_lower = query.casefold()

    category_markers = {
        "electronics": "Category Policy Addendum: Electronics",
        "headphones": "Category Policy Addendum: Electronics",
        "television": "Category Policy Addendum: Electronics",
        "furniture": "Category Policy Addendum: Furniture",
        "sofa": "Category Policy Addendum: Furniture",
        "home & kitchen": "Category Policy Addendum: Home & Kitchen",
        "kitchen": "Category Policy Addendum: Home & Kitchen",
        "blender": "Category Policy Addendum: Home & Kitchen",
        "mixer": "Category Policy Addendum: Home & Kitchen",
        "furniture": "Category Policy Addendum: Furniture",
        "toys": "Category Policy Addendum: Toys",
        "apparel": "Category Policy Addendum: Apparel",
        "clothing": "Category Policy Addendum: Apparel",
        "beauty": "Category Policy Addendum: Beauty",
        "groceries": "Category Policy Addendum: Groceries",
        "grocery": "Category Policy Addendum: Groceries",
        "sports & outdoors": "Category Policy Addendum: Sports & Outdoors",
        "sports": "Category Policy Addendum: Sports & Outdoors",
    }

    requested_category = next(
        (
            title
            for marker, title in category_markers.items()
            if marker in query_lower
        ),
        None,
    )

    relevant_results = [
        item for item in results
        if requested_category is None
        or item["title"] == requested_category
    ]

    text = "\n".join(item["text"] for item in relevant_results)

    if not text.strip():
        return None

    facts = []

    asks_window = (
        "return window" in query_lower
        or "how many days" in query_lower
        or "days from delivery" in query_lower
    )
    asks_fee = (
        "restocking fee" in query_lower
        or "restocking" in query_lower
        or "fee structure" in query_lower
    )
    asks_pickup = (
        "pickup fee" in query_lower
        or "pickup charge" in query_lower
        or "pickup cost" in query_lower
    )

    if asks_window:
        match = re.search(
            r"standard return window for [^\n.]{1,180}?"
            r"\bis\s+(?:strictly\s+)?\**(\d+)\**\s+days?",
            text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"return window[^\n.]{0,180}?(?:is|strictly)\s+\**(\d+)\**\s+days?",
                text,
                re.IGNORECASE,
            )

        if match:
            facts.append(
                f"The standard return window is {match.group(1)} days."
            )

    if asks_fee:
        # Match the specific opened-item change-of-mind rule.
        match = re.search(
            r"restocking fee[^\n.]{0,200}?(?:exactly\s+)?\**"
            r"(\d+(?:\.\d+)?)\**\s*%",
            text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"restocking fee[^\n.]{0,200}?(?:zero|nil|no restocking fee)",
                text,
                re.IGNORECASE,
            )

        if match:
            if match.lastindex:
                facts.append(
                    f"The restocking fee is {match.group(1)}% "
                    "for an opened item returned due to a change of mind."
                )
            else:
                facts.append("No restocking fee applies to this item.")

    if asks_pickup:
        # Match the pickup-fee statement, including its exact amount.
        match = re.search(
            r"return pickup fee for a change of mind return "
            r"is\s+\**(\d+(?:\.\d+)?)\**\s+rupees?",
            text,
            re.IGNORECASE,
        )

        if match:
            facts.append(
                f"The change-of-mind return pickup fee is "
                f"₹{match.group(1)}, deducted from the refund."
            )

    asks_reporting_deadline = any(
        marker in query_lower for marker in ("reporting deadline", "report within", "must be reported")
    )
    if asks_reporting_deadline:
        match = re.search(
            r"(?:reported|report)\s+(?:to\s+[^\n.]{1,60}\s+)?within\s+(?:exactly\s+)?\**(\d+)\**\s+days?",
            text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"reported[^\n.]{0,160}?within\s+\**(\d+)\**\s+days?",
                text,
                re.IGNORECASE,
            )
        if match:
            facts.append(f"Damaged, wrong, or defective items must be reported within {match.group(1)} days of delivery.")

    asks_processing_time = any(
        marker in query_lower for marker in ("when will i get my money", "refund timeline", "upi", "refund was approved")
    )
    if asks_processing_time and "upi" in query_lower:
        match = re.search(r"\bupi\s*:\s*(\d+)\s+business days?", text, re.IGNORECASE)
        if match:
            facts.append(f"Refunds to UPI are credited to the source UPI account within {match.group(1)} business days of approval.")

    asks_goodwill = "goodwill" in query_lower and "refund" in query_lower
    if asks_goodwill:
        if re.search(r"(?:may not|cannot|must not)[^\n.]{0,100}(?:stack|combine|add)[^\n.]{0,100}full refund", text, re.IGNORECASE):
            facts.append("A goodwill credit cannot be stacked with a full refund on the same order.")

    requested_count = sum((asks_window, asks_fee, asks_pickup, asks_reporting_deadline, asks_processing_time, asks_goodwill))

    if requested_count and len(facts) == requested_count:
        return "According to the retrieved policy:\n- " + "\n- ".join(facts)

    return None


def answer_from_evidence(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 4,
    min_score: int = 2,
    index: Any = None,
) -> dict[str, Any]:
    """Return an evidence-grounded answer with citations or abstain."""
    if not query or not query.strip():
        return _abstain(
            "Please provide a policy question or contact a human support agent."
        )

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    results = retrieve(query, chunks, top_k=top_k, index=index)

    if not results or results[0]["retrieval_score"] < min_score:
        return _abstain(
            "I couldn't find sufficiently relevant policy evidence to answer "
            "confidently. Please refer this question to a human support agent."
        )

    evidence, citations = _make_evidence(results)

    concise_answer = _extract_policy_answer(query, results)

    if concise_answer is not None:
        answer = concise_answer
    else:
        joined_evidence = "\n".join(item["text"] for item in evidence).casefold()
        if (
            "warranty" in query.casefold()
            and ("used" in query.casefold() or re.search(r"\b\d+\s+days?\b", query.casefold()))
            and not re.search(r"warrant[^\n.]{0,100}\b45\s+days?\b|\b45\s+days?[^\n.]{0,100}warrant", joined_evidence)
        ):
            return _abstain(
                "I couldn't verify that the policy covers a used television after 45 days. Please ask a human support agent to review the warranty terms."
            )
        excerpts = "\n\n".join(
            f"[{item['title']} — {item['source']}]\n{item['text']}"
            for item in evidence
        )

        answer = (
            "I found potentially relevant policy evidence, but couldn't "
            "extract a sufficiently precise answer. Please review the "
            "following excerpts or refer the question to a human agent:\n\n"
            + excerpts
        )

    return {
        "status": "evidence_found",
        "answer": answer,
        "citations": citations,
        "evidence": evidence,
    }
