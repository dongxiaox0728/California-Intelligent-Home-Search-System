from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any


class QueryParser:

    DEFAULT_AMENITIES = {
        "pool",
        "garage",
        "fireplace",
        "outdoor_space",
        "basement",
        "kitchen",
    }

    AMENITY_ALIASES = {
        "swimming pool": "pool",
        "pools": "pool",
        "car garage": "garage",
        "attached garage": "garage",
        "private backyard": "outdoor_space",
        "backyard": "outdoor_space",
        "yard": "outdoor_space",
        "patio": "outdoor_space",
        "deck": "outdoor_space",
    }

    def __init__(
        self,
        listings_path: str | Path = "data/processed/listing_sample_cleaned.csv",
        amenities_path: str | Path = "taxonomy/taxonomy_week3_amenities.json",
    ) -> None:
        self.valid_cities = self._load_cities(Path(listings_path))
        self.valid_amenities = self._load_amenities(Path(amenities_path))

    def parse(self, query: str) -> dict[str, Any]:
        """Convert a natural-language query into structured filters."""
        if not isinstance(query, str):
            raise TypeError("query must be a string")

        text = " ".join(query.lower().strip().split())
        if not text:
            raise ValueError("query cannot be empty")

        filters: dict[str, Any] = {}

        self._parse_price(text, filters)
        self._parse_bedrooms(text, filters)
        self._parse_bathrooms(text, filters)
        self._parse_city(text, filters)
        self._parse_amenities(text, filters)
        self.validate(filters)

        return filters

    def validate(self, filters: dict[str, Any]) -> None:

        for key in ("price_min", "price_max"):
            if key in filters and not 0 <= filters[key] <= 100_000_000:
                raise ValueError(f"{key} is outside the allowed range")

        for key in ("bedrooms", "bedrooms_min", "bedrooms_max"):
            if key in filters and not 0 <= filters[key] <= 20:
                raise ValueError(f"{key} is outside the allowed range")

        for key in ("bathrooms", "bathrooms_min", "bathrooms_max"):
            if key in filters and not 0 <= filters[key] <= 20:
                raise ValueError(f"{key} is outside the allowed range")

        range_pairs = (
            ("price_min", "price_max"),
            ("bedrooms_min", "bedrooms_max"),
            ("bathrooms_min", "bathrooms_max"),
        )

        for minimum, maximum in range_pairs:
            if (
                minimum in filters
                and maximum in filters
                and filters[minimum] > filters[maximum]
            ):
                raise ValueError(f"{minimum} cannot be greater than {maximum}")

        if "city" in filters and self.valid_cities:
            if filters["city"].lower() not in self.valid_cities:
                raise ValueError(f"invalid city: {filters['city']}")

    def to_sql(
        self,
        filters: dict[str, Any],
        table_name: str = "rets_property",
    ) -> tuple[str, list[Any]]:

        self.validate(filters)

        conditions: list[str] = []
        params: list[Any] = []

        mappings = {
            "price_min": ("L_SystemPrice", ">="),
            "price_max": ("L_SystemPrice", "<="),
            "bedrooms": ("L_Keyword2", "="),
            "bedrooms_min": ("L_Keyword2", ">="),
            "bedrooms_max": ("L_Keyword2", "<="),
            "bathrooms": ("LM_Dec_3", "="),
            "bathrooms_min": ("LM_Dec_3", ">="),
            "bathrooms_max": ("LM_Dec_3", "<="),
            "city": ("L_City", "="),
        }

        for key, (column, operator) in mappings.items():
            if key in filters:
                conditions.append(f"{column} {operator} %s")
                params.append(filters[key])

        for amenity in filters.get("amenities", []):
            conditions.append("LOWER(L_Remarks) LIKE %s")
            params.append(f"%{amenity.replace('_', ' ').lower()}%")

        for amenity in filters.get("excluded_amenities", []):
            conditions.append("LOWER(L_Remarks) NOT LIKE %s")
            params.append(f"%{amenity.replace('_', ' ').lower()}%")

        sql = f"SELECT * FROM {table_name}"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return sql, params

    def _parse_price(self, text: str, filters: dict[str, Any]) -> None:
        number = r"\$?\s*([\d,.]+)\s*(k|m|thousand|million)?"

        range_match = re.search(
            rf"(?:between\s+)?{number}\s*(?:and|to|-)\s*{number}",
            text,
        )
        if range_match:
            filters["price_min"] = self._parse_number(
                range_match.group(1), range_match.group(2)
            )
            filters["price_max"] = self._parse_number(
                range_match.group(3), range_match.group(4)
            )
            return

        max_match = re.search(
            rf"(?:under|below|less than|up to|maximum of|max of)\s*{number}",
            text,
        )
        if max_match:
            filters["price_max"] = self._parse_number(
                max_match.group(1), max_match.group(2)
            )

        min_match = re.search(
            rf"(?:over|above|more than|at least|minimum of|min of)\s*{number}",
            text,
        )
        if min_match:
            filters["price_min"] = self._parse_number(
                min_match.group(1), min_match.group(2)
            )

    def _parse_bedrooms(self, text: str, filters: dict[str, Any]) -> None:
        label = r"(?:bed|beds|bedroom|bedrooms|br)"

        range_match = re.search(
            rf"(?:between\s+)?(\d+)\s*(?:and|to|-)\s*(\d+)\s*{label}\b",
            text,
        )
        if range_match:
            filters["bedrooms_min"] = int(range_match.group(1))
            filters["bedrooms_max"] = int(range_match.group(2))
            return

        min_match = re.search(
            rf"(?:at least|minimum of|min of)\s*(\d+)\s*{label}\b",
            text,
        )
        if min_match:
            filters["bedrooms_min"] = int(min_match.group(1))
            return

        max_match = re.search(
            rf"(?:up to|at most|maximum of|max of)\s*(\d+)\s*{label}\b",
            text,
        )
        if max_match:
            filters["bedrooms_max"] = int(max_match.group(1))
            return

        exact_match = re.search(rf"(\d+)\s*(\+)?\s*{label}\b", text)
        if exact_match:
            value = int(exact_match.group(1))
            key = "bedrooms_min" if exact_match.group(2) else "bedrooms"
            filters[key] = value

    def _parse_bathrooms(self, text: str, filters: dict[str, Any]) -> None:
        label = r"(?:bath|baths|bathroom|bathrooms|ba)"
        value_pattern = r"\d+(?:\.\d+)?"

        range_match = re.search(
            rf"(?:between\s+)?({value_pattern})\s*(?:and|to|-)\s*"
            rf"({value_pattern})\s*{label}\b",
            text,
        )
        if range_match:
            filters["bathrooms_min"] = self._clean_float(range_match.group(1))
            filters["bathrooms_max"] = self._clean_float(range_match.group(2))
            return

        min_match = re.search(
            rf"(?:at least|minimum of|min of)\s*({value_pattern})\s*{label}\b",
            text,
        )
        if min_match:
            filters["bathrooms_min"] = self._clean_float(min_match.group(1))
            return

        max_match = re.search(
            rf"(?:up to|at most|maximum of|max of)\s*({value_pattern})\s*{label}\b",
            text,
        )
        if max_match:
            filters["bathrooms_max"] = self._clean_float(max_match.group(1))
            return

        exact_match = re.search(
            rf"({value_pattern})\s*(\+)?\s*{label}\b",
            text,
        )
        if exact_match:
            value = self._clean_float(exact_match.group(1))
            key = "bathrooms_min" if exact_match.group(2) else "bathrooms"
            filters[key] = value

    def _parse_city(self, text: str, filters: dict[str, Any]) -> None:
        for city_lower, city_original in sorted(
            self.valid_cities.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if re.search(rf"\b{re.escape(city_lower)}\b", text):
                filters["city"] = city_original
                return

    def _parse_amenities(self, text: str, filters: dict[str, Any]) -> None:
        included: list[str] = []
        excluded: list[str] = []

        candidates = {
            amenity.replace("_", " "): amenity
            for amenity in self.valid_amenities
        }
        candidates.update(self.AMENITY_ALIASES)

        for phrase, canonical in sorted(
            candidates.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            phrase_pattern = re.escape(phrase)
            negated = re.search(
                rf"\b(?:no|without|exclude|excluding|not with)\s+"
                rf"(?:a\s+|an\s+)?{phrase_pattern}\b",
                text,
            )

            if negated:
                if canonical not in excluded:
                    excluded.append(canonical)
                continue

            if re.search(rf"\b{phrase_pattern}\b", text):
                if canonical not in included:
                    included.append(canonical)

        included = [item for item in included if item not in excluded]

        if included:
            filters["amenities"] = included
        if excluded:
            filters["excluded_amenities"] = excluded

    @staticmethod
    def _parse_number(value: str, suffix: str | None) -> int:
        number = float(value.replace(",", ""))
        suffix = (suffix or "").lower()

        if suffix in {"k", "thousand"}:
            number *= 1_000
        elif suffix in {"m", "million"}:
            number *= 1_000_000

        return int(number)

    @staticmethod
    def _clean_float(value: str) -> int | float:
        number = float(value)
        return int(number) if number.is_integer() else number

    def _load_cities(self, path: Path) -> dict[str, str]:
        cities: dict[str, str] = {}

        try:
            import csv

            with path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    city = (row.get("L_City") or "").strip()
                    if city:
                        cities[city.lower()] = city
        except (FileNotFoundError, OSError):
            pass

        return cities

    def _load_amenities(self, path: Path) -> set[str]:
        amenities = set(self.DEFAULT_AMENITIES)

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if isinstance(data, list):
                for item in data:
                    extracted = item.get("extracted_entities", {})
                    amenities.update(extracted.get("amenities", []))
            elif isinstance(data, dict):
                amenities.update(data.get("amenities", []))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        return amenities


if __name__ == "__main__":
    parser = QueryParser()

    example = "3 bed under 700k in Irvine with pool and no garage"
    parsed_filters = parser.parse(example)
    sql_query, sql_params = parser.to_sql(parsed_filters)

    print("Query:", example)
    print("Filters:", parsed_filters)
    print("SQL:", sql_query)
    print("Parameters:", sql_params)
