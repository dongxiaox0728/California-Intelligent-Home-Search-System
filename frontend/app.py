import streamlit as st
import requests

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Real Estate Intelligent Search",
    layout="wide"
)

st.title("Real Estate Intelligent Search")

query = st.text_input(
    "What are you looking for?",
    placeholder="e.g. houses with beach view"
)

top_k = st.slider(
    "Number of results",
    min_value=1,
    max_value=10,
    value=5
)

def post_json(endpoint: str, payload: dict) -> dict:
    response = requests.post(
        f"{API_BASE_URL}{endpoint}",
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"{endpoint} returned {response.status_code}: {response.text}"
        )

    return response.json()


def first_available(listing: dict, keys: list[str], default=None):
    for key in keys:
        value = listing.get(key)
        if value is not None and value != "":
            return value
    return default


if st.button("Search"):
    if not query.strip():
        st.warning("Please enter a search query.")
    else:
        try:
            # Step 1: check the user query for Fair Housing compliance.
            with st.spinner("Checking query compliance..."):
                compliance = post_json(
                    "/check-compliance",
                    {"text": query}
                )

            violations = compliance.get("violations", [])
            is_compliant = compliance.get(
                "compliant",
                len(violations) == 0
            )

            # If there is any warning/violation, stop and show it.
            if (not is_compliant) or violations:
                st.error(
                    "This search cannot be processed because the query "
                    "triggered a Fair Housing compliance warning."
                )

                for violation in violations:
                    severity = str(
                        violation.get("severity", "warning")
                    ).upper()

                    category = violation.get(
                        "category",
                        "Compliance"
                    )

                    message = violation.get(
                        "message",
                        "This query contains potentially restricted language."
                    )

                    st.warning(
                        f"{severity} — {category}: {message}"
                    )

            else:
                # Step 2: semantic search.
                with st.spinner("Searching listings..."):
                    search_data = post_json(
                        "/search",
                        {
                            "query": query,
                            "top_k": top_k
                        }
                    )

                results = search_data.get("results", [])
                count = search_data.get("count", len(results))

                st.success(f"Found {count} listings")

                if not results:
                    st.info("No matching listings were found.")

                # Step 3: summarize each listing's remarks.
                for i, listing in enumerate(results, start=1):
                    address = first_available(
                        listing,
                        ["L_Address", "address", "Address"],
                        f"Listing {i}"
                    )

                    price = first_available(
                        listing,
                        ["L_SystemPrice", "price", "Price"]
                    )

                    bedrooms = first_available(
                        listing,
                        ["L_Keyword2", "bedrooms", "beds"]
                    )

                    bathrooms = first_available(
                        listing,
                        ["LM_Dec_3", "bathrooms", "baths"]
                    )

                    listing_id = first_available(
                        listing,
                        ["L_ListingID", "listing_id", "id"]
                    )

                    remarks = first_available(
                        listing,
                        ["L_Remarks", "remarks", "description"],
                        ""
                    )

                    similarity_score = listing.get(
                        "similarity_score"
                    )

                    st.subheader(address)

                    details = []

                    if listing_id is not None:
                        details.append(
                            f"Listing ID: {listing_id}"
                        )

                    if price is not None:
                        try:
                            details.append(
                                f"Price: ${float(price):,.0f}"
                            )
                        except (TypeError, ValueError):
                            details.append(
                                f"Price: {price}"
                            )

                    if bedrooms is not None:
                        details.append(
                            f"Beds: {bedrooms}"
                        )

                    if bathrooms is not None:
                        details.append(
                            f"Baths: {bathrooms}"
                        )

                    if similarity_score is not None:
                        try:
                            details.append(
                                "Similarity: "
                                f"{float(similarity_score):.3f}"
                            )
                        except (TypeError, ValueError):
                            details.append(
                                f"Similarity: {similarity_score}"
                            )

                    if details:
                        st.write(" | ".join(details))

                    if remarks:
                        try:
                            summary_data = post_json(
                                "/summarize",
                                {
                                    "remarks": str(remarks),
                                    "num_sentences": 3
                                }
                            )

                            summary = summary_data.get(
                                "summary",
                                "No summary available."
                            )

                            st.markdown("**Summary**")
                            st.write(summary)

                            with st.expander(
                                "View original remarks"
                            ):
                                st.write(remarks)

                        except Exception as summary_error:
                            st.warning(
                                "Summary could not be generated: "
                                f"{summary_error}"
                            )

                            with st.expander(
                                "View original remarks"
                            ):
                                st.write(remarks)

                    else:
                        st.write(
                            "No listing remarks available to summarize."
                        )

                    st.divider()

        except requests.exceptions.ConnectionError:
            st.error(
                "Could not connect to the FastAPI server. "
                "Make sure it is running on "
                "http://127.0.0.1:8000."
            )

        except requests.exceptions.Timeout:
            st.error(
                "The API request timed out. "
                "The semantic model may still be loading."
            )

        except Exception as e:
            st.error(f"Something went wrong: {e}")
