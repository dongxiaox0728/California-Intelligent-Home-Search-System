from scripts.query_parser import QueryParser
import pytest

parser = QueryParser()


def test_sql_generation():
    filters = parser.parse("3 bed under 700k in Irvine")

    sql, params = parser.to_sql(filters)

    assert "L_SystemPrice <= %s" in sql
    assert "L_Keyword2 = %s" in sql
    assert "L_City = %s" in sql

    assert 700000 in params
    assert 3 in params
    assert "Irvine" in params


def test_values_are_not_inserted_into_sql():
    filters = parser.parse("3 bed under 700k in Irvine")

    sql, params = parser.to_sql(filters)

    assert "700000" not in sql
    assert "Irvine" not in sql


def test_sql_injection_protection():
    malicious_city = "Irvine'; DROP TABLE rets_property; --"

    with pytest.raises(ValueError, match="invalid city"):
        parser.to_sql({"city": malicious_city})