from pathlib import Path
import hashlib
import json
import warnings

import faiss
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMBEDDINGS_PATH = PROJECT_ROOT / "data/models/listing_embeddings.npy"
DATA_PATH = PROJECT_ROOT / "data/processed/listing_full_cleaned.csv"

INDEX_OUTPUT_PATH = PROJECT_ROOT / "data/models/listing_semantic.index"
METADATA_OUTPUT_PATH = PROJECT_ROOT / "data/models/listing_metadata.csv"

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

    if embeddings.ndim != 2 or not embeddings.size:
        raise ValueError(f"Expected a nonempty two-dimensional matrix, got {embeddings.shape}.")
    if not np.isfinite(embeddings).all() or np.any(np.linalg.norm(embeddings, axis=1) == 0):
        raise ValueError("Embeddings must be finite and nonzero.")

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
    df = pd.read_csv(DATA_PATH, dtype={ID_COLUMN: str})

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

    ids = df[ID_COLUMN].str.strip()
    if ids.isna().any() or ids.eq("").any() or ids.duplicated().any():
        raise ValueError("Listing IDs must be nonempty and unique.")
    df[ID_COLUMN] = ids
    manifest_path = EMBEDDINGS_PATH.with_suffix(".json")
    manifest = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest["listing_ids"] != ids.tolist()
                or manifest["dataset_sha256"] != hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
                or manifest["embeddings_sha256"] != hashlib.sha256(EMBEDDINGS_PATH.read_bytes()).hexdigest()
                or manifest["dimensions"] != embeddings.shape[1]
                or manifest["normalized"] is not True):
            raise ValueError("Dataset, IDs or embeddings do not match the generation manifest. Regenerate embeddings.")
    else:
        warnings.warn("Legacy embeddings have no alignment manifest. Baseline search remains available; "
                      "regenerate embeddings and rebuild the index to enable search_eligible().")

    # 4. Normalize the vectors.
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
    metadata = df.reset_index(drop=True).copy()
    metadata.insert(0, "faiss_position", metadata.index)

    metadata.to_csv(METADATA_OUTPUT_PATH, index=False)
    index_manifest_path = INDEX_OUTPUT_PATH.with_suffix(".json")
    if manifest is not None:
        index_manifest = {
            "model_name": manifest["model_name"],
            "dimensions": index.d,
            "listing_ids": ids.tolist(),
            "index_sha256": hashlib.sha256(INDEX_OUTPUT_PATH.read_bytes()).hexdigest(),
            "metadata_sha256": hashlib.sha256(METADATA_OUTPUT_PATH.read_bytes()).hexdigest(),
        }
        index_manifest_path.write_text(json.dumps(index_manifest, indent=2) + "\n", encoding="utf-8")
    else:
        index_manifest_path.unlink(missing_ok=True)

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