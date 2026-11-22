"""Run: python3 tests/test_weighted_ranker.py. No external services required."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts.weighted_ranker import WeightedRanker


def parsed(text='pool', rules=None):
    return {'semantic_words': text, 'structured_filters': {'conditions': {},
            'ranking_rules': [] if rules is None else rules}}


PRICE_RULE = {'field': 'price', 'direction': 'closest', 'target': 700000}


class FakeSearcher:
    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    def search_eligible(self, query, eligible_ids, top_k):
        self.calls.append((query, set(eligible_ids), top_k))
        rows = [{'L_ListingID': key, 'faiss_position': position,
                 'similarity_score': score if query.strip() else None,
                 'price': 99999999}  # Stale metadata must not replace DB values.
                for position, (key, score) in enumerate(self.scores.items()) if key in eligible_ids]
        if query.strip():
            rows.sort(key=lambda row: row['similarity_score'], reverse=True)
        for rank, row in enumerate(rows, 1):
            row['rank'] = rank
        return rows[:top_k]


class TestWeightedRanker(unittest.TestCase):
    def test_equal_weight_formula_and_original_rows_unchanged(self):
        rows = [{'L_ListingID': 'A', 'price': 775000}, {'L_ListingID': 'B', 'price': 700000}]
        before = deepcopy(rows)
        query = parsed(rules=[PRICE_RULE])
        original_query = deepcopy(query)
        result = WeightedRanker(FakeSearcher({'A': .9, 'B': .4})).rank(rows, query)
        self.assertEqual([r['L_ListingID'] for r in result], ['B', 'A'])
        self.assertAlmostEqual(result[0]['final_score'], .5 * .4 + .5 * 1)
        self.assertAlmostEqual(result[1]['final_score'], .5 * .9 + .5 * .4)
        self.assertEqual(result[0]['semantic_weight'], .5)
        self.assertEqual(result[0]['structured_weight'], .5)
        self.assertEqual(rows, before)
        self.assertEqual(query, original_query)

    def test_fusion_before_top100_retains_semantic_rank101_winner(self):
        scores = {str(i): .9 if i < 100 else .8 for i in range(101)}
        rows = [{'L_ListingID': key, 'price': 1200000 if key != '100' else 700000} for key in scores]
        searcher = FakeSearcher(scores)
        result = WeightedRanker(searcher).rank(rows, parsed(rules=[PRICE_RULE]))
        self.assertEqual(searcher.calls[0][2], 101)
        self.assertEqual(len(result), 100)
        self.assertEqual(result[0]['L_ListingID'], '100')
        self.assertEqual(result[0]['semantic_rank'], 101)
        self.assertEqual([row['rank'] for row in result], list(range(1, 101)))

    def test_signal_fallbacks_and_ties(self):
        searcher = FakeSearcher({'A': .8, 'B': .2})
        ranker = WeightedRanker(searcher)
        rows = [{'L_ListingID': 'A', 'price': 750000}, {'L_ListingID': 'B', 'price': 700000}]
        semantic = ranker.rank(rows, parsed())
        self.assertEqual([r['final_score'] for r in semantic], [.8, .2])
        self.assertIsNone(semantic[0]['structured_score'])
        self.assertEqual(semantic[0]['semantic_weight'], 1)
        structured = ranker.rank(rows, parsed('', [PRICE_RULE]))
        self.assertEqual([r['L_ListingID'] for r in structured], ['B', 'A'])
        self.assertEqual([r['final_score'] for r in structured], [1, .5])
        self.assertIsNone(structured[0]['similarity_score'])
        neither = ranker.rank(list(reversed(rows)), parsed(''))
        self.assertEqual([r['L_ListingID'] for r in neither], ['A', 'B'])
        self.assertTrue(all(r['final_score'] is None for r in neither))
        tied = WeightedRanker(FakeSearcher({'A': .4, 'B': .9})).rank(
            [{'L_ListingID': 'A', 'price': 700000}, {'L_ListingID': 'B', 'price': 750000}],
            parsed(rules=[PRICE_RULE]))
        self.assertEqual([r['final_score'] for r in tied], [.7, .7])
        self.assertEqual([r['L_ListingID'] for r in tied], ['A', 'B'])

    def test_sqft_uses_database_value_and_no_rules_cap(self):
        rows = [{'L_ListingID': 'A', 'LM_Int2_3': 2200, 'L_SystemPrice': 700000}]
        rules = [PRICE_RULE, {'field': 'sqft', 'direction': 'closest', 'target': 2000}]
        result = WeightedRanker(FakeSearcher({'A': .9})).rank(rows, parsed(rules=rules))
        # The raw MySQL row must take precedence over conflicting metadata aliases.
        self.assertAlmostEqual(result[0]['structured_score'], .75)
        self.assertAlmostEqual(result[0]['final_score'], .825)

    def test_empty_and_invalid_candidates(self):
        ranker = WeightedRanker(FakeSearcher({'A': .5}))
        self.assertEqual(ranker.rank([], parsed()), [])
        with self.assertRaises(ValueError):
            ranker.rank([{'L_ListingID': 'missing'}], parsed())
        with self.assertRaises(ValueError):
            ranker.rank([{'L_ListingID': 'A', 'price': 1}, {'L_ListingID': 'A', 'price': 2}], parsed())
        self.assertEqual(len(ranker.rank([{'L_ListingID': 'A'}, {'L_ListingID': 'A'}], parsed())), 1)
        with self.assertRaises(ValueError):
            ranker.rank([], {'semantic_words': None})


if __name__ == '__main__':
    unittest.main(verbosity=2)
