import json
import os

import pandas as pd


def test_taxonomy_loaded():
    taxonomy_path = "data/processed/taxonomy.json"

    assert os.path.exists(taxonomy_path), (
        "taxonomy.json does not exist. "
        "Create data/processed/taxonomy.json first."
    )

    with open(taxonomy_path, "r", encoding="utf-8") as f:
        tax = json.load(f)

    assert "terms" in tax, "taxonomy.json must contain a 'terms' list."
    assert len(tax["terms"]) >= 200, "Taxonomy should contain at least 200 terms."

    assert all(
        "id" in t and "term" in t for t in tax["terms"]
    ), "Each taxonomy term must contain both 'id' and 'term'."


def test_sample_data_quality():
    sample_path = "data/processed/listing_sample.csv"

    assert os.path.exists(sample_path), (
        "listing_sample.csv does not exist. "
        "Run scripts/data_loading.py first."
    )

    df = pd.read_csv(sample_path)

    assert len(df) >= 500, "Sample dataset should contain at least 500 rows."
    assert "remarks" in df.columns, "CSV must contain a 'remarks' column."
    assert df["remarks"].notna().all(), "Remarks should not contain missing values."
    assert df["remarks"].str.len().min() > 50, (
        "Every remark should be longer than 50 characters."
    )