from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from scripts.query_parser import QueryParser


INPUT_FILE = Path("data/processed/week4_query_examples.csv")
METRICS_FILE = Path("data/processed/week4_parser_metrics.json")
FAILURES_FILE = Path("data/processed/week4_parser_failures.csv")


def normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:

    normalized = dict(filters)

    for key in ("amenities", "excluded_amenities"):
        if key in normalized and isinstance(normalized[key], list):
            normalized[key] = sorted(normalized[key])

    return normalized


def load_examples(path: Path) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. "
            "Place week4_query_examples.csv in data/processed/."
        )

    examples: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"query", "expected_filters"}
        missing = required_columns - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}"
            )

        for row_number, row in enumerate(reader, start=2):
            query = (row.get("query") or "").strip()
            expected_text = (row.get("expected_filters") or "").strip()

            if not query:
                raise ValueError(f"Missing query on CSV row {row_number}")

            try:
                expected_filters = json.loads(expected_text)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid expected_filters JSON on CSV row {row_number}: "
                    f"{expected_text}"
                ) from error

            examples.append(
                {
                    "row": row_number,
                    "query": query,
                    "expected": expected_filters,
                }
            )

    return examples


def evaluate(
    parser: QueryParser,
    examples: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:

    correct = 0
    failures: list[dict[str, Any]] = []

    for example in examples:
        query = example["query"]
        expected = normalize_filters(example["expected"])

        try:
            predicted = normalize_filters(parser.parse(query))
            error_message = ""
        except Exception as error:
            predicted = {}
            error_message = f"{type(error).__name__}: {error}"

        is_correct = not error_message and predicted == expected

        if is_correct:
            correct += 1
        else:
            failures.append(
                {
                    "row": example["row"],
                    "query": query,
                    "expected": expected,
                    "predicted": predicted,
                    "error": error_message,
                }
            )

    total = len(examples)
    accuracy = correct / total if total else 0.0

    metrics = {
        "correct": correct,
        "incorrect": total - correct,
        "total": total,
        "accuracy": round(accuracy, 4),
        "accuracy_percent": round(accuracy * 100, 2),
        "target_percent": 90.0,
        "target_met": accuracy >= 0.90,
    }

    return metrics, failures


def save_metrics(metrics: dict[str, Any], path: Path) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)


def save_failures(failures: list[dict[str, Any]], path: Path) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["row", "query", "expected", "predicted", "error"],
        )
        writer.writeheader()

        for failure in failures:
            writer.writerow(
                {
                    "row": failure["row"],
                    "query": failure["query"],
                    "expected": json.dumps(
                        failure["expected"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "predicted": json.dumps(
                        failure["predicted"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "error": failure["error"],
                }
            )


def print_results(
    metrics: dict[str, Any],
    failures: list[dict[str, Any]],
) -> None:
    """Display the evaluation results in the terminal."""
    print("\nQuery Parser Evaluation")
    print("=" * 30)
    print(f"Correct:   {metrics['correct']}")
    print(f"Incorrect: {metrics['incorrect']}")
    print(f"Total:     {metrics['total']}")
    print(f"Accuracy:  {metrics['accuracy_percent']:.2f}%")
    print(
        "90% target: "
        + ("PASSED" if metrics["target_met"] else "NOT YET PASSED")
    )

    if failures:
        print("\nFailed examples")
        print("-" * 30)

        for failure in failures:
            print(f"\nQuery:     {failure['query']}")
            print(f"Expected:  {failure['expected']}")
            print(f"Predicted: {failure['predicted']}")

            if failure["error"]:
                print(f"Error:     {failure['error']}")
    else:
        print("\nAll examples passed.")


def main() -> None:
    examples = load_examples(INPUT_FILE)
    parser = QueryParser()

    metrics, failures = evaluate(parser, examples)

    save_metrics(metrics, METRICS_FILE)
    save_failures(failures, FAILURES_FILE)
    print_results(metrics, failures)

    print(f"\nMetrics saved to:  {METRICS_FILE}")
    print(f"Failures saved to: {FAILURES_FILE}")


if __name__ == "__main__":
    main()
