"""
    Score numeric preferences without filtering or changing source listings.

    Closest-target score = 1 / (1 + abs(value - target) / tolerance).
    Tolerances: price=$50,000, bedrooms=1, bathrooms=1, sqft=200. The structured score
    is the arithmetic mean across the supplied rules, each counted once.

    Ascending/descending rules use distance from the best available eligible value
    (minimum/maximum respectively), using the same tolerance formula. Thus their
    scores depend on the candidate set; supply all eligible listings before top_k.
    Missing, nonnumeric, negative or nonfinite listing values score zero for that
    rule and stay in the denominator. No rules gives None scores and stable order.

    This component does not apply hard constraints or combine semantic scores.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


class StructuredRanker:
    TOLERANCES = {"price": 50_000.0, "bedrooms": 1.0, "bathrooms": 1.0, "sqft": 200.0}
    FIELD_COLUMNS = {
        "price": ("price", "L_SystemPrice"),
        "bedrooms": ("bedrooms", "beds", "L_Keyword2"),
        "bathrooms": ("bathrooms", "baths", "LM_Dec_3"),
        "sqft": ("sqft", "LM_Int2_3"),
    }

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) and number >= 0 else None

    @classmethod
    def _value(cls, listing: Mapping[str, Any], field: str) -> float | None:
        # Use the first present alias, even if invalid, to avoid hiding bad data
        # behind an inconsistent second representation of the same field.
        for column in cls.FIELD_COLUMNS[field]:
            if column in listing:
                return cls._number(listing[column])
        return None

    @classmethod
    def _rules(cls, supplied: Any) -> list[dict[str, Any]]:
        if isinstance(supplied, Mapping):
            structured = supplied.get("structured_filters")
            if not isinstance(structured, Mapping) or "ranking_rules" not in structured:
                raise ValueError("Parser output must contain structured_filters.ranking_rules.")
            supplied = structured["ranking_rules"]
        if not isinstance(supplied, (list, tuple)):
            raise TypeError("Supply a list of ranking rules or a complete parser result.")
        rules = []
        seen = set()
        for raw in supplied:
            if not isinstance(raw, Mapping):
                raise TypeError("Each ranking rule must be a dictionary.")
            field, direction = raw.get("field"), raw.get("direction")
            if not isinstance(field, str) or field not in cls.TOLERANCES:
                raise ValueError("Supported ranking fields: price, bedrooms, bathrooms, sqft.")
            if direction not in ("closest", "asc", "desc"):
                raise ValueError("Supported ranking directions: closest, asc, desc.")
            rule = {"field": field, "direction": direction}
            target = None
            if direction == "closest":
                target = cls._number(raw.get("target"))
                if target is None:
                    raise ValueError("A closest rule needs a finite, nonnegative numeric target.")
                rule["target"] = target
            elif "target" in raw:
                raise ValueError("Ascending/descending rules must not supply a target.")
            key = (field, direction, target)
            if key in seen:
                raise ValueError("Duplicate ranking rules would give a preference extra weight.")
            seen.add(key)
            rules.append(rule)
        return rules

    def rank(
        self,
        listings: Iterable[Mapping[str, Any]],
        ranking_rules: Any,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:

        if top_k is not None and (isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0):
            raise ValueError("top_k must be a positive integer or None.")
        rules = self._rules(ranking_rules)
        rows = []
        for listing in listings:
            if not isinstance(listing, Mapping):
                raise TypeError("Each listing must be a dictionary.")
            rows.append(dict(listing))
        # Compute directional reference values over the entire candidate set.
        references = []
        for rule in rules:
            if rule["direction"] == "closest":
                references.append(rule["target"])
            else:
                values = [value for row in rows
                          if (value := self._value(row, rule["field"])) is not None]
                references.append((min(values) if rule["direction"] == "asc" else max(values))
                                  if values else None)
        for row in rows:
            details = []
            for rule, reference in zip(rules, references):
                value = self._value(row, rule["field"])
                tolerance = self.TOLERANCES[rule["field"]]
                score = (1.0 / (1.0 + abs(value - reference) / tolerance)
                         if value is not None and reference is not None else 0.0)
                details.append({**rule, "value": value, "reference": reference,
                                "tolerance": tolerance, "score": score})
            row["rule_scores"] = details
            row["structured_score"] = (math.fsum(item["score"] for item in details) / len(details)
                                       if details else None)
        if rules:
            rows.sort(key=lambda row: row["structured_score"], reverse=True)
        for rank, row in enumerate(rows, start=1):
            row["structured_rank"] = rank
        return rows if top_k is None else rows[:top_k]
