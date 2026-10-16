# ShopSense milestone checklist

Status is intentionally conservative: a checked item means the implementation is present in this repository, not that it is production-ready.

| Milestone | Current evidence | Status / limitation |
|---|---|---|
| M1 Intake | Pydantic `SupportTicket`; rule-based issue/sentiment/urgency/amount parsing; missing fields and injection flags; unit tests | Implemented baseline. Not provider-agnostic LLM intake. |
| M2 Tools | CSV-backed order lookup with ownership check; deterministic preliminary refund evaluation | Implemented baseline. No transaction side effects. |
| M3 Memory/index | Markdown ingestion/chunking; bounded session memory and JSON-backed entity-scoped memory helpers | Partial. Memory helpers are not integrated into the graph; no vector index. |
| M4 RAG | Keyword-weighted retrieval, evidence chunks, citations and abstention; RAG tests | Partial. No Qdrant, semantic embeddings, hybrid search or reranking. |
| M5 Workflow/checkpointing | LangGraph intake, guardrails, order lookup, policy retrieval, decision routing, human interrupt/resume | Implemented local demo. `MemorySaver` is process-local, not durable across restarts. |
| M6 Multi-agent/MCP | Intake, RAG, action and reviewer modules; shared deterministic business functions | Partial. Specialist modules are thin and MCP transport is not implemented. |
| M7 Reliability/observability | Bounded retry, safe fallback, circuit breaker, redacted structured logging, tracing callback, workflow audit events | Partial. Helpers are not wired into every dependency; no LangFuse export or comprehensive failure-injection suite. |
| M8 Evaluation/API/guardrails | FastAPI endpoints, unit/integration tests, golden-set evaluator template | Partial. Golden-set responses still need to be generated and evaluated; no measured golden-set score is claimed. |

## Verification commands

```powershell
python -m pytest -q
python -m uvicorn capstone.api.main:app --reload
```

The evaluator in `scripts/evaluate_golden_set.py` checks only populated real responses against expected routes, required citations, and prohibited phrases. Do not fill `evaluation/results.json` with invented responses or scores.
