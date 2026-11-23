"""Sends the query to the arch engine and formats the results for the website"""
from collections import OrderedDict
from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
import math
from numbers import Integral, Real
from threading import RLock
from time import monotonic

from scripts.search_orchestrator import SearchOrchestrator
from scripts.hard_constraints_filter import HardConstraintsFilter


class WebsiteHardConstraintsFilter(HardConstraintsFilter):
    def filter(self, parsed_query):
        return [{key: value for key, value in row.items() if key != "id"}
                for row in super().filter(parsed_query)]


def json_safe(value):
    """Preserve DB fields while handling dates, Decimal, NumPy scalars and NaN."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, (Real, Decimal)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "item"):
        return json_safe(value.item())
    raise TypeError(f"Unsupported response value: {type(value).__name__}")


class SearchService:
    def __init__(self, parser=None, hard_filter=None, semantic_searcher=None,
                 parse_ttl=300, clock=monotonic):
        self._parser = parser
        self._parse_ttl = parse_ttl
        self._clock = clock
        self._parsed = OrderedDict()
        self._lock = RLock()
        self.orchestrator = SearchOrchestrator(
            parser=self,
            hard_filter=hard_filter if hard_filter is not None else WebsiteHardConstraintsFilter(),
            semantic_searcher=semantic_searcher)

    def search_options(self):
        return json_safe(self.orchestrator.hard_filter.search_options())

    @staticmethod
    def _apply_refinements(parsed, refinements):
        structured = parsed["structured_filters"]
        conditions = structured["conditions"]
        rules = structured["ranking_rules"]

        if "city" in refinements:
            conditions.pop("city", None)
            if refinements["city"] is not None:
                conditions["city"] = refinements["city"]

        for field in ("price", "bedrooms", "bathrooms"):
            edits = refinements.get(field)
            if edits is None:
                continue

            if "min" in edits or "max" in edits:
                exact = conditions.pop(field, None)
                for bound in ("min", "max"):
                    key = f"{field}_{bound}"
                    value = edits.get(bound, conditions.get(key, exact))
                    if value is None:
                        conditions.pop(key, None)
                    else:
                        conditions[key] = value

            if "preferred" in edits:
                rules = [rule for rule in rules if rule["field"] != field or rule["direction"] != "closest"]
                target = edits["preferred"]
                if target is not None:
                    HardConstraintsFilter._conditions({f"{field}_min": target})
                    rules.append({"field": field, "direction": "closest", "target": target})

        structured["conditions"] = HardConstraintsFilter._conditions(conditions)
        structured["ranking_rules"] = rules
        return parsed

    def parse(self, query, refinements=None):
        parsed = self._parse_query(query)
        return self._apply_refinements(parsed, refinements) if refinements else parsed

    def _parse_query(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")
        query = query.strip()
        with self._lock:
            cached = self._parsed.get(query)
            if cached is not None and cached[0] > self._clock():
                self._parsed.move_to_end(query)
                return deepcopy(cached[1])
            if self._parser is None:
                from scripts.query_parser import QueryParser
                self._parser = QueryParser(
                    database_cities=self.orchestrator.hard_filter.cities()
                )
            parsed = self._parser.parse(query)
            self._parsed[query] = (self._clock() + self._parse_ttl, deepcopy(parsed))
            self._parsed.move_to_end(query)
            while len(self._parsed) > 128:
                self._parsed.popitem(last=False)
            return deepcopy(parsed)

    def search(self, query, top_k=5, refinements=None):
        with self._lock:
            parsed = self.parse(query, refinements=refinements) if refinements else None
            report = self.orchestrator.search(query, top_k=top_k, parsed_query=parsed)
        results = []
        aliases = {"listing_id": "L_ListingID", "price": "L_SystemPrice",
                   "beds": "L_Keyword2", "baths": "LM_Dec_3",
                   "sqft": "LM_Int2_3", "property_type": "L_Type_",
                   "remarks": "L_Remarks"}
        for original in report["results"]:
            listing = dict(original)
            for alias, column in aliases.items():
                if column in original:
                    listing[alias] = original[column]
            results.append(listing)
        return json_safe({**report, "query": query, "count": len(results), "results": results})
