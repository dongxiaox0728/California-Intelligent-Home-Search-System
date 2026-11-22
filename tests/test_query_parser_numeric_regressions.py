"""
    Offline numeric extraction checks; no database, embedding model or API calls.

    Run: python3 tests/test_query_parser_numeric_regressions.py
"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.query_parser import QueryParser


class TestNumericParsing(unittest.TestCase):
    def setUp(self):
        self.parser=QueryParser(load_database_cities=False,llm_cleanup=False,
                               listings_path=ROOT/'tests/nonexistent_numeric_fixture.csv',
                               cities_path=ROOT/'tests/nonexistent_numeric_cities.json')
        self.parser.valid_cities={'la quinta':'La Quinta','apple valley':'Apple Valley'}

    def structured(self,text):
        return self.parser.parse(text)['structured_filters']

    def test_punctuation_cannot_be_a_price(self):
        for text in ['homes, and , with a garden', 'homes . and . with a garage',
                     'homes at $1.25 million with a pool']:
            with self.subTest(text=text):
                result=self.structured(text)
                self.assertNotIn('price_min',result['conditions'])
                self.assertNotIn('price_max',result['conditions'])

    def test_previously_crashing_queries(self):
        result=self.structured('La Quinta, at least 3 bedrooms and 2.5 bathrooms, up to $1.1 million.')
        self.assertEqual(result['conditions'],{'city':'La Quinta','bedrooms_min':3,
                                              'bathrooms_min':2.5,'price_max':1100000})
        self.assertEqual(result['ranking_rules'],[])
        result=self.structured('Apple Valley, $550k max, minimum 3 beds and 2 baths.')
        self.assertEqual(result['conditions'],{'city':'Apple Valley','price_max':550000,
                                              'bedrooms_min':3,'bathrooms_min':2})
        self.assertEqual(result['ranking_rules'],[])

    def test_general_hard_price_phrasings(self):
        for text in ['up to $720k', 'no more than $720k', '$720k max', '$720k or less',
                     'a maximum price of $720,000', 'my budget tops out at $720k',
                     'my budget limit is $720k', 'the most I can spend is $720k',
                     '$720k is the most I can spend', 'my absolute maximum is $720k',
                     'at most $720k']:
            with self.subTest(text=text):
                result=self.structured(text)
                self.assertEqual(result['conditions'],{'price_max':720000})
                self.assertEqual(result['ranking_rules'],[])
        for text in ['no less than $480k', 'at least $480k', '$480k or more', 'minimum price of $480k']:
            with self.subTest(text=text):
                result=self.structured(text)
                self.assertEqual(result['conditions'],{'price_min':480000})
                self.assertEqual(result['ranking_rules'],[])

    def test_range_tightening_and_conflict(self):
        result=self.structured('between $450k and $780k, at most $750k, at least $500k')
        self.assertEqual(result['conditions'],{'price_min':500000,'price_max':750000})
        self.assertEqual(result['ranking_rules'],[])
        with self.assertRaises(ValueError):
            self.structured('at least $900k and up to $700k')

    def test_hard_limit_and_soft_target_remain_distinct(self):
        result=self.structured('$920k maximum, ideally around $810k and about 3 bedrooms')
        self.assertEqual(result['conditions'],{'price_max':920000})
        self.assertCountEqual(result['ranking_rules'],[
            {'field':'price','direction':'closest','target':810000},
            {'field':'bedrooms','direction':'closest','target':3}])

    def test_shared_qualifier_scope_and_explicit_override(self):
        self.assertEqual(self.structured('at least 4 bedrooms and 3 bathrooms')['conditions'],
                         {'bedrooms_min':4,'bathrooms_min':3})
        result=self.structured('at least 4 bedrooms and about 3 bathrooms')
        self.assertEqual(result['conditions'],{'bedrooms_min':4})
        self.assertEqual(result['ranking_rules'],[{'field':'bathrooms','direction':'closest','target':3}])
        # A different clause must not inherit the earlier lower bound.
        result=self.structured('at least 4 bedrooms. Ideally 3 bathrooms')
        self.assertNotIn('bathrooms_min',result['conditions'])

    def test_soft_numeric_rules_and_fractional_bathrooms(self):
        result=self.structured('around 1900 sqft, preferably 4 bedrooms and about 2.5 bathrooms')
        self.assertEqual(result['conditions'],{})
        self.assertCountEqual(result['ranking_rules'],[
            {'field':'sqft','direction':'closest','target':1900},
            {'field':'bedrooms','direction':'closest','target':4},
            {'field':'bathrooms','direction':'closest','target':2.5}])

    def test_sorting_and_hard_cap_are_not_two_price_targets(self):
        for sort_text in ['cheapest first', 'lowest-priced first', 'lower-priced listings first',
                          'lowest price first']:
            with self.subTest(sort_text=sort_text):
                result=self.structured('$900k maximum, '+sort_text)
                self.assertEqual(result['conditions'],{'price_max':900000})
                self.assertEqual(result['ranking_rules'],[{'field':'price','direction':'asc'}])

    def test_numeric_description_does_not_become_a_budget(self):
        result=self.parser.parse('a 5 to 10 minute walk to coffee shops and no garage')
        self.assertEqual(result['structured_filters'],{'conditions':{},'ranking_rules':[]})
        self.assertIn('no garage',result['semantic_words'])

    def test_llm_still_receives_original_query_and_extracted_structure(self):
        calls=[]
        def cleanup(query,conditions,rules):
            calls.append((query,dict(conditions),list(rules)))
            return 'a private yard, no pool'
        self.parser.llm_cleanup=True
        self.parser._clean_semantics_with_llm=cleanup
        query='At most $900k, ideally $800k, with a private yard and no pool'
        result=self.parser.parse(query)
        self.assertEqual(calls[0][0],query)
        self.assertEqual(calls[0][1],{'price_max':900000})
        self.assertEqual(calls[0][2],[{'field':'price','direction':'closest','target':800000}])
        self.assertEqual(result['semantic_words'],'a private yard, no pool')


if __name__=='__main__':
    unittest.main(verbosity=2)
