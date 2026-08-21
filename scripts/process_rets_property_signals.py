from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

import mysql.connector
from dotenv import load_dotenv

from scripts.signal_extractor import SignalExtractor
from scripts.text_cleaning import TextCleaner


# Load variables from the .env file in the project root.
load_dotenv()

OUTPUT_PATH = Path("data/processed/listing_signals.jsonl")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
}


def validate_db_config() -> None:
    """Fail early if a required database environment variable is missing."""
    missing = [
        key
        for key, value in DB_CONFIG.items()
        if value is None or str(value).strip() == ""
    ]

    if missing:
        raise ValueError(
            "Missing required database environment variables: "
            + ", ".join(missing)
        )


def iter_rets_property_rows() -> Iterator[dict[str, Any]]:
    """
    Stream listing records directly from the rets_property table.
    """
    validate_db_config()

    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                L_ListingID,
                L_Remarks
            FROM rets_property
            WHERE L_Remarks IS NOT NULL
              AND TRIM(L_Remarks) <> ''
        """

        cursor.execute(query)

        for row in cursor:
            yield row

    finally:
        cursor.close()
        connection.close()


def process_rets_property() -> None:
    """
    Process the rets_property table directly and save Week 6
    schema-aligned signals as JSONL.
    """
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    signal_extractor = SignalExtractor(
        taxonomy_path="taxonomy/taxonomy_week1.json"
    )
    text_cleaner = TextCleaner()

    processed_count = 0
    failed_count = 0

    print("Reading listings directly from rets_property...")
    print("Extracting Week 6 signals...")

    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        for row in iter_rets_property_rows():
            try:
                # Clean the raw MLS remarks before Week 3 / Week 6 extraction.
                cleaned_row = row.copy()
                cleaned_row["L_Remarks"] = text_cleaner.clean_text(
                    row.get("L_Remarks", "")
                )

                signals = signal_extractor.extract_signals(cleaned_row)

                output_file.write(
                    json.dumps(signals, ensure_ascii=False) + "\n"
                )

                processed_count += 1

                if processed_count % 1000 == 0:
                    print(f"Processed {processed_count} listings...")

            except Exception as exc:
                failed_count += 1
                print(
                    f"Failed listing {row.get('L_ListingID')}: {exc}"
                )

    print()
    print("Finished.")
    print(f"Successfully processed: {processed_count}")
    print(f"Failed: {failed_count}")
    print(f"Saved results to: {OUTPUT_PATH}")


if __name__ == "__main__":
    process_rets_property()
