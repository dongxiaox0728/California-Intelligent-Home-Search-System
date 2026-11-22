"""
    Interactive weighted search: parser -> hard filter -> both scores -> top 100.

    Run from any directory with the project's virtual environment:
        python3 tests/try_weighted_search.py
        python3 tests/try_weighted_search.py --query "condo in Irvine with a pool"

    Requires the generated index/metadata/manifests, MySQL, and OPENAI_API_KEY in
        .env for the default LLM cleanup. Use --no-llm to check offline query parsing.
        Uses equal weights when both preferences exist, returns up to 100 actual listings,
        and displays the top 10 by default. Use --display-limit 100 to show all results.
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


def run_query(query, parser, hard_filter, searcher, display_limit=10):
    from scripts.weighted_ranker import WeightedRanker

    if isinstance(display_limit, bool) or not isinstance(display_limit, int) or display_limit <= 0:
        raise ValueError("display_limit must be a positive integer.")
    started = perf_counter()
    parsed = parser.parse(query)
    print("\n1. Parsed query")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    eligible = hard_filter.filter(parsed)
    print(f"\n2. Hard filter: {len(eligible):,} database rows matched.")
    if not eligible:
        print("No matches. Hard constraints have not been relaxed.")
        return []
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
        print(f"Note: {len(excluded):,} eligible IDs are outside the indexed CSV snapshot. "
              "Only the indexed subset can be searched; check export coverage if unexpected.")
    if not searchable_ids:
        print("No eligible listings are present in the index.")
        return []
    indexed_eligible = [row for row in eligible if str(row['L_ListingID']).strip() in searchable_ids]
    print("\n3. Score every eligible indexed listing, then select the top 100.")
    print("Both preferences present: 0.5 semantic + 0.5 structured. "
          "One present: use it alone. Neither: stable index order.")
    results = WeightedRanker(searcher).rank(indexed_eligible, parsed)
    result_ids = [str(row['L_ListingID']).strip() for row in results]
    if len(results) != min(100, len(searchable_ids)):
        raise AssertionError("Unexpected result count.")
    if len(result_ids) != len(set(result_ids)) or not set(result_ids) <= searchable_ids:
        raise AssertionError("Duplicate or ineligible result.")
    if [row['rank'] for row in results] != list(range(1, len(results) + 1)):
        raise AssertionError("Incorrect final ranks.")
    scores = [row['final_score'] for row in results]
    if any(score is not None for score in scores):
        if not all(score is not None and math.isfinite(score) for score in scores):
            raise AssertionError("Invalid final scores.")
        if any(left < right for left, right in zip(scores, scores[1:])):
            raise AssertionError("Final scores are not ordered highest first.")
    def label(score):
        return 'not scored' if score is None else f'{score:.4f}'
    visible = results[:display_limit]
    print(f"\n4. Showing top {len(visible)} of {len(results)} ranked results")
    for row in visible:
        print(f"\nRank {row['rank']} | ID: {row['L_ListingID']} | "
              f"Final: {label(row['final_score'])} | Semantic: {label(row['similarity_score'])} | "
              f"Structured: {label(row['structured_score'])}")
        print(f"Address: {row.get('L_Address', 'N/A')} | City: {row.get('L_City', 'N/A')}")
        print(f"Price: {row.get('price', 'N/A')} | Beds: {row.get('bedrooms', 'N/A')} | "
              f"Baths: {row.get('bathrooms', 'N/A')} | Sqft: {row.get('sqft', 'N/A')}")
        for rule in row['rule_scores']:
            print(f"  {rule['field']} ({rule['direction']}): value={rule['value']}, "
                  f"reference={rule['reference']}, score={rule['score']:.4f}")
        print(f"Remarks: {row.get('L_Remarks', row.get('remarks', row.get('cleaned_remarks', '')))}")
    print(f"\nChecks passed: result eligibility, count, uniqueness, ranks and final score order. "
          f"Query took {perf_counter() - started:.2f}s, excluding model/index startup.")
    print("Review remarks to judge relevance; scores are not probabilities.")
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--query", help="Run one query and exit; otherwise start an interactive session.")
    cli.add_argument("--no-llm", action="store_true", help="Use rule-based semantic cleanup without an API call.")
    cli.add_argument("--display-limit", type=int, default=10, help="Number of results to display (default: 10); ranking still returns up to 100.")
    args = cli.parse_args()
    if args.display_limit <= 0:
        cli.error("--display-limit must be positive")

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
            run_query(args.query, parser, hard_filter, searcher, args.display_limit)
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
            run_query(query, parser, hard_filter, searcher, args.display_limit)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        except (ValueError, AssertionError) as exc:
            print(f"Test failed: {exc}")
        except Exception as exc:
            print(f"Test failed ({type(exc).__name__}). Check MySQL and API connectivity.")


if __name__ == "__main__":
    main()
