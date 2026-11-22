"""
    Automated tests and a visible sample ranking (no database/model/API needed).
    Run checks: python3 tests/test_structured_ranker.py
    Show results: python3 tests/test_structured_ranker.py --demo
"""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts.structured_ranker import StructuredRanker


def closest(field, target):
    return {"field": field, "direction": "closest", "target": target}


class TestStructuredRanker(unittest.TestCase):
    def setUp(self):
        self.ranker = StructuredRanker()

    def test_three_rules_average_and_explanation(self):
        rows = [
            {"id": "A", "price": 700000, "beds": 2, "baths": 2},
            {"id": "B", "price": 750000, "beds": 3, "baths": 2},
            {"id": "C", "price": 800000, "beds": 4, "baths": 3},
        ]
        rules = [closest("price", 700000), closest("bedrooms", 3), closest("bathrooms", 2)]
        result = self.ranker.rank(rows, rules)
        self.assertEqual([row['id'] for row in result], ['A', 'B', 'C'])
        self.assertAlmostEqual(result[0]['structured_score'], (1 + .5 + 1) / 3)
        self.assertAlmostEqual(result[1]['structured_score'], (.5 + 1 + 1) / 3)
        self.assertAlmostEqual(result[2]['structured_score'], (1/3 + .5 + .5) / 3)
        self.assertEqual([d['tolerance'] for d in result[0]['rule_scores']], [50000, 1, 1])
        self.assertEqual([r['structured_rank'] for r in result], [1, 2, 3])

    def test_target_distance_is_symmetric_and_not_a_filter(self):
        rows = [{'price': p} for p in [750000, 650000, 700000, 900000]]
        result = self.ranker.rank(rows, [closest('price', 700000)])
        self.assertEqual([r['price'] for r in result], [700000, 750000, 650000, 900000])
        self.assertEqual([r['structured_score'] for r in result], [1, .5, .5, .2])

    def test_database_fields_and_parser_output(self):
        parsed = {'structured_filters': {'conditions': {'city': 'Irvine'},
                   'ranking_rules': [closest('price', 700000), closest('bedrooms', 3), closest('bathrooms', 2.5)]},
                  'semantic_words': 'pool'}
        row = {'L_SystemPrice': Decimal('700000'), 'L_Keyword2': 3, 'LM_Dec_3': Decimal('2.5')}
        self.assertEqual(self.ranker.rank([row], parsed)[0]['structured_score'], 1)

    def test_missing_values_keep_denominator_and_candidates(self):
        result = self.ranker.rank([{'price': 700000}, {}],
                                 [closest('price', 700000), closest('bedrooms', 3)])
        self.assertEqual([r['structured_score'] for r in result], [.5, 0])
        for bad in [None, '', 'unknown', float('nan'), float('inf'), -1, True]:
            with self.subTest(value=bad):
                self.assertEqual(self.ranker.rank([{'beds': bad}], [closest('bedrooms', 3)])[0]['structured_score'], 0)

    def test_ascending_descending_and_top_k(self):
        rows = [{'price': 750000, 'beds': 2}, {'price': 700000, 'beds': 4}]
        asc = self.ranker.rank(rows, [{'field': 'price', 'direction': 'asc'}], top_k=1)
        self.assertEqual(asc[0]['price'], 700000)
        desc = self.ranker.rank(rows, [{'field': 'bedrooms', 'direction': 'desc'}])
        self.assertEqual([r['beds'] for r in desc], [4, 2])
        self.assertAlmostEqual(desc[1]['structured_score'], 1/3)
        self.assertEqual(self.ranker.rank([{}], [{'field': 'price', 'direction': 'asc'}])[0]['structured_score'], 0)

    def test_no_rules_empty_candidates_and_no_mutation(self):
        rows = [{'id': 'B', 'rank': 2, 'similarity_score': .3}, {'id': 'A'}]
        original = deepcopy(rows)
        rules = []
        result = self.ranker.rank(rows, rules)
        self.assertEqual([r['id'] for r in result], ['B', 'A'])
        self.assertTrue(all(r['structured_score'] is None for r in result))
        self.assertEqual(result[0]['rank'], 2)
        self.assertEqual(result[0]['similarity_score'], .3)
        self.assertEqual(rows, original)
        self.assertEqual(rules, [])
        self.assertEqual(self.ranker.rank([], [closest('price', 100)]), [])

    def test_square_footage_target_and_database_alias(self):
        parsed = {'structured_filters': {'conditions': {}, 'ranking_rules': [closest('sqft', 2000)]}}
        rows = [{'id': 'A', 'sqft': 1800}, {'id': 'B', 'LM_Int2_3': 2000},
                {'id': 'C', 'sqft': 2100}, {'id': 'D', 'sqft': 2200}]
        result = self.ranker.rank(rows, parsed)
        self.assertEqual([r['id'] for r in result], ['B', 'C', 'A', 'D'])
        for row, expected in zip(result, [1, 2/3, .5, .5]):
            self.assertAlmostEqual(row['structured_score'], expected)
            self.assertEqual(row['rule_scores'][0]['tolerance'], 200)

    def test_square_footage_participates_in_average(self):
        result = self.ranker.rank([{'price': 700000, 'beds': 3, 'baths': 2, 'sqft': 2200}],
                                 [closest('price', 700000), closest('bedrooms', 3),
                                  closest('bathrooms', 2), closest('sqft', 2000)])
        self.assertAlmostEqual(result[0]['structured_score'], (1 + 1 + 1 + .5) / 4)

    def test_invalid_rules_fail_explicitly(self):
        bad_rules = [
            [closest('unknown_field', 1000)], [closest('price', -1)], [closest('price', float('nan'))],
            [{'field': 'price', 'direction': 'closest'}],
            [{'field': 'price', 'direction': 'unknown'}],
            [{'field': 'price', 'direction': 'asc', 'target': 1}],
            [closest('price', 1), closest('price', 1)],
        ]
        for rules in bad_rules:
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                self.ranker.rank([], rules)
        for bad_k in [0, -1, True, 1.5]:
            with self.subTest(top_k=bad_k), self.assertRaises(ValueError):
                self.ranker.rank([], [], top_k=bad_k)


def show_demo():
    import json

    # These are illustrative candidates, not listings fetched from MySQL.
    listings = [
        {"L_ListingID": "A", "price": 700000, "beds": 2, "baths": 2},
        {"L_ListingID": "B", "price": 750000, "beds": 3, "baths": 2},
        {"L_ListingID": "C", "price": 800000, "beds": 4, "baths": 3},
        {"L_ListingID": "D", "price": 700000, "beds": 3, "baths": 2},
    ]
    rules = [closest("price", 700000), closest("bedrooms", 3), closest("bathrooms", 2)]
    print("SAMPLE DATA: target $700,000, 3 bedrooms, 2 bathrooms")
    print("Tolerances: $50,000, 1 bedroom, 1 bathroom; equal-weight average.\n")
    results = StructuredRanker().rank(listings, rules)
    for listing in results:
        print(f"Rank {listing['structured_rank']} | ID {listing['L_ListingID']} | "
              f"Price ${listing['price']:,.0f} | Beds {listing['beds']} | Baths {listing['baths']}")
        grades = ", ".join(f"{rule['field']}={rule['score']:.4f}" for rule in listing['rule_scores'])
        print(f"  {grades} -> average={listing['structured_score']:.4f}")
    print("\nComplete returned results:")
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    if '--demo' in sys.argv:
        show_demo()
    else:
        unittest.main(verbosity=2)
