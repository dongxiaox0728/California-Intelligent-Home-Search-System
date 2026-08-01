from scripts.semantic_searcher import SemanticSearcher


def main() -> None:
    searcher = SemanticSearcher()
    searcher.load()

    query = "family home with a large backyard"

    results = searcher.search(
        query=query,
        top_k=5,
    )

    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    print("=" * 80)

    for result in results:
        print(
            f"\nRank: {result['rank']} | "
            f"Score: {result['similarity_score']:.4f}"
        )

        print(f"Listing ID: {result['L_ListingID']}")
        print(f"Address: {result.get('L_Address', 'N/A')}")
        print(f"City: {result.get('L_City', 'N/A')}")
        print(f"Price: ${result.get('price', 0):,.0f}")
        print(f"Beds: {result.get('beds', 'N/A')}")
        print(f"Baths: {result.get('baths', 'N/A')}")
        print(f"Remarks: {result.get('remarks', '')}")
        print("-" * 80)


if __name__ == "__main__":
    main()