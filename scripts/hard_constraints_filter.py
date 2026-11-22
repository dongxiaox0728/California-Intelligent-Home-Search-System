"""Apply parsed hard conditions to rets_property; semantic text stay separate."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class HardConstraintsFilter:

    COLUMNS = {
        "city": ("L_City", "="),
        "property_type": ("L_Type_", "="),
        "price_min": ("L_SystemPrice", ">="),
        "price_max": ("L_SystemPrice", "<="),
        "bedrooms": ("L_Keyword2", "="),
        "bedrooms_min": ("L_Keyword2", ">="),
        "bedrooms_max": ("L_Keyword2", "<="),
        "bathrooms": ("LM_Dec_3", "="),
        "bathrooms_min": ("LM_Dec_3", ">="),
        "bathrooms_max": ("LM_Dec_3", "<="),
        "sqft_min": ("LM_Int2_3", ">="),
        "sqft_max": ("LM_Int2_3", "<="),
    }

    def __init__(self, connection: Any = None) -> None:
        self.connection = connection

    @classmethod
    def _conditions(cls, parsed_query: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(parsed_query, Mapping):
            raise TypeError("Expected a parser result or conditions dictionary")
        if "structured_filters" in parsed_query:
            structured = parsed_query["structured_filters"]
            if not isinstance(structured, Mapping) or "conditions" not in structured:
                raise ValueError("Parser result must contain structured_filters.conditions")
            conditions = structured["conditions"]
        else:
            conditions = parsed_query
        if not isinstance(conditions, Mapping):
            raise TypeError("conditions must be a dictionary")
        unknown = set(conditions) - cls.COLUMNS.keys()
        if unknown:
            raise ValueError(f"Unsupported hard conditions: {', '.join(sorted(map(str, unknown)))}")
        result = dict(conditions)
        for key, value in result.items():
            if key in {"city", "property_type"}:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{key} must be a nonempty string")
                result[key] = value.strip()
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"{key} must be a finite, nonnegative number")
                ceiling = 100_000_000 if key.startswith("price_") else 20 if key.startswith(("bedrooms", "bathrooms")) else None
                if ceiling is not None and value > ceiling:
                    raise ValueError(f"{key} is outside the allowed range")
                if key.startswith("bedrooms") and int(value) != value:
                    raise ValueError("Bedroom counts must be whole numbers")
        for field in ("price", "bedrooms", "bathrooms", "sqft"):
            low, high = result.get(field + "_min"), result.get(field + "_max")
            if low is not None and high is not None and low > high:
                raise ValueError(f"{field} minimum cannot exceed its maximum")
            exact = result.get(field)
            if exact is not None and ((low is not None and exact < low) or (high is not None and exact > high)):
                raise ValueError(f"Exact {field} conflicts with its bounds")
        return result

    def build_query(self, parsed_query: Mapping[str, Any]) -> tuple[str, list[Any]]:
        conditions = self._conditions(parsed_query)
        clauses, parameters = [], []
        for key, (column, operator) in self.COLUMNS.items():
            if key in conditions:
                clauses.append(f"`{column}` {operator} %s")
                parameters.append(conditions[key])
        sql = "SELECT * FROM `rets_property`"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return sql, parameters

    @staticmethod
    def _connect() -> Any:
        try:
            from dotenv import load_dotenv
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError("Install dependencies: python3 -m pip install mysql-connector-python python-dotenv") from exc
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "root"),
            database=os.getenv("MYSQL_DATABASE", "real_estate"),
            connection_timeout=10,
        )

    def filter(self, parsed_query: Mapping[str, Any]) -> list[dict[str, Any]]:
        ##Fetch all eligible listings; return [] when none match.
        sql, parameters = self.build_query(parsed_query)
        return self._fetch(sql, parameters)

    def search_options(self) -> dict[str, Any]:
        cities = self._fetch("""
            SELECT DISTINCT TRIM(`L_City`) AS city
            FROM `rets_property`
            WHERE TRIM(`L_City`) <> ''
            ORDER BY city
        """)
        bounds, = self._fetch("""
            SELECT MAX(CASE WHEN `L_SystemPrice` BETWEEN 0 AND 100000000 THEN `L_SystemPrice` END) AS price,
                   MAX(CASE WHEN `L_Keyword2` BETWEEN 0 AND 20 THEN `L_Keyword2` END) AS bedrooms,
                   MAX(CASE WHEN `LM_Dec_3` BETWEEN 0 AND 20 THEN `LM_Dec_3` END) AS bathrooms
            FROM `rets_property`
        """)
        return {
            "cities": [row["city"] for row in cities],
            "maxima": {field: float(value) for field, value in bounds.items() if value is not None},
        }

    def _fetch(self, sql, parameters=()) -> list[dict[str, Any]]:
        owned = self.connection is None
        connection = self._connect() if owned else self.connection
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(sql, parameters)
            return cursor.fetchall()
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            finally:
                if owned:
                    connection.close()


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--conditions", help="Hard conditions as a JSON object; no LLM needed")
    group.add_argument("--query", help="Natural-language query, using your existing QueryParser")
    cli.add_argument("--preview", action="store_true", help="Print SQL and parameters without fetching listings")
    cli.add_argument("--output", type=Path, help="Save all eligible listings as JSON")
    args = cli.parse_args()
    try:
        if args.query is not None:
            if __package__:
                from .query_parser import QueryParser
            else:
                from query_parser import QueryParser
            parsed = QueryParser().parse(args.query)
        else:
            parsed = json.loads(args.conditions)
        hard_filter = HardConstraintsFilter()
        sql, parameters = hard_filter.build_query(parsed)
        if args.preview:
            print(sql)
            print("Parameters:", json.dumps(parameters, ensure_ascii=False))
            return
        listings = hard_filter.filter(parsed)
        print(f"Matched {len(listings)} listings.")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(listings, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
            print(f"Saved all matches to {args.output}")
        else:
            print(json.dumps(listings[:5], indent=2, ensure_ascii=False, default=str))
            if len(listings) > 5:
                print("Showing the first 5 matches only; use --output to save all matches.")
    except Exception as exc:
        # Avoid printing database credentials or raw API response details.
        if isinstance(exc, (ValueError, TypeError, RuntimeError)):
            cli.exit(1, f"Filtering failed: {exc}\n")
        cli.exit(1, f"Filtering failed ({type(exc).__name__}). Check MySQL is running and your MYSQL_* settings.\n")


if __name__ == "__main__":
    main()
