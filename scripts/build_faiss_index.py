from pathlib import Path

import faiss
import numpy as np
import pandas as pd


EMBEDDINGS_PATH = Path("data/models/listing_embeddings.npy")
DATA_PATH = Path("data/processed/listing_full_cleaned.csv")

INDEX_OUTPUT_PATH = Path("data/models/listing_semantic.index")
METADATA_OUTPUT_PATH = Path("data/models/listing_metadata.csv")

ID_COLUMN = "L_ListingID"


def main() -> None:
    # 1. Confirm that all required input files exist.
    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(
            f"Could not find embeddings at: {EMBEDDINGS_PATH}\n"
            "Run generate_embeddings.py first."
        )

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find dataset at: {DATA_PATH}"
        )

    # 2. Load the previously generated embeddings.
    embeddings = np.load(EMBEDDINGS_PATH)

    # FAISS expects float32 vectors.
    embeddings = np.asarray(embeddings, dtype=np.float32)

    print("=" * 60)
    print("EMBEDDING INFORMATION")
    print("=" * 60)
    print(f"Number of embeddings: {embeddings.shape[0]:,}")
    print(f"Embedding dimensions: {embeddings.shape[1]}")
    print(f"Data type: {embeddings.dtype}")

    if embeddings.ndim != 2:
        raise ValueError(
            f"Expected a two-dimensional embedding matrix, "
            f"but received shape {embeddings.shape}."
        )

    # 3. Load the listing data.
    df = pd.read_csv(DATA_PATH)

    if ID_COLUMN not in df.columns:
        raise ValueError(
            f"Required ID column '{ID_COLUMN}' was not found."
        )

    # Each embedding must correspond to exactly one dataset row.
    if len(df) != len(embeddings):
        raise ValueError(
            "Dataset and embedding counts do not match:\n"
            f"- Dataset rows: {len(df):,}\n"
            f"- Embeddings: {len(embeddings):,}\n"
            "Regenerate the embeddings from the current dataset."
        )

    # 4. Normalize the vectors.
    #
    # Your embedding script already used normalize_embeddings=True,
    # but normalizing again is safe and guarantees the index receives
    # unit-length vectors.
    faiss.normalize_L2(embeddings)

    # 5. Create an exact inner-product index.
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)

    # 6. Add all listing embeddings to the index.
    index.add(embeddings)

    # 7. Verify that every embedding was added.
    if index.ntotal != len(df):
        raise RuntimeError(
            f"Expected {len(df):,} indexed vectors, "
            f"but FAISS contains {index.ntotal:,}."
        )

    # 8. Save the FAISS index.
    INDEX_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_OUTPUT_PATH))

    # 9. Save listing metadata in the same row order.
    #
    # FAISS returns row positions such as 0, 15, or 248.
    # This file lets us map those positions back to real listings.
    metadata = df.reset_index(drop=True).copy()
    metadata.insert(0, "faiss_position", metadata.index)

    metadata.to_csv(METADATA_OUTPUT_PATH, index=False)

    print("\n" + "=" * 60)
    print("FAISS INDEX CREATED")
    print("=" * 60)
    print(f"Index type: {type(index).__name__}")
    print(f"Vectors indexed: {index.ntotal:,}")
    print(f"Dimensions: {index.d}")
    print(f"Index saved to: {INDEX_OUTPUT_PATH}")
    print(f"Metadata saved to: {METADATA_OUTPUT_PATH}")


if __name__ == "__main__":
    main()