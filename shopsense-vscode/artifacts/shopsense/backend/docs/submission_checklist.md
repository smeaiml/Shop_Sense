# Submission checklist

## Before packaging
- [ ] Run `python -m pip install -e ".[dev]"` in the target environment.
- [ ] Run `python -m pytest -q` and save the actual output.
- [ ] Start the API with `python -m uvicorn capstone.api.main:app --reload`.
- [ ] Open `/docs` and demonstrate `/support/chat`, `/support/review`, `/policy/ask`, and `/refunds/evaluate`.
- [ ] Demonstrate cross-customer order denial, policy citations, and a human-review interrupt/resume.
- [ ] Keep `data/shopsense/eval/golden_set.json` unchanged.
- [ ] Run the golden-set evaluation only with real outputs; report cases not evaluated and all failures.
- [ ] Keep `.env`, API keys, `.venv`, `.git`, and caches out of the submitted ZIP.

## Submission contents
- Source code under `src/capstone/`
- Existing synthetic ShopSense data under `data/shopsense/`
- Tests under `tests/`
- Setup and demo steps in `docs/`
- Evaluation report in `docs/evaluation_report.md`
- Presentation in `presentation/ShopSense_Capstone_Presentation.pptx`

## Demo safety
This is a local demonstration. The human-review endpoint has no authentication and checkpoint state is in-memory. Do not expose the service publicly or claim a refund was actually executed.
