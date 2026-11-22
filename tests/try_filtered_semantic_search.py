"""
    Manual end-to-end check: parser -> MySQL hard filter -> semantic ranking.

    Run from any directory with the project's virtual environment:
        python3 tests/try_filtered_semantic_search.py
        python3 tests/try_filtered_semantic_search.py --query "condo in Irvine with a pool" --top-k 5

    Requires the generated index/metadata/manifests, MySQL, and OPENAI_API_KEY in
        .env for the default LLM cleanup. Use --no-llm to check offline query parsing.
        Numeric ranking_rules are displayed but are not applied in this semantic test.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_query(query, parser, hard_filter, searcher, top_k):
    started = perf_counter()
    parsed = parser.parse(query)
    print("\n1. Parsed query")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    if parsed["structured_filters"].get("ranking_rules"):
        print("Numeric ranking rules are not applied yet; results use semantic similarity only.")

    eligible = hard_filter.filter(parsed)
    print(f"\n2. Hard filter: {len(eligible):,} database rows matched.")
    if not eligible:
        print("No matches. Hard constraints have not been relaxed.")
        return []

    # The CSV export includes only listings with sufficiently long remarks.
    # Report database matches outside that snapshot instead of silently dropping them.
    indexed_ids = set(searcher.metadata["L_ListingID"].str.strip())
    eligible_ids = set()
    for listing in eligible:
        value = listing.get("L_ListingID")
        if value is None or not str(value).strip():
            raise ValueError("A database match has no listing ID.")
        eligible_ids.add(str(value).strip())
    searchable_ids = eligible_ids & indexed_ids
    excluded = eligible_ids - indexed_ids
    print(f"Unique eligible IDs: {len(eligible_ids):,}; present in index: {len(searchable_ids):,}.")
    if excluded:
        print(f"Note: {len(excluded):,} eligible IDs are outside the indexed CSV snapshot "
              "(for example, listings excluded by the remarks-length requirement). "
              "This test searches only the indexed subset.")
    if not searchable_ids:
        print("No eligible listings are present in the index. Check the CSV/database snapshot.")
        return []

    semantic_text = parsed["semantic_words"]
    print(f"\n3. Semantic text: {semantic_text!r}")
    if not semantic_text.strip():
        print("No semantic preferences: skipping embedding; results use stable index order.")
    results = searcher.search_eligible(
        query=semantic_text, eligible_ids=sorted(searchable_ids), top_k=top_k,
    )

    # Verify eligibility, count, uniqueness, ranks, and score order independently
    # of what the display looks like. Semantic relevance still needs human review.
    result_ids = [str(row["L_ListingID"]).strip() for row in results]
    if len(results) != min(top_k, len(searchable_ids)):
        raise AssertionError("Unexpected number of results.")
    if len(result_ids) != len(set(result_ids)) or not set(result_ids) <= searchable_ids:
        raise AssertionError("Duplicate or ineligible listing in results.")
    if [row["rank"] for row in results] != list(range(1, len(results) + 1)):
        raise AssertionError("Incorrect result ranks.")
    scores = [row["similarity_score"] for row in results]
    if semantic_text.strip():
        if not all(score is not None and math.isfinite(score) for score in scores):
            raise AssertionError("Invalid semantic scores.")
        if any(left < right for left, right in zip(scores, scores[1:])):
            raise AssertionError("Scores are not ordered highest first.")
    elif any(score is not None for score in scores):
        raise AssertionError("Empty semantic text should not receive similarity scores.")

    print("\n4. Final results")
    for row in results:
        score = row["similarity_score"]
        score_label = "not scored" if score is None else f"{score:.4f}"
        print(f"\nRank {row['rank']} | Similarity: {score_label} | ID: {row['L_ListingID']}")
        print(f"Address: {row.get('L_Address', 'N/A')} | City: {row.get('L_City', 'N/A')}")
        print(f"Price: {row.get('price', 'N/A')} | Beds: {row.get('beds', 'N/A')} | "
              f"Baths: {row.get('baths', 'N/A')}")
        print(f"Remarks: {row.get('remarks', row.get('cleaned_remarks', ''))}")
    print(f"\nChecks passed: eligible IDs, result count, unique IDs, ranks and score order. "
          f"Query took {perf_counter() - started:.2f}s (excluding initial model/index loading).")
    print("Review the remarks yourself to judge relevance; similarity is not a probability.")
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--query", help="Run one query and exit; otherwise start an interactive session.")
    cli.add_argument("--top-k", type=int, default=5)
    cli.add_argument("--no-llm", action="store_true", help="Use rule-based semantic cleanup without an API call.")
    args = cli.parse_args()
    if args.top_k <= 0:
        cli.error("--top-k must be positive")

    # Deferred imports allow --help to work without loading the ML libraries.
    try:
        from scripts.query_parser import QueryParser
        from scripts.hard_constraints_filter import HardConstraintsFilter
        from scripts.semantic_searcher import SemanticSearcher
        parser = QueryParser(llm_cleanup=not args.no_llm)
        print(f"City lookup: {parser.city_source} ({len(parser.valid_cities):,} names)")
        if not parser.valid_cities:
            raise ValueError("No city names loaded. Start the database and restart this test.")
        hard_filter = HardConstraintsFilter()
        searcher = SemanticSearcher()
        searcher.load()
    except Exception as exc:
        # Avoid printing connection strings, credentials, or API response bodies.
        cli.exit(1, f"Setup failed ({type(exc).__name__}). Check dependencies, generated artifacts, "
                 "Docker/MySQL, and the project's .env settings.\n")

    if args.query is not None:
        try:
            run_query(args.query, parser, hard_filter, searcher, args.top_k)
        except (ValueError, AssertionError) as exc:
            cli.exit(1, f"Test failed: {exc}\n")
        except Exception as exc:
            cli.exit(1, f"Test failed ({type(exc).__name__}). Check MySQL, API connectivity and model files.\n")
        return
    print("\nEnter a property search, or :quit to exit.")
    while True:
        try:
            query = input("\nQuery > ").strip()
            if query.lower() in {":quit", ":exit"}:
                break
            if not query:
                continue
            run_query(query, parser, hard_filter, searcher, args.top_k)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        except (ValueError, AssertionError) as exc:
            print(f"Test failed: {exc}")
        except Exception as exc:
            print(f"Test failed ({type(exc).__name__}). Check MySQL and API connectivity.")


if __name__ == "__main__":
    main()
