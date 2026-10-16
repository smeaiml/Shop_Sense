"""Response safety checks for unsupported transactional claims."""

import re
from typing import Any

UNSUPPORTED_CLAIM_PATTERNS = (
    r"(?<!no )(?<!not )your refund (?:has been|was|is) approved",
    r"refund (?:has been|is being) processed",
    r"refund issued",
    r"wallet credit (?:has been|was) added",
)


def check_response_safety(
    response: str,
    *,
    citations: list[dict[str, Any]] | None = None,
    require_citations: bool = False,
) -> dict[str, Any]:
    """Flag unsupported claims that a transaction occurred or missing citations."""
    text = response or ""
    lowered = text.casefold()
    violations = [
        pattern for pattern in UNSUPPORTED_CLAIM_PATTERNS
        if re.search(pattern, lowered)
    ]
    missing_citations = require_citations and not citations
    if missing_citations:
        violations.append("citations_required")
    return {
        "safe": not violations,
        "violations": violations,
        "response": text,
    }
