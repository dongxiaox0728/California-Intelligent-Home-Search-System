"""
    Interactive full pipeline test: retrieves the top 10 actual listings.

    Run: python3 tests/try_search_orchestrator.py
    One query: python3 tests/try_search_orchestrator.py --query "condo in Irvine with a pool"
    Newest fallback uses ListingContractDate. Override via LISTING_DATE_COLUMN
    in .env or --date-column COLUMN if needed.
    The orchestrator's normal default is 100; this test explicitly requests 10.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def show_query(orchestrator, query):
    started = perf_counter()
    report = orchestrator.search(query, top_k=10)
    print('\nParsed query:')
    print(json.dumps(report['parsed_query'], indent=2, ensure_ascii=False))
    print(f"\nRanking path: {report['mode']} | Eligible: {report['eligible_count']:,} | "
          f"Candidates scored: {report['candidate_count']:,} | Returned: {len(report['results'])}")
    for warning in report['warnings']:
        print(f'Note: {warning}')
    def grade(value):
        return 'not scored' if value is None else f'{value:.4f}'
    for row in report['results']:
        print(f"\nRank {row['rank']} | ID: {row['L_ListingID']} | Final: {grade(row['final_score'])}")
        print(f"Semantic: {grade(row['similarity_score'])} | Structured: {grade(row['structured_score'])}")
        print(f"Address: {row.get('L_Address', 'N/A')} | City: {row.get('L_City', 'N/A')}")
        for label, columns in [('Price', ('L_SystemPrice','price')), ('Bedrooms', ('L_Keyword2','bedrooms','beds')),
                               ('Bathrooms', ('LM_Dec_3','bathrooms','baths')), ('Sqft', ('LM_Int2_3','sqft'))]:
            print(f"{label}: {next((row[c] for c in columns if c in row), 'N/A')}")
        if report['date_column']:
            print(f"Listing date ({report['date_column']}): {row.get(report['date_column'])}")
        for rule in row['rule_scores']:
            print(f"  {rule['field']}: value={rule['value']}, reference={rule['reference']}, score={rule['score']:.4f}")
        print(f"Remarks: {row.get('L_Remarks', row.get('remarks', ''))}")
    if not report['results']:
        print('No matching searchable listings. Hard constraints have not been relaxed.')
    print(f'\nCompleted in {perf_counter()-started:.2f}s. Scores are ranking values, not percentages.')
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--query', help='Run one query and exit.')
    cli.add_argument('--no-llm', action='store_true', help='Use rule-based cleanup without an API call.')
    cli.add_argument('--date-column', help='Actual database column for the first-listing date.')
    args = cli.parse_args()
    try:
        from scripts.query_parser import QueryParser
        from scripts.search_orchestrator import SearchOrchestrator
        parser = QueryParser(llm_cleanup=not args.no_llm)
        print(f'City lookup: {parser.city_source} ({len(parser.valid_cities):,} names)')
        if not parser.valid_cities:
            raise ValueError('No city names loaded. Start the database, then restart this test.')
        orchestrator = SearchOrchestrator(parser=parser, date_column=args.date_column)
    except (ValueError, ImportError) as exc:
        cli.exit(1, f'Setup failed: {exc}\n')
    except Exception as exc:
        cli.exit(1, f'Setup failed ({type(exc).__name__}). Check dependencies, Docker/MySQL and .env.\n')
    if args.query is not None:
        try:
            show_query(orchestrator, args.query)
        except (ValueError, AssertionError) as exc:
            cli.exit(1, f'Search failed: {exc}\n')
        except Exception as exc:
            cli.exit(1, f'Search failed ({type(exc).__name__}). Check database, model/index files and API access.\n')
        return
    print('\nEnter a property search, or :quit to exit. This test returns up to 10 listings.')
    while True:
        try:
            query = input('\nQuery > ').strip()
            if query.lower() in (':quit', ':exit'):
                break
            if query:
                show_query(orchestrator, query)
        except (EOFError, KeyboardInterrupt):
            print('\nGoodbye!')
            break
        except (ValueError, AssertionError) as exc:
            print(f'Search failed: {exc}')
        except Exception as exc:
            print(f'Search failed ({type(exc).__name__}). Check database, model/index files and API access.')


if __name__ == '__main__':
    main()
