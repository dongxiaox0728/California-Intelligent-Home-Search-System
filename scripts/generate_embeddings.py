from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data/processed/listing_full_cleaned.csv"
OUTPUT_PATH = PROJECT_ROOT / "data/models/listing_embeddings.npy"
ID_COLUMN = "L_ListingID"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TEXT_COLUMN = "cleaned_remarks"


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find the cleaned dataset at {DATA_PATH}"
        )

    dataset_hash = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    df = pd.read_csv(DATA_PATH, dtype={ID_COLUMN: str})
    if ID_COLUMN not in df.columns:
        raise ValueError(f"Required ID column '{ID_COLUMN}' was not found.")
    ids = df[ID_COLUMN].str.strip()
    if ids.isna().any() or ids.eq("").any() or ids.duplicated().any():
        raise ValueError("Listing IDs must be nonempty and unique.")

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
    if embeddings.ndim != 2 or len(embeddings) != len(ids) or not np.isfinite(embeddings).all():
        raise ValueError("Invalid embedding matrix.")
    if hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() != dataset_hash:
        raise ValueError("Dataset changed during embedding generation; retry with a fixed snapshot.")
    np.save(OUTPUT_PATH, embeddings)
    manifest = {
        "model_name": MODEL_NAME,
        "normalized": True,
        "text_column": TEXT_COLUMN,
        "dimensions": embeddings.shape[1],
        "listing_ids": ids.tolist(),
        "dataset_sha256": dataset_hash,
        "embeddings_sha256": hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest(),
    }
    OUTPUT_PATH.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("\nEmbedding generation complete.")
    print(f"Embedding shape: {embeddings.shape}")
    print(f"Embedding data type: {embeddings.dtype}")
    print(f"Saved embeddings to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()