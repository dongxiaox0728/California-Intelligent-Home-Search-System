from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


DATA_PATH = Path("data/processed/listing_sample_cleaned.csv")
OUTPUT_PATH = Path("data/models/listing_embeddings.npy")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TEXT_COLUMN = "cleaned_remarks"


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find the cleaned dataset at {DATA_PATH}"
        )

    df = pd.read_csv(DATA_PATH)

    if TEXT_COLUMN not in df.columns:
        raise ValueError(
            f"Required column '{TEXT_COLUMN}' was not found."
        )

    remarks = df[TEXT_COLUMN].fillna("").astype(str).str.strip()

    empty_count = remarks.eq("").sum()

    if empty_count > 0:
        raise ValueError(
            f"Found {empty_count} empty cleaned remarks."
        )

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print(f"Generating embeddings for {len(remarks):,} listings...")

    embeddings = model.encode(
        remarks.tolist(),
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(OUTPUT_PATH, embeddings)

    print("\nEmbedding generation complete.")
    print(f"Embedding shape: {embeddings.shape}")
    print(f"Embedding data type: {embeddings.dtype}")
    print(f"Saved embeddings to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()