"""Run: python3 tests/test_search_orchestrator.py. No API, database or model needed."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import date, datetime, timezone
from copy import deepcopy

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.search_orchestrator import SearchOrchestrator


class IDs:
    def __init__(self, ids):
        self.ids = ids
        self.str = self
    def astype(self, _):
        return self
    def strip(self):
        return self.ids


class Searcher:
    def __init__(self, scores):
        self.scores = scores
        self.metadata = {'L_ListingID': IDs(list(scores))}
        self.calls = []
    def search_eligible(self, query, eligible_ids, top_k):
        self.calls.append((query, top_k))
        rows = [dict(L_ListingID=key, similarity_score=score, faiss_position=i)
                for i, (key, score) in enumerate(self.scores.items()) if key in eligible_ids]
        rows.sort(key=lambda row: row['similarity_score'], reverse=True)
        for rank, row in enumerate(rows, 1):
            row['rank'] = rank
        return rows[:top_k]


PRICE = {'field': 'price', 'direction': 'closest', 'target': 700000}


def make(rows, text='', rules=None, searcher=None, date_column='listed_at'):
    parsed = {'semantic_words': text, 'structured_filters': {
        'conditions': {'city': 'Irvine'}, 'ranking_rules': rules or []}}
    parser = SimpleNamespace(parse=lambda query: parsed)
    def apply_filter(value):
        assert value is parsed
        return rows
    return SearchOrchestrator(parser, SimpleNamespace(filter=apply_filter), searcher, date_column)


class TestSearchOrchestrator(unittest.TestCase):
    def test_combined_formula_and_limit_after_scoring(self):
        scores = {str(i): (.9 if i < 100 else .8) for i in range(101)}
        rows = [dict(L_ListingID=key, L_SystemPrice=1200000 if key != '100' else 700000) for key in scores]
        s = Searcher(scores)
        result = make(rows, 'pool', [PRICE], s).search('query', top_k=10)
        self.assertEqual(result['mode'], 'combined')
        self.assertEqual(len(result['results']), 10)
        self.assertEqual(result['results'][0]['L_ListingID'], '100')
        self.assertAlmostEqual(result['results'][0]['final_score'], .9)
        self.assertEqual(s.calls, [('pool', 101)])
        self.assertEqual(len(make(rows, 'pool', [PRICE], s).search('query')['results']), 100)

    def test_semantic_only_and_explicit_index_coverage(self):
        rows = [dict(L_ListingID='A'), dict(L_ListingID='B'), dict(L_ListingID='unindexed')]
        s = Searcher({'A': .2, 'B': .8})
        report = make(rows, 'pool', searcher=s).search('query')
        self.assertEqual(report['mode'], 'semantic')
        self.assertEqual([r['L_ListingID'] for r in report['results']], ['B', 'A'])
        self.assertEqual(report['results'][0]['final_score'], .8)
        self.assertEqual(report['missing_index_count'], 1)
        self.assertTrue(report['warnings'])
        self.assertTrue(all(r['structured_score'] is None for r in report['results']))

    def test_structured_only_does_not_require_faiss_or_index_membership(self):
        rows = [dict(L_ListingID='A', L_SystemPrice=750000), dict(L_ListingID='unindexed', L_SystemPrice=700000)]
        original = deepcopy(rows)
        orch = make(rows, rules=[PRICE])
        report = orch.search('query', top_k=10)
        self.assertEqual(report['mode'], 'structured')
        self.assertEqual(report['results'][0]['L_ListingID'], 'unindexed')
        self.assertEqual(report['results'][0]['final_score'], 1)
        self.assertIsNone(orch.semantic_searcher)
        self.assertEqual(report['missing_index_count'], 0)
        self.assertEqual(rows, original)

    def test_newest_with_ties_missing_dates_and_timezone(self):
        rows = [dict(L_ListingID='C', listed_at='bad'),
                dict(L_ListingID='B', listed_at='2026-10-22T12:00:00-05:00'),
                dict(L_ListingID='A', listed_at=datetime(2026,10,22,17,tzinfo=timezone.utc)),
                dict(L_ListingID='D', listed_at=date(2026,10,21)),
                dict(L_ListingID='E', listed_at=None)]
        report = make(rows).search('query')
        self.assertEqual(report['mode'], 'newest')
        self.assertEqual([r['L_ListingID'] for r in report['results']], ['A','B','D','C','E'])
        self.assertEqual(report['invalid_date_count'], 2)
        self.assertTrue(all(r['final_score'] is None for r in report['results']))
        self.assertEqual([r['rank'] for r in report['results']], [1,2,3,4,5])
        reversed_report = make(list(reversed(rows))).search('query')
        self.assertEqual([r['L_ListingID'] for r in reversed_report['results']], ['A','B','D','C','E'])

    def test_newest_limit_and_no_date_guessing(self):
        rows = [dict(L_ListingID=str(i), listed_at=f'2026-10-{i+1:02}') for i in range(20)]
        self.assertEqual(len(make(rows).search('query',top_k=10)['results']), 10)
        with self.assertRaisesRegex(ValueError, 'absent'):
            make([{'L_ListingID': 'A'}]).search('query')
        with self.assertRaisesRegex(ValueError, 'No valid dates'):
            make([{'L_ListingID': 'A', 'listed_at': '0000-00-00'}]).search('query')

    def test_listing_contract_date_default(self):
        rows = [dict(L_ListingID='older', ListingContractDate='2026-10-01'),
                dict(L_ListingID='newer', ListingContractDate='2026-10-22')]
        with patch.dict('os.environ', {'LISTING_DATE_COLUMN': ''}):
            report = make(rows, date_column=None).search('query')
        self.assertEqual(report['date_column'], 'ListingContractDate')
        self.assertEqual([r['L_ListingID'] for r in report['results']], ['newer', 'older'])

    def test_empty_duplicates_and_bad_limits(self):
        self.assertEqual(make([]).search('query')['results'], [])
        row = dict(L_ListingID=1, L_SystemPrice=700000)
        self.assertEqual(len(make([row, row], rules=[PRICE]).search('query')['results']), 1)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            make([row, dict(L_ListingID=1, L_SystemPrice=1)], rules=[PRICE]).search('query')
        for value in [0, 101, True, 1.5]:
            with self.subTest(top_k=value), self.assertRaises(ValueError):
                make([]).search('query', top_k=value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
