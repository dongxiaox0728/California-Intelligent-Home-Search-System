from pathlib import Path
import json
import pandas as pd

from scripts.entity_extractor import EntityExtractor


DATA_PATH = Path("data/processed/listing_sample_cleaned.csv")
TEXT_COLUMN = "cleaned_remarks"
TAXONOMY_INPUT_PATH = "taxonomy/taxonomy_week1.json"
TAXONOMY_OUTPUT_PATH = "taxonomy/taxonomy_week3_amenities.json"


def main():
    df = pd.read_csv(DATA_PATH)

    extractor = EntityExtractor(TAXONOMY_INPUT_PATH)

    remarks = (
        df[TEXT_COLUMN]
        .dropna()
        .astype(str)
        .loc[lambda x: x.str.strip() != ""]
        .head(20)
    )

    results = []

    for index, remark in remarks.items():
        extracted = extractor.extract_all(remark)

        results.append(
            {
                "row": int(index),
                "cleaned_remarks": remark,
                "extracted_entities": extracted,
            }
        )

    with open(TAXONOMY_OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print(f"Saved results to {TAXONOMY_OUTPUT_PATH}")


if __name__ == "__main__":
    main()