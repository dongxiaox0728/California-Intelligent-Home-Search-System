import unittest

import numpy as np
from rank_bm25 import BM25Okapi

from scripts.bm25_search import BM25Index, BM25Searcher


class BM25IndexTests(unittest.TestCase):
    def test_compact_index_matches_reference_scores(self):
        corpus = [[], ["home", "home", "pool"], ["home", "view"], ["home", "pool", "pool"]]
        reference = BM25Okapi(corpus)
        index = BM25Index(iter(corpus))

        for query in (["home"], ["pool", "pool", "view"], ["unknown"], []):
            with self.subTest(query=query):
                np.testing.assert_array_equal(index.get_scores(query), reference.get_scores(query))


def main() -> None:
    searcher = BM25Searcher()
    searcher.load()

    query = "family home with a large backyard"
    results = searcher.search(query, top_k=5)

    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    print("=" * 80)

    for result in results:
        print(
            f"\nRank: {result['rank']} | "
            f"BM25 score: {result['bm25_score']:.4f}"
        )
        print(f"Listing ID: {result['L_ListingID']}")
        print(f"Address: {result.get('L_Address', 'N/A')}")
        print(f"City: {result.get('L_City', 'N/A')}")
        print(f"Remarks: {result.get('remarks', '')}")
        print("-" * 80)


if __name__ == "__main__":
    main()
