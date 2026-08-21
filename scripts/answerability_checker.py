from __future__ import annotations

from typing import Any

from scripts.query_parser import QueryParser


class AnswerabilityChecker:

    def __init__(self, parser: QueryParser | None = None) -> None:
        self.parser = parser or QueryParser()

    def check_pre_query(
        self,
        query: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:

        if not isinstance(query, str):
            return False, "Query must be a string.", None

        if not query.strip():
            return False, "Query cannot be empty.", None

        try:
            filters = self.parser.parse(query)

        except (ValueError, TypeError) as error:
            return False, f"Query cannot be answered: {error}", None

        if not filters:
            return (
                False,
                "The query does not contain any supported search criteria.",
                None,
            )

        return True, "Query is answerable.", filters

    def check_post_query(
        self,
        results: Any,
    ) -> tuple[bool, str]:

        if results is None:
            return False, "The query returned no results."

        try:
            if len(results) == 0:
                return False, "No listings match your criteria."
        except TypeError:
            return False, "The query returned an unsupported result format."

        if hasattr(results, "isnull") and callable(results.isnull):
            try:
                if results.isnull().all().all():
                    return False, "Query returned no meaningful data."
            except Exception:
                pass

            return True, "Results found."

        if isinstance(results, list) and results:
            if all(isinstance(row, dict) for row in results):
                all_values = [
                    value
                    for row in results
                    for value in row.values()
                ]

                if all_values and all(value is None for value in all_values):
                    return False, "Query returned no meaningful data."

                return True, "Results found."

            if all(isinstance(row, (tuple, list)) for row in results):
                flat_values = [
                    value
                    for row in results
                    for value in row
                ]

                if flat_values and all(value is None for value in flat_values):
                    return False, "Query returned no meaningful data."

                return True, "Results found."

        return True, "Results found."


if __name__ == "__main__":
    checker = AnswerabilityChecker()

    test_queries = [
        "3 bed under 700k in Irvine with pool",
        "Which neighborhood has the lowest crime rate?",
        "",
    ]

    for query in test_queries:
        can_answer, message, filters = checker.check_pre_query(query)

        print("\nQuery:", repr(query))
        print("Answerable:", can_answer)
        print("Message:", message)
        print("Filters:", filters)

    # Example post-query checks
    print("\nPost-query examples:")

    empty_results = []
    print(
        "Empty:",
        checker.check_post_query(empty_results)
    )

    valid_results = [
        {
            "L_City": "Irvine",
            "L_SystemPrice": 650000,
            "L_Keyword2": 3,
        }
    ]
    print(
        "Valid:",
        checker.check_post_query(valid_results)
    )

    null_results = [
        {
            "L_City": None,
            "L_SystemPrice": None,
            "L_Keyword2": None,
        }
    ]
    print(
        "All-null:",
        checker.check_post_query(null_results)
    )
