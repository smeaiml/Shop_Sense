
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_SET = PROJECT_ROOT / "data" / "shopsense" / "eval" / "golden_set.json"
RESULTS_FILE = PROJECT_ROOT / "evaluation" / "results.json"


def main():
    cases = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))

    if not RESULTS_FILE.exists():
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        template = [
            {
                "id": case["id"],
                "actual_route": "",
                "response": "",
            }
            for case in cases
        ]

        RESULTS_FILE.write_text(
            json.dumps(template, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"Loaded {len(cases)} golden-set cases.")
        print(f"Created response template: {RESULTS_FILE}")
        print("Next: populate actual_route and response with real outputs.")
        return

    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    results_by_id = {item["id"]: item for item in results}

    total_checks = 0
    passed_checks = 0
    evaluated_cases = 0

    for case in cases:
        result = results_by_id.get(case["id"])

        if not result or not result.get("response", "").strip():
            print(f"NOT EVALUATED: {case['id']} — no actual response")
            continue

        evaluated_cases += 1
        response = result["response"].casefold()
        failures = []

        total_checks += 1
        if result.get("actual_route") == case["expected_route"]:
            passed_checks += 1
        else:
            failures.append(
                f"Route mismatch: expected {case['expected_route']}, "
                f"got {result.get('actual_route', 'missing')}"
            )

        for citation in case.get("must_cite", []):
            total_checks += 1
            if citation.casefold() in response:
                passed_checks += 1
            else:
                failures.append(f"Missing citation: {citation}")

        for phrase in case.get("must_not_contain", []):
            total_checks += 1
            if phrase.casefold() not in response:
                passed_checks += 1
            else:
                failures.append(f"Prohibited phrase: {phrase}")

        status = "PASS" if not failures else "FAIL"
        print(f"{status}: {case['id']}")
        for failure in failures:
            print(f"  - {failure}")

    print("\n--- Evaluation summary ---")
    print(f"Golden-set cases: {len(cases)}")
    print(f"Cases evaluated: {evaluated_cases}")
    print(f"Cases not evaluated: {len(cases) - evaluated_cases}")

    if total_checks:
        print(
            f"Mechanical check pass rate: "
            f"{passed_checks}/{total_checks} "
            f"({passed_checks / total_checks * 100:.1f}%)"
        )
    else:
        print("No checks scored yet; actual responses are still needed.")

    print(
        "\nNote: Matching routes, citations, and phrases does not prove "
        "that the answer is factually correct or policy-compliant."
    )


if __name__ == "__main__":
    main()
