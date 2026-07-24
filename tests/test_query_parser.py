from scripts.query_parser import QueryParser


parser = QueryParser()


def test_price_max():
    result = parser.parse("homes under 700k")
    assert result["price_max"] == 700000


def test_price_min():
    result = parser.parse("homes over 500k")
    assert result["price_min"] == 500000


def test_bedrooms():
    result = parser.parse("3 bedroom home")
    assert result["bedrooms"] == 3


def test_bathrooms():
    result = parser.parse("2.5 bathroom house")
    assert result["bathrooms"] == 2.5


def test_combined_query():
    result = parser.parse(
        "3 bed under 700k in Irvine with pool and no garage"
    )

    assert result["bedrooms"] == 3
    assert result["price_max"] == 700000
    assert result["city"] == "Irvine"
    assert "pool" in result["amenities"]
    assert "garage" in result["excluded_amenities"]