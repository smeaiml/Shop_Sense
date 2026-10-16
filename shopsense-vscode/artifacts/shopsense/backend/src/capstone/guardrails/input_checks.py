"""Input validation and prompt-injection signal detection."""

import re

INJECTION_PATTERNS = (
    r"ignore (?:all )?(?:previous|prior) instructions",
    r"ignore all rules",
    r"reveal (?:your )?(?:system prompt|hidden instructions)",
    r"bypass (?:the )?policy",
    r"developer message",
)


def inspect_support_input(message: str, max_length: int = 5000) -> dict[str, object]:
    """Validate a support message without treating its contents as instructions."""
    if not isinstance(message, str):
        return {"valid": False, "issues": ["message_must_be_text"], "injection_detected": False}
    issues = []
    if not message.strip():
        issues.append("message_required")
    if len(message) > max_length:
        issues.append("message_too_long")
    injection = any(re.search(pattern, message, re.IGNORECASE) for pattern in INJECTION_PATTERNS)
    return {
        "valid": not issues,
        "issues": issues,
        "injection_detected": injection,
        "normalized_message": message.strip()[:max_length],
    }
