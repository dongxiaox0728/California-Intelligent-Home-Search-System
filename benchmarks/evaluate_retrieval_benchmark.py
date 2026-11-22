#!/usr/bin/env python3
"""
    Compare retrieval rankings using saved, independently assigned relevance grades.

    Run from the project root:
    python3 benchmarks/evaluate_retrieval_benchmark.py

    Standard library only. No models, database, or API calls are used.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_RUN = Path(__file__).resolve().parent / "retrieval_v1/runs/comparison_local"


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def grade(value: str) -> int:
    result = int(value)
    if result not in range(4):
        raise ValueError(f"Relevance grade must be 0, 1, 2 or 3; received {value!r}")
    return result


def dcg(grades: list[int]) -> float:
    return sum((2 ** value - 1) / math.log2(rank + 1)
               for rank, value in enumerate(grades, start=1))


def mean_available(values) -> float | None:
    usable = [value for value in values if value is not None]
    return statistics.mean(usable) if usable else None


def evaluate(input_path: Path, judgments_path: Path, queries_path: Path,
             k: int = 10, relevant_min: int = 2):
    if k < 1 or relevant_min not in (1, 2, 3):
        raise ValueError("k must be positive and relevant-min must be 1, 2 or 3")
    labels = {}
    pools = defaultdict(list)
    for row in read_csv(judgments_path, {"query_id", "listing_id", "relevance_grade"}):
        key = (row["query_id"], row["listing_id"])
        if not all(key) or key in labels:
            raise ValueError(f"Blank or duplicate judgment key: {key}")
        labels[key] = grade(row["relevance_grade"])
        pools[key[0]].append(labels[key])
    if not labels:
        raise ValueError("The pooled judgments file is empty")

    categories = {}
    if queries_path.exists():
        for line in queries_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            query = json.loads(line)
            qid = query["query_id"]
            if qid in categories:
                raise ValueError(f"Duplicate query definition: {qid}")
            categories[qid] = query.get("category", "unspecified")

    grouped = defaultdict(list)
    ranks, listing_keys = set(), set()
    systems, query_ids = set(), set()
    needs_review = unreviewed = 0
    for row in read_csv(input_path, {"query_id", "system", "listing_id", "rank",
                                     "relevance_grade", "hard_constraints_met"}):
        rank = int(row["rank"])
        if rank < 1:
            raise ValueError("Result ranks must start at 1")
        if rank > k:
            continue
        qid, system, listing = row["query_id"], row["system"], row["listing_id"]
        if not all((qid, system, listing)):
            raise ValueError("Query, system and listing identifiers cannot be blank")
        rank_key, listing_key = (qid, system, rank), (qid, system, listing)
        if rank_key in ranks or listing_key in listing_keys:
            raise ValueError(f"Duplicate rank or listing in {qid}/{system}")
        ranks.add(rank_key)
        listing_keys.add(listing_key)
        value = grade(row["relevance_grade"])
        if "is_judged" in row and row["is_judged"].strip().lower() != "true":
            raise ValueError(f"Unjudged result at {qid}/{system}/{rank}")
        if labels.get((qid, listing)) != value:
            raise ValueError(f"Missing or inconsistent pooled grade for {qid}/{listing}")
        met = row["hard_constraints_met"].strip().lower()
        if met not in ("true", "false"):
            raise ValueError(f"Unknown hard-constraint status for {qid}/{listing}")
        if met == "false" and value != 0:
            raise ValueError(f"Hard-requirement failure must have grade 0: {qid}/{listing}")
        grouped[(qid, system)].append((rank, value, met == "false"))
        systems.add(system)
        query_ids.add(qid)
        needs_review += row.get("review_needed", "").lower() == "true"
        unreviewed += row.get("human_reviewed", "false").lower() != "true"

    if not grouped:
        raise ValueError("No ranked results to evaluate")
    expected_queries = set(categories) if categories else query_ids
    if categories and query_ids - expected_queries:
        raise ValueError("Rankings contain queries absent from the query definitions")
    # This CSV-based evaluator cannot distinguish a legitimate empty result set
    # from a missing run, so it refuses to silently award a zero for absent groups.
    missing = [(qid, system) for qid in sorted(expected_queries)
               for system in sorted(systems) if (qid, system) not in grouped]
    if missing:
        raise ValueError(f"Missing query/system groups (empty runs need explicit handling): {missing[:5]}")

    per_query = []
    for (qid, system), results in sorted(grouped.items()):
        results.sort()
        if [r[0] for r in results] != list(range(1, len(results) + 1)):
            raise ValueError(f"Ranks must be contiguous from 1: {qid}/{system}")
        values = [r[1] for r in results]
        actual_dcg = dcg(values)
        # Both systems use the SAME ideal ordering from the full judged pool.
        ideal_dcg = dcg(sorted(pools[qid], reverse=True)[:k])
        relevant = sum(value >= relevant_min for value in values)
        violations = sum(r[2] for r in results)
        per_query.append({
            "query_id": qid, "category": categories.get(qid, "unspecified"),
            "system": system, "returned_count": len(results),
            "relevant_count": relevant, "violation_count": violations,
            "dcg_at_k": actual_dcg, "ideal_dcg_at_k": ideal_dcg,
            "ndcg_at_k": actual_dcg / ideal_dcg if ideal_dcg else None,
            "precision_at_k": relevant / k,
            "violation_rate_at_k": violations / len(results),
        })

    summaries = []
    scopes = ["overall"] + sorted({r["category"] for r in per_query})
    for scope in scopes:
        for system in sorted(systems):
            group = [r for r in per_query if r["system"] == system
                     and (scope == "overall" or r["category"] == scope)]
            summaries.append({
                "scope": scope, "system": system, "query_count": len(group),
                "ndcg_query_count": sum(r["ndcg_at_k"] is not None for r in group),
                "mean_ndcg_at_k": mean_available(r["ndcg_at_k"] for r in group),
                "mean_precision_at_k": mean_available(r["precision_at_k"] for r in group),
                "mean_violation_rate_at_k": mean_available(r["violation_rate_at_k"] for r in group),
                "returned_count": sum(r["returned_count"] for r in group),
                "violation_count": sum(r["violation_count"] for r in group),
            })
    meta = {"k": k, "relevant_min": relevant_min, "query_count": len(expected_queries),
            "systems": sorted(systems), "input": str(input_path.resolve()),
            "judgments": str(judgments_path.resolve()),
            "top_k_result_rows": sum(r["returned_count"] for r in per_query),
            "review_flagged_result_rows": needs_review,
            "not_human_reviewed_result_rows": unreviewed,
            "definitions": {
                "gain": "2**grade - 1", "discount": "log2(rank + 1)",
                "ideal": "Shared ideal from each query's full judged pool, limited to k",
                "precision": "Count of grade >= relevant_min divided by k; missing slots are non-relevant",
                "violations": "Hard-constraint failures divided by actual returned results within k",
                "averaging": "Equal weight per query (macro average)",
                "zero_ideal": "nDCG is undefined and excluded when the pool has no positive grades; other metrics retained",
            }}
    return per_query, summaries, meta


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_RUN / "top10_with_grades.csv")
    parser.add_argument("--judgments", type=Path, help="Full graded pool; defaults beside --input")
    parser.add_argument("--queries", type=Path, help="Query definitions; defaults beside --input")
    parser.add_argument("--output", type=Path, help="Report directory; defaults to evaluation/ beside --input")
    parser.add_argument("--k", type=int, choices=range(1, 11), default=10,
                        help="Evaluation cutoff, 1–10 (this benchmark pool covers top 10)")
    parser.add_argument("--relevant-min", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    judgments = args.judgments or args.input.parent / "judging_pool_graded.csv"
    queries = args.queries or args.input.parent / "queries_input.jsonl"
    output = args.output or args.input.parent / "evaluation"
    try:
        per_query, summary, meta = evaluate(args.input, judgments, queries, args.k, args.relevant_min)
        output.mkdir(parents=True, exist_ok=True)
        write_csv(output / "metrics_per_query.csv", per_query)
        write_csv(output / "metrics_summary.csv", summary)
        (output / "evaluation.json").write_text(json.dumps({**meta, "summary": summary}, indent=2) + "\n")
    except (OSError, ValueError, KeyError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(f"\nRetrieval evaluation: {meta['query_count']} queries, top {args.k}")
    print(f"Relevant = grade {args.relevant_min}–3. Higher nDCG/precision is better; lower violation rate is better.\n")
    print(f"{'Scope':<29} {'System':<12} {'nDCG':>9} {'Precision':>11} {'Violations':>12}")
    print("-" * 78)
    def fmt(value):
        return "n/a" if value is None else f"{value:.4f}"
    for row in summary:
        print(f"{row['scope']:<29} {row['system']:<12} {fmt(row['mean_ndcg_at_k']):>9} "
              f"{fmt(row['mean_precision_at_k']):>11} {fmt(row['mean_violation_rate_at_k']):>12}")
    overall = {r["system"]: r for r in summary if r["scope"] == "overall"}
    if "baseline" in overall and "new" in overall:
        print("\nOverall change (new minus baseline):")
        for key, name in [("mean_ndcg_at_k", "nDCG"), ("mean_precision_at_k", "Precision"),
                          ("mean_violation_rate_at_k", "Violation rate")]:
            a, b = overall["new"][key], overall["baseline"][key]
            print(f"  {name}: {'n/a' if a is None or b is None else f'{a - b:+.4f}'}")
    skipped = {r["query_id"] for r in per_query if r["ndcg_at_k"] is None}
    if skipped:
        print(f"\nnDCG undefined for {len(skipped)} all-zero judged pools; excluded from nDCG averages.")
    if meta["not_human_reviewed_result_rows"]:
        print("\nLabel status: provisional AI judgments; review before final benchmark claims.")
    print(f"Reports saved to: {output.resolve()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
