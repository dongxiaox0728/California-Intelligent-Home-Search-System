"""
    Interactive query-parser playground. Does not connect to a database.
    Run from any directory:
    python3 /path/to/IDX-nlp/scripts/try_query_parser.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add the project folder so Python can find scripts/query_parser.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.query_parser import QueryParser


EXAMPLES = (
    "3 bedrooms under 700k in Irvine with a pool",
    "around 200k with no garage",
    "condo in Irvine with at least 2 bathrooms and 1800 sqft",
    "under 250k around 200k with a patio and quiet neighborhood",
    "preferably a pool and no garage",
)


def show_result(parser: QueryParser, query: str) -> None:
    try:
        result = parser.parse(query)
        print("\nParsed result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        print(f"\nCould not parse query: {exc}")
    print()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    args_parser = argparse.ArgumentParser(description=__doc__)
    args_parser.add_argument("--query", help="Parse one query and exit.")
    args_parser.add_argument("--listings", type=Path,
                             default=project_root / "data/processed/listing_sample_cleaned.csv")
    args_parser.add_argument("--amenities", type=Path,
                             default=project_root / "taxonomy/taxonomy_week1.json")
    args = args_parser.parse_args()
    parser = QueryParser(listings_path=args.listings, amenities_path=args.amenities)
    if not parser.valid_cities:
        print(f"Note: no cities loaded from {args.listings}; city recognition is unavailable.")
    if not args.amenities.is_file():
        print(f"Note: taxonomy not found at {args.amenities}; built-in amenities and aliases are used.")
    if args.query is not None:
        show_result(parser, args.query)
        return

    print("Query parser playground")
    print("Enter a query, or use :examples, :help, or :quit.")
    print("This tool displays parsed conditions, ranking rules and semantic text.\n")
    while True:
        try:
            query = input("Query > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not query:
            continue
        command = query.lower()
        if command in {":quit", ":exit"}:
            break
        if command == ":help":
            print(":examples  Show sample queries\n:quit      Exit\n")
        elif command == ":examples":
            for example in EXAMPLES:
                print(f"  {example}")
            print()
        else:
            show_result(parser, query)


if __name__ == "__main__":
    main()
