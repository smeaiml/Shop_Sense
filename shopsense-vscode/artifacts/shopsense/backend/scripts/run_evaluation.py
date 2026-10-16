"""Run the 20-ticket acceptance suite against the real support graph."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = BACKEND_ROOT / "runtime" / "evaluation"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# Keep evaluation isolated from the live demo store and exclude the expected
# labels from the model input. The graph receives only each case's question.
os.environ.setdefault("SHOP_SENSE_DB_PATH", str(RUNTIME_DIR / "shopsense-evaluation.sqlite3"))
os.environ.setdefault("SHOP_SENSE_RUNTIME_DIR", str(RUNTIME_DIR))
os.environ["LLM_PROVIDER"] = "rules"
os.environ["LLM_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from capstone.workflows.graph import invoke_support  # noqa: E402


def _route(result: dict[str, Any]) -> str:
    if result.get("status") == "refused":
        return "refuse"
    if result.get("requires_human") or result.get("status") in {
        "pending_human_review", "pending_approval", "action_pending",
    }:
        return "human_review"
    return "auto"


def run(output_path: Path) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    cases = json.loads(
        (BACKEND_ROOT / "data" / "shopsense" / "eval" / "golden_set.json").read_text(encoding="utf-8")
    )
    results: list[dict[str, Any]] = []

    for case in cases:
        # Labels (expected answer, route, citations, and prohibited terms) are
        # used only after inference; none is passed to invoke_support.
        result = invoke_support(
            message=case["question"],
            ticket_id=f"evaluation-{run_id}-{case['id']}",
        )
        response = str(result.get("response") or "")
        response_lower = response.casefold()
        titles = [
            str(item.get("title") or "")
            for item in result.get("citations", [])
            if isinstance(item, dict)
        ]
        missing_citations = [
            expected
            for expected in case.get("must_cite", [])
            if not any(expected.casefold() in title.casefold() for title in titles)
        ]
        prohibited = [
            term
            for term in case.get("must_not_contain", [])
            if term.casefold() in response_lower
        ]
        actual_route = _route(result)
        case_result = {
            "id": case["id"],
            "expected_route": case.get("expected_route"),
            "actual_route": actual_route,
            "status": result.get("status"),
            "decision": result.get("decision"),
            "route_pass": actual_route == case.get("expected_route"),
            "citations": titles,
            "missing_citations": missing_citations,
            "prohibited_terms_found": prohibited,
            "pass": (
                actual_route == case.get("expected_route")
                and not missing_citations
                and not prohibited
            ),
            "response": response,
            "errors": result.get("errors", []),
        }
        results.append(case_result)

    total = len(results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": total,
        "passed": sum(bool(item["pass"]) for item in results),
        "route_accuracy": (
            sum(bool(item["route_pass"]) for item in results) / total if total else 0
        ),
        "citation_checks_passed": sum(not item["missing_citations"] for item in results),
        "prohibited_term_checks_passed": sum(not item["prohibited_terms_found"] for item in results),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=RUNTIME_DIR / "latest.json",
        help="Path for the full JSON report (defaults to an ignored runtime file).",
    )
    args = parser.parse_args()
    summary = run(args.output)
    print(
        f"Passed {summary['passed']}/{summary['cases']} cases; "
        f"route accuracy {summary['route_accuracy']:.0%}; "
        f"citation checks {summary['citation_checks_passed']}/{summary['cases']}; "
        f"prohibited-term checks {summary['prohibited_term_checks_passed']}/{summary['cases']}. "
        f"Report: {args.output}"
    )
    for item in summary["results"]:
        if not item["pass"]:
            print(
                f"FAIL {item['id']}: route={item['actual_route']}/{item['expected_route']}; "
                f"missing_citations={item['missing_citations']}; "
                f"prohibited={item['prohibited_terms_found']}"
            )
