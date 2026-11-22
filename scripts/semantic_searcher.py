from __future__ import annotations

from pathlib import Path
import hashlib
import json
from collections.abc import Iterable
from typing import Any

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "data/models/listing_semantic.index"
METADATA_PATH = PROJECT_ROOT / "data/models/listing_metadata.csv"


class SemanticSearcher:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        index_path: Path = INDEX_PATH,
        metadata_path: Path = METADATA_PATH,
    ) -> None:
        self.model_name = model_name
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self._eligible_positions: dict[str, int] | None = None

        self.model: SentenceTransformer | None = None
        self.index: faiss.Index | None = None
        self.metadata: pd.DataFrame | None = None
    ##Load the embedding model, FAISS index, and listing metadata.
    def load(self) -> None:

        self._eligible_positions = None
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at: {self.index_path}"
            )

        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found at: {self.metadata_path}"
            )

        print(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name, device="cpu")

        print(f"Loading FAISS index: {self.index_path}")
        self.index = faiss.read_index(str(self.index_path))

        print(f"Loading metadata: {self.metadata_path}")
        self.metadata = pd.read_csv(self.metadata_path, dtype={"L_ListingID": str})

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
    ##Convert a query into an embedding and return the top matching listings.
    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:

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
    ##Verify the saved index/metadata pair before using listing-ID selection.
    def _prepare_eligible_positions(self) -> dict[str, int]:
        if self._eligible_positions is not None:
            return self._eligible_positions
        manifest_path = self.index_path.with_suffix(".json")
        if not manifest_path.exists():
            raise ValueError(
                "Filtered retrieval requires verified listing IDs. Run generate_embeddings.py "
                "and build_faiss_index.py to create manifests. Original search() still works."
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest["model_name"] != self.model_name
                or manifest["dimensions"] != self.index.d
                or manifest["index_sha256"] != hashlib.sha256(self.index_path.read_bytes()).hexdigest()
                or manifest["metadata_sha256"] != hashlib.sha256(self.metadata_path.read_bytes()).hexdigest()):
            raise ValueError("Model, index or metadata does not match the saved manifest.")
        ids = self.metadata["L_ListingID"].str.strip()
        if (ids.isna().any() or ids.eq("").any() or ids.duplicated().any()
                or ids.tolist() != manifest["listing_ids"]
                or self.metadata["faiss_position"].tolist() != list(range(len(ids)))):
            raise ValueError("Invalid listing-ID or FAISS-position alignment.")
        self._eligible_positions = {listing_id: position for position, listing_id in enumerate(ids)}
        return self._eligible_positions

    def search_eligible(
        self,
        query: str,
        eligible_ids: Iterable[str | int],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:

        if self.model is None or self.index is None or self.metadata is None:
            raise RuntimeError("SemanticSearcher has not been loaded. Call load() before search_eligible().")
        if not isinstance(query, str):
            raise TypeError("query must be a string.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer.")
        if isinstance(eligible_ids, (str, bytes)):
            raise TypeError("eligible_ids must be an iterable of listing IDs, not a single string.")
        requested = set()
        for value in eligible_ids:
            if value is None or isinstance(value, bool) or not isinstance(value, (str, int, np.integer)):
                raise ValueError("Eligible IDs must be nonempty strings or integers.")
            listing_id = str(value).strip()
            if not listing_id:
                raise ValueError("Eligible IDs cannot be empty.")
            requested.add(listing_id)
        if not requested:
            return []
        lookup = self._prepare_eligible_positions()
        missing = requested - lookup.keys()
        if missing:
            raise ValueError(f"{len(missing)} eligible listing IDs are missing from the index; check dataset alignment.")
        positions = np.array(sorted(lookup[listing_id] for listing_id in requested), dtype=np.int64)
        scores = None
        if query.strip():
            query_vector = np.asarray(self.model.encode(
                [query.strip()], convert_to_numpy=True, normalize_embeddings=True,
            ), dtype=np.float32)
            if (query_vector.shape != (1, self.index.d)
                    or not np.isfinite(query_vector).all()
                    or np.linalg.norm(query_vector) == 0):
                raise ValueError("Query embedding is invalid or incompatible with the index.")
            # Reuse the normalized vectors already saved in the flat FAISS index.
            vectors = np.vstack([self.index.reconstruct(int(pos)) for pos in positions])
            scores = vectors @ query_vector[0]
            order = np.argsort(-scores, kind="stable")[:top_k]
        else:
            order = np.arange(min(top_k, len(positions)))
        results = []
        for rank, offset in enumerate(order, start=1):
            position = int(positions[offset])
            listing = self.metadata.iloc[position].to_dict()
            listing.update(rank=rank, faiss_position=position,
                           similarity_score=None if scores is None else float(scores[offset]))
            results.append(listing)
        return results
