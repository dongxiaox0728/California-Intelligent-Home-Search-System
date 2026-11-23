"""
    Website search integration tests: no model downloads, database or API calls.

    Run: python3 -B tests/test_backend_search.py
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from backend import main
from backend.search_service import SearchService, json_safe
from scripts.hard_constraints_filter import HardConstraintsFilter
from scripts.query_parser import QueryParser


def parsed(text="", rules=None):
    return {"semantic_words": text, "structured_filters": {
        "conditions": {"city": "Irvine", "price_max": 900000},
        "ranking_rules": rules or []}}


class IDs:
    def __init__(self, ids):
        self.ids = ids
        self.str = self
    def astype(self, _):
        return self
    def strip(self):
        return self.ids


class Searcher:
    def __init__(self):
        self.metadata = {"L_ListingID": IDs(["A", "B"])}
    def search_eligible(self, query, eligible_ids, top_k):
        rows = [{"L_ListingID": key, "similarity_score": score,
                 "rank": rank, "faiss_position": rank - 1}
                for rank, (key, score) in enumerate([("B", .9), ("A", .8)], 1)
                if key in eligible_ids]
        return rows[:top_k]


ROWS = [
    {"L_ListingID": "A", "L_City": "Irvine", "L_SystemPrice": Decimal("700000"),
     "L_Keyword2": 0, "LM_Dec_3": Decimal("1.5"), "LM_Int2_3": 1200,
     "L_Type_": "Condominium", "L_Remarks": "A quiet home with a pool.",
     "ListingContractDate": date(2026, 10, 22)},
    {"L_ListingID": "B", "L_City": "Irvine", "L_SystemPrice": Decimal("850000"),
     "L_Keyword2": 3, "LM_Dec_3": Decimal("2.5"), "LM_Int2_3": 1800,
     "L_Type_": "Condominium", "L_Remarks": "A private pool.",
     "ListingContractDate": date(2026, 10, 21)},
]


class SearchServiceTests(unittest.TestCase):
    def test_typed_city_uses_the_same_database_lookup_as_search_options(self):
        city_rows = [{"city": "Irvine"}, {"city": "San Luis Obispo"}]
        bounds = [{"price": 900000, "bedrooms": 4, "bathrooms": 3}]
        service = SearchService()
        with (
            patch.object(HardConstraintsFilter, "_fetch", side_effect=[city_rows, bounds, city_rows]) as fetch,
            patch.object(QueryParser, "_load_database_cities") as docker_lookup,
            patch.object(QueryParser, "_clean_semantics_with_llm", return_value="pool"),
        ):
            options = service.search_options()
            query = service.parse("3-bedroom homes in San Luis Obispo with a pool")

        self.assertIn("San Luis Obispo", options["cities"])
        self.assertEqual(query["structured_filters"]["conditions"]["city"], "San Luis Obispo")
        self.assertEqual(fetch.call_args_list[0], fetch.call_args_list[2])
        docker_lookup.assert_not_called()

    def test_all_ranking_paths_and_frontend_fields(self):
        price = {"field": "price", "direction": "closest", "target": 700000}
        for text, rules, mode, first in [("", [], "newest", "A"),
                ("", [price], "structured", "A"), ("pool", [], "semantic", "B"),
                ("pool", [price], "combined", "A")]:
            with self.subTest(mode=mode):
                parser = Mock(); parser.parse.return_value = parsed(text, rules)
                hard_filter = Mock(); hard_filter.filter.return_value = deepcopy(ROWS)
                service = SearchService(parser, hard_filter, Searcher())
                result = service.search("query", 1)
                self.assertEqual(result["mode"], mode)
                self.assertEqual(result["count"], 1)
                row = result["results"][0]
                self.assertEqual(row["listing_id"], first)
                for alias, canonical in [("price", "L_SystemPrice"), ("beds", "L_Keyword2"),
                        ("baths", "LM_Dec_3"), ("property_type", "L_Type_"), ("remarks", "L_Remarks")]:
                    self.assertEqual(row[alias], row[canonical])
                self.assertEqual(row["rank"], 1)
                hard_filter.filter.assert_called_once_with(parsed(text, rules))
                json.dumps(result, allow_nan=False)

    def test_parse_reused_without_mutation_and_expires(self):
        clock = Mock(return_value=0)
        parser = Mock(); parser.parse.return_value = parsed()
        hard_filter = Mock(); hard_filter.filter.return_value = []
        service = SearchService(parser, hard_filter, parse_ttl=10, clock=clock)
        original = service.parse(" query ")
        original["structured_filters"]["conditions"]["price_max"] = 1
        service.search("query", 5)
        parser.parse.assert_called_once_with("query")
        self.assertEqual(hard_filter.filter.call_args.args[0]["structured_filters"]["conditions"]["price_max"],900000)
        clock.return_value = 11
        service.parse("query")
        self.assertEqual(parser.parse.call_count, 2)

    def test_refinements_override_conditions_and_preserve_semantic_search(self):
        parser = Mock()
        parser.parse.return_value = parsed("private pool", [
            {"field": "price", "direction": "closest", "target": 850000},
        ])
        hard_filter = Mock()
        hard_filter.filter.return_value = deepcopy(ROWS)
        service = SearchService(parser, hard_filter, Searcher())
        refinements = {
            "city": None,
            "price": {"max": None, "preferred": 700000},
            "bathrooms": {"min": 1.5, "max": 3},
        }

        result = service.search("query", 1, refinements=refinements)

        effective = result["parsed_query"]
        self.assertEqual(effective["semantic_words"], "private pool")
        self.assertEqual(effective["structured_filters"]["conditions"], {"bathrooms_min": 1.5, "bathrooms_max": 3})
        hard_filter.filter.assert_called_once_with(effective)
        self.assertEqual(result["mode"], "combined")
        self.assertEqual(result["results"][0]["listing_id"], "A")
        self.assertEqual(service.parse("query"), parser.parse.return_value)
        parser.parse.assert_called_once_with("query")

    def test_no_matches_and_lazy_semantic_loading(self):
        parser = Mock(); parser.parse.return_value = parsed()
        hard_filter = Mock(); hard_filter.filter.return_value = []
        service = SearchService(parser, hard_filter)
        result = service.search("query")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["count"], 0)
        self.assertIsNone(service.orchestrator.semantic_searcher)

    def test_duplicate_import_row_ids_do_not_block_website_search(self):
        parser = Mock(); parser.parse.return_value = parsed()
        rows = [{**ROWS[0], "id": 1}, {**ROWS[0], "id": 2}]
        original = deepcopy(rows)
        with patch.object(HardConstraintsFilter, "filter", return_value=rows):
            report = SearchService(parser=parser).search("query", top_k=5)
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["results"][0]["listing_id"], "A")
        self.assertNotIn("id", report["results"][0])
        self.assertEqual(rows, original)

    def test_conflicting_listing_values_are_still_rejected(self):
        parser = Mock(); parser.parse.return_value = parsed()
        rows = [{**ROWS[0], "id": 1}, {**ROWS[0], "id": 2, "L_SystemPrice": 800000}]
        with patch.object(HardConstraintsFilter, "filter", return_value=rows):
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                SearchService(parser=parser).search("query")

    def test_json_safe_dates_decimals_and_nan(self):
        self.assertEqual(json_safe({"price": Decimal("3.5"), "date": date(2026, 10, 22),
                                   "score": float("nan")}),
                         {"price": 3.5, "date": "2026-10-22", "score": None})


class EndpointTests(unittest.TestCase):
    def setUp(self):
        main.limiter.reset()
        self.client = TestClient(main.app)
        self.cache = Mock()
        self.cache.get.return_value = None
        self.service = Mock()
        self.service.parse.return_value = parsed()
        self.response = {"query":"query", "count":0,"results":[],"mode":"newest"}
        self.service.search.return_value = self.response
        self.patch_cache = patch.object(main, "redis_client", self.cache)
        self.patch_service = patch.object(main, "search_service", self.service)
        self.patch_cache.start(); self.patch_service.start()
        self.addCleanup(self.patch_cache.stop); self.addCleanup(self.patch_service.stop)
        self.addCleanup(self.client.close)

    def test_search_delegates_and_old_cache_is_not_reused(self):
        legacy = "search:" + main.hashlib.sha256(b"query:5").hexdigest()
        old_hybrid = "search:hybrid:v1:" + main.hashlib.sha256(
            json.dumps(["query", 5, {}], sort_keys=True).encode()
        ).hexdigest()
        self.cache.get.side_effect = lambda key: json.dumps({"legacy": True}) if key in {legacy, old_hybrid} else None
        response = self.client.post("/search",json={"query":"query","top_k":5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.response)
        self.service.search.assert_called_once_with(query="query", top_k=5)
        self.assertTrue(self.cache.setex.call_args.args[0].startswith("search:hybrid:v2:"))

    def test_cache_hit_skips_search_and_bad_json_is_ignored(self):
        self.cache.get.return_value = json.dumps(self.response)
        response = self.client.post("/search",json={"query":"query"})
        self.assertEqual(response.json(),self.response)
        self.service.search.assert_not_called()
        self.cache.get.return_value = "broken JSON"
        self.assertEqual(self.client.post("/search",json={"query":"query"}).status_code,200)
        self.service.search.assert_called_once()

    def test_redis_outage_does_not_block_search(self):
        self.cache.get.side_effect = ConnectionError("offline")
        self.cache.setex.side_effect = ConnectionError("offline")
        self.assertEqual(self.client.post("/search",json={"query":"query"}).json(),self.response)

    def test_parse_returns_flat_ui_filters_and_full_new_structure(self):
        response = self.client.post("/parse-query",json={"query":"query"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["filters"], parsed()["structured_filters"]["conditions"])
        self.assertEqual(response.json()["parsed_query"],parsed())

    def test_refinements_reach_backend_and_partition_the_search_cache(self):
        cache_keys = set()
        for city in ("Irvine", "Santa Barbara", None):
            refinements = {"city": city}
            body = {"query": "pool homes", "refinements": refinements}
            self.assertEqual(self.client.post("/search", json=body).status_code, 200)
            self.service.search.assert_called_with(query="pool homes", top_k=5, refinements=refinements)
            cache_keys.add(self.cache.setex.call_args.args[0])
            self.assertEqual(self.client.post("/parse-query", json=body).status_code, 200)
            self.service.parse.assert_called_with("pool homes", refinements=refinements)
        self.assertEqual(len(cache_keys), 3)

    def test_invalid_inputs_and_query_errors(self):
        for body in [{"query":" "},{"query":"query","top_k":0},
                     {"query":"query","top_k":101},{"query":"query","top_k":True}]:
            self.assertEqual(self.client.post("/search",json=body).status_code,422)
        self.service.search.assert_not_called()
        self.service.search.side_effect = ValueError("invalid query")
        self.assertEqual(self.client.post("/search",json={"query":"query"}).status_code,400)
        self.service.search.side_effect = RuntimeError("search unavailable")
        self.assertEqual(self.client.post("/search",json={"query":"query"}).status_code,503)

    def test_health_and_bm25_remain_available(self):
        self.assertEqual(self.client.get("/health").status_code,200)
        bm25=Mock();bm25.search.return_value=[]
        with patch.object(main,"component",return_value=bm25):
            self.assertEqual(self.client.post("/bm25-search",json={"query":"query"}).json()["results"],[])
        self.service.search.assert_not_called()

    def test_missing_intent_model_has_readable_cors_response(self):
        with patch.object(main, "component", side_effect=RuntimeError("model missing")):
            response = self.client.post("/classify-intent", json={"query":"query"},
                                        headers={"Origin":"http://localhost:5173"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Restore the trained model",response.json()["detail"])
        self.assertEqual(response.headers["access-control-allow-origin"],"http://localhost:5173")
        self.assertEqual(self.client.post("/search",json={"query":"query"}).status_code,200)

    def test_intent_component_checks_model_before_import(self):
        main.component.cache_clear()
        with patch.object(Path, "is_dir", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "trained model is missing"):
                main.component("intent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
