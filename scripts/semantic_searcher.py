from __future__ import annotations

from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

INDEX_PATH = Path("data/models/listing_semantic.index")
METADATA_PATH = Path("data/models/listing_metadata.csv")


class SemanticSearcher:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        index_path: Path = INDEX_PATH,
        metadata_path: Path = METADATA_PATH,
    ) -> None:
        self.model_name = model_name
        self.index_path = index_path
        self.metadata_path = metadata_path

        self.model: SentenceTransformer | None = None
        self.index: faiss.Index | None = None
        self.metadata: pd.DataFrame | None = None

    def load(self) -> None:
        """
        Load the embedding model, FAISS index, and listing metadata.
        """
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at: {self.index_path}"
            )

        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found at: {self.metadata_path}"
            )

        print(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)

        print(f"Loading FAISS index: {self.index_path}")
        self.index = faiss.read_index(str(self.index_path))

        print(f"Loading metadata: {self.metadata_path}")
        self.metadata = pd.read_csv(self.metadata_path)

        if self.index.ntotal != len(self.metadata):
            raise ValueError(
                "FAISS index and metadata row counts do not match:\n"
                f"- Indexed vectors: {self.index.ntotal:,}\n"
                f"- Metadata rows: {len(self.metadata):,}"
            )

        print(
            f"Semantic searcher loaded successfully with "
            f"{self.index.ntotal:,} listings."
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Convert a query into an embedding and return the top matching listings.
        """
        if self.model is None or self.index is None or self.metadata is None:
            raise RuntimeError(
                "SemanticSearcher has not been loaded. "
                "Call load() before search()."
            )

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        top_k = min(top_k, self.index.ntotal)

        query_embedding = self.model.encode(
            [query.strip()],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        scores, positions = self.index.search(
            query_embedding,
            top_k,
        )

        results: list[dict[str, Any]] = []

        for rank, (position, score) in enumerate(
            zip(positions[0], scores[0]),
            start=1,
        ):
            if position == -1:
                continue

            listing = self.metadata.iloc[position].to_dict()

            listing["rank"] = rank
            listing["similarity_score"] = float(score)
            listing["faiss_position"] = int(position)

            results.append(listing)

        return results