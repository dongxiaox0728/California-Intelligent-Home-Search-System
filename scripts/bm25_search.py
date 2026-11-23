from __future__ import annotations

import math
import re
from array import array
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATA_PATH = Path("data/processed/listing_full_cleaned.csv")
TEXT_COLUMN = "cleaned_remarks"


class BM25Index:
    K1 = 1.5
    B = 0.75
    EPSILON = 0.25

    def __init__(self, corpus: Iterable[list[str]]) -> None:
        self.postings: dict[str, tuple[array, array]] = {}
        lengths = []
        for position, tokens in enumerate(corpus):
            lengths.append(len(tokens))
            for token, count in Counter(tokens).items():
                if token not in self.postings:
                    self.postings[token] = (array("I"), array("I"))
                positions, frequencies = self.postings[token]
                positions.append(position)
                frequencies.append(count)

        if not self.postings:
            raise ValueError("The BM25 dataset contains no searchable words.")

        self.size = len(lengths)
        average_length = sum(lengths) / self.size
        self.normalization = self.K1 * (1 - self.B + self.B * np.asarray(lengths) / average_length)
        idf = {}
        idf_sum = 0.0
        for token, (positions, _) in self.postings.items():
            document_frequency = len(positions)
            value = math.log(self.size - document_frequency + 0.5) - math.log(document_frequency + 0.5)
            idf[token] = value
            idf_sum += value

        # Match BM25Okapi's floor for terms that appear in more than half the corpus.
        idf_floor = self.EPSILON * (idf_sum / len(idf))
        self.idf = {token: value if value >= 0 else idf_floor for token, value in idf.items()}

    def get_scores(self, query: Iterable[str]) -> np.ndarray:
        scores = np.zeros(self.size)
        for token in query:
            posting = self.postings.get(token)
            if posting is None:
                continue
            position_buffer, frequency_buffer = posting
            positions = np.frombuffer(position_buffer, dtype=np.uintc)
            frequencies = np.frombuffer(frequency_buffer, dtype=np.uintc)
            scores[positions] += self.idf[token] * (
                frequencies * (self.K1 + 1) / (frequencies + self.normalization[positions])
            )
        return scores


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
        self.bm25: BM25Index | None = None

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

        metadata = pd.read_csv(self.data_path)

        if self.text_column not in metadata.columns:
            raise ValueError(
                f"Required column '{self.text_column}' was not found."
            )

        remarks = metadata[self.text_column].fillna("").astype(str)
        index = BM25Index(self.tokenize(remark) for remark in remarks)
        self.metadata, self.bm25 = metadata, index

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
