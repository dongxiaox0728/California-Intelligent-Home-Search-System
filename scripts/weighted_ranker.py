"""
    Equal-weight semantic/structured fusion, selecting up to 100 results last.

    When both signals exist: final_score = .5 * similarity_score + .5 * structured_score.
    Uses the existing raw cosine similarity (not a probability); no per-query min-max
    normalization is applied. With only one signal, use it alone. With neither,
    keep saved index order and return None scores. All input listings must be
    eligible AND indexed; the caller must report any database/index coverage gaps.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from scripts.structured_ranker import StructuredRanker


class WeightedRanker:
    SEMANTIC_WEIGHT = 0.5
    STRUCTURED_WEIGHT = 0.5
    RESULT_LIMIT = 100

    def __init__(self, semantic_searcher):
        self.semantic_searcher = semantic_searcher
        self.structured_ranker = StructuredRanker()

    def rank(
        self,
        eligible_listings: Iterable[Mapping[str, Any]],
        parsed_query: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(parsed_query, Mapping):
            raise TypeError("parsed_query must be the complete parser result.")
        semantic_text = parsed_query.get("semantic_words")
        if not isinstance(semantic_text, str):
            raise ValueError("Parser result must contain string semantic_words.")
        rules = self.structured_ranker._rules(parsed_query)
        rows_by_id = {}
        for listing in eligible_listings:
            if not isinstance(listing, Mapping):
                raise TypeError("Each eligible listing must be a dictionary.")
            value = listing.get("L_ListingID")
            if value is None or isinstance(value, bool) or not str(value).strip():
                raise ValueError("Every eligible listing needs a nonempty L_ListingID.")
            listing_id = str(value).strip()
            row = dict(listing)
            row["L_ListingID"] = listing_id
            if listing_id in rows_by_id and rows_by_id[listing_id] != row:
                raise ValueError("Conflicting database rows share a listing ID.")
            rows_by_id[listing_id] = row
        if not rows_by_id:
            return []

        # Crucial: ask for EVERY eligible candidate, never the semantic top 100.
        semantic_results = self.semantic_searcher.search_eligible(
            query=semantic_text, eligible_ids=list(rows_by_id), top_k=len(rows_by_id),
        )
        result_ids = [str(row["L_ListingID"]).strip() for row in semantic_results]
        if len(result_ids) != len(set(result_ids)) or set(result_ids) != set(rows_by_id):
            raise ValueError("Semantic results must cover every eligible listing exactly once.")
        semantic_active = bool(semantic_text.strip())
        structured_active = bool(rules)
        merged = []
        # Start in index order so equal final scores have a stable tie order.
        for semantic_row in sorted(semantic_results, key=lambda row: row["faiss_position"]):
            listing_id = str(semantic_row["L_ListingID"]).strip()
            row = dict(semantic_row)
            database_row = rows_by_id[listing_id]
            row.update(database_row)
            # Canonicalize authoritative database values so stale CSV aliases
            # cannot override fields such as L_SystemPrice or LM_Int2_3.
            for field, aliases in self.structured_ranker.FIELD_COLUMNS.items():
                for alias in aliases:
                    if alias in database_row:
                        row[aliases[0]] = database_row[alias]
                        break
            score = semantic_row["similarity_score"]
            if semantic_active:
                if score is None or not math.isfinite(float(score)):
                    raise ValueError("Missing or invalid semantic score.")
                score = float(score)
            else:
                score = None
            row.update(similarity_score=score,
                       semantic_rank=semantic_row["rank"] if semantic_active else None,
                       faiss_position=semantic_row["faiss_position"])
            merged.append(row)

        # No truncation here either; asc/desc references use all candidates.
        structured_results = self.structured_ranker.rank(merged, rules)
        structured_results.sort(key=lambda row: row["faiss_position"])
        semantic_weight = self.SEMANTIC_WEIGHT if structured_active else 1.0
        structured_weight = self.STRUCTURED_WEIGHT if semantic_active else 1.0
        semantic_weight = semantic_weight if semantic_active else 0.0
        structured_weight = structured_weight if structured_active else 0.0
        for row in structured_results:
            if semantic_active or structured_active:
                row["final_score"] = (
                    semantic_weight * (row["similarity_score"] if semantic_active else 0.0)
                    + structured_weight * (row["structured_score"] if structured_active else 0.0)
                )
            else:
                row["final_score"] = None
            if not structured_active:
                row["structured_rank"] = None
            row["semantic_weight"] = semantic_weight
            row["structured_weight"] = structured_weight
        if semantic_active or structured_active:
            structured_results.sort(key=lambda row: row["final_score"], reverse=True)
        for rank, row in enumerate(structured_results, start=1):
            row["rank"] = rank
        return structured_results[:self.RESULT_LIMIT]
