from pathlib import Path

import pandas as pd


DATA_PATH = Path("data/processed/listing_sample_cleaned.csv")
OUTPUT_PATH = Path("data/processed/week3_labeled_sample.csv")
TEXT_COLUMN = "cleaned_remarks"
SAMPLE_SIZE = 250


def main():
    df = pd.read_csv(DATA_PATH)

    sample = (
        df[[TEXT_COLUMN]]
        .dropna()
        .drop_duplicates()
        .loc[lambda x: x[TEXT_COLUMN].str.strip() != ""]
        .sample(n=SAMPLE_SIZE, random_state=42)
        .reset_index(drop=True)
    )

    sample.insert(0, "record_id", range(1, len(sample) + 1))
    sample["bedrooms"] = ""
    sample["bathrooms"] = ""
    sample["price"] = ""
    sample["sqft"] = ""
    sample["amenities"] = ""

    sample.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(sample)} remarks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()