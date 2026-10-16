# ShopSense evaluation report

## Scope

This report describes the local deterministic workflow and the tests in this repository. It does not claim a golden-set benchmark score.

## Existing automated checks

Latest development-sandbox run after implementing the workflow and integration tests: **55 passed**. Re-run the test suite in the target Windows environment before submission, because the uploaded Windows virtual environment itself is not portable to this Linux sandbox.

The project includes unit tests for:
- Intake parsing and missing-field handling.
- Customer-scoped order lookup.
- Refund eligibility and approval-tier routing.
- Policy retrieval, citations, and abstention.
- FastAPI health, order, policy, and refund-evaluation endpoints.

Workflow integration tests are in `tests/test_workflow.py`. They require the declared LangGraph dependency. Run the full suite in the same environment used for the demo:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

Record the exact final output and date here after running the tests in the submission environment.

## Golden set

`data/shopsense/eval/golden_set.json` contains the 20 provided evaluation cases. `scripts/evaluate_golden_set.py` creates a response template if none exists and scores populated real outputs for route match, required citations, and prohibited phrases.

**Golden-set status: not scored in this report.** No actual system outputs have been populated and independently checked here, so no golden-set accuracy or safety pass rate is claimed. Route/citation/phrase matching is a mechanical check, not proof of factual correctness.

## Known limitations and risks

- Keyword-weighted retrieval is not semantic/vector retrieval.
- Customer-provided evidence is not considered verified by the graph; requests can pause for human review or request more information.
- Human review uses a caller-supplied reviewer ID and is not authenticated.
- Checkpoints use in-memory storage and are lost on process restart.
- The demo never issues refunds or executes other transactional actions.
- Dataset inconsistencies noted by the supplied validator should be disclosed; do not regenerate the frozen dataset for the final run.

## Reproducibility

- Python: use Python 3.10+.
- Install: `python -m pip install -e ".[dev]"`.
- Tests: `python -m pytest -q`.
- API: `python -m uvicorn capstone.api.main:app --reload`.
- Data: use the existing `data/shopsense/` corpus, mock tables, and golden set; do not regenerate during final evaluation.
