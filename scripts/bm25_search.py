from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi


DATA_PATH = Path("data/processed/listing_full_cleaned.csv")
TEXT_COLUMN = "cleaned_remarks"


def clean_value(value: Any) -> Any:

    if pd.isna(value):
        return None

    if isinstance(value, np.generic):
        return value.item()

    return value


class BM25Searcher:
    def __init__(
        self,
        data_path: Path = DATA_PATH,
        text_column: str = TEXT_COLUMN,
    ) -> None:
        self.data_path = data_path
        self.text_column = text_column

        self.metadata: pd.DataFrame | None = None
        self.bm25: BM25Okapi | None = None

    ##Convert text into lowercase alphanumeric tokens.
    @staticmethod
    def tokenize(text: str) -> list[str]:
        
        return re.findall(r"\b[a-z0-9]+\b", text.lower())

    
    ##Load the listing dataset and build the BM25 corpus. 
    def load(self) -> None:
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Dataset not found at: {self.data_path}"
            )

        self.metadata = pd.read_csv(self.data_path)

        if self.text_column not in self.metadata.columns:
            raise ValueError(
                f"Required column '{self.text_column}' was not found."
            )

        remarks = (
            self.metadata[self.text_column]
            .fillna("")
            .astype(str)
            .tolist()
        )

        tokenized_corpus = [
            self.tokenize(remark)
            for remark in remarks
        ]

        self.bm25 = BM25Okapi(tokenized_corpus)

        print(
            f"BM25 searcher loaded successfully with "
            f"{len(self.metadata):,} listings."
        )

    ##Return listings with the highest BM25 keyword scores.
    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:

        if self.metadata is None or self.bm25 is None:
            raise RuntimeError(
                "BM25Searcher has not been loaded. "
                "Call load() before search()."
            )

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        top_k = min(top_k, len(self.metadata))

        query_tokens = self.tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        top_positions = np.argsort(scores)[::-1][:top_k]

        results: list[dict[str, Any]] = []

        for rank, position in enumerate(top_positions, start=1):
            row = self.metadata.iloc[position]

            # Convert pandas / NumPy values into JSON-safe Python values.
            listing = {
                key: clean_value(value)
                for key, value in row.items()
            }

            listing["rank"] = int(rank)
            listing["bm25_score"] = float(scores[position])
            listing["dataset_position"] = int(position)

            results.append(listing)

        return results