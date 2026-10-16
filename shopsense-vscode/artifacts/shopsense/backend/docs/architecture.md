# ShopSense architecture

## Request path

1. `POST /support/chat` accepts a customer message and optional customer/order/ticket references.
2. The LangGraph intake node parses issue type, sentiment, urgency, order reference, and claimed amount.
3. Guardrails detect prompt-injection wording, angry sentiment, product-safety terms, and legal/consumer-forum escalation.
4. The order lookup tool checks the order/customer relationship before returning shipment, refund, or fulfilment records.
5. The policy node retrieves relevant Markdown policy chunks and preserves source citations.
6. The decision node invokes deterministic refund evaluation only when the order/customer identity is verified and a reason is identifiable.
7. Risky, ambiguous-evidence, high-value, or approval-required requests pause at a LangGraph human-review interrupt. Other requests return a policy-grounded answer or a request for more information.
8. `POST /support/review` resumes a paused thread using its `thread_id` and an explicit reviewer decision.

## Components

- `agents/intake_agent.py`: deterministic typed ticket parsing.
- `agents/rag_agent.py` and `rag/`: Markdown ingestion, chunking, keyword-weighted retrieval, evidence excerpts and citations.
- `agents/action_agent.py` and `tools/actions.py`: preliminary refund policy evaluation only.
- `agents/reviewer_agent.py`: deterministic escalation signals.
- `tools/repository.py`: CSV-backed order and related-record lookup with customer ownership checks.
- `workflows/graph.py`: LangGraph routing, human interrupts, safe responses and audit events.
- `workflows/approvals.py`: validates reviewer payloads.
- `workflows/checkpoints.py`: `MemorySaver` checkpoint for a local demo.
- `tools/calculators.py` and `tools/lookups.py`: deterministic refund arithmetic and entity-scoped mock-table lookups.
- `guardrails/`: input, action-routing, and output safety helpers.
- `reliability/`: bounded retries, explicit safe fallback, and a circuit-breaker helper.
- `memory/`: bounded in-memory session context and a JSON-backed entity-scoped store.
- `observability/`: redacted structured logging and dependency-free tracing callback.
- `api/main.py`: FastAPI health, order, policy, refund-evaluation, support-chat and human-review endpoints.

## Safety boundaries

- No code in this project issues a refund or changes order data.
- Customer text is untrusted. Statements about photos, timing, parcel loss, cancellations, and return eligibility are not accepted as verified evidence by the graph.
- Order details are returned only after matching the supplied customer reference to the order's customer reference.
- Policy answers include source citations; when retrieval cannot support an answer, the system abstains or requests human review.
- The review API uses a reviewer ID supplied in the request but does not authenticate that person. It is a demo-only interface and must not be exposed publicly without authentication, authorization, and audit controls.

## Limitations

- Retrieval is keyword-weighted rather than a semantic/vector or hybrid Qdrant index.
- `MemorySaver` persists graph state only in the running process. State is lost when the process restarts; this is not a durable production checkpoint store.
- Memory and observability helpers are not yet wired into the request graph; the JSON store is local, unencrypted and not a production customer-data store.
- MCP transport, LiteLLM provider routing, and LangFuse export are not implemented as production integrations.
- The current workflow is a deterministic orchestration demo. It does not execute returns, replacements, wallet credits, or refunds.
