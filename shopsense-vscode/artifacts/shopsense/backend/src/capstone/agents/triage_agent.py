"""Validated support-ticket triage specialist."""

from capstone.agents.intake_agent import parse_ticket, sanitize_customer_message


class TriageAgent:
    def run(self, message: str, *, ticket_id: str | None = None, customer_id: str | None = None):
        safe_message, has_injection = sanitize_customer_message(message)
        ticket = parse_ticket(message, ticket_id=ticket_id, customer_id=customer_id)
        return ticket, safe_message, has_injection
