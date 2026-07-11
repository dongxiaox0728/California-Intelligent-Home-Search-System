import json
from pathlib import Path

import pandas as pd

from scripts.entity_extractor import EntityExtractor


DATA_PATH = Path("data/processed/week3_test.csv")
TAXONOMY_PATH = "taxonomy/taxonomy_week1.json"
OUTPUT_PATH = Path("data/processed/entity_metrics.json")

ENTITIES = [
    "bedrooms",
    "bathrooms",
    "price",
    "sqft",
]


def normalize_value(value, entity):
    if pd.isna(value) or str(value).strip() == "":
        return None

    if entity == "bathrooms":
        return float(value)

    return int(float(value))


def update_counts(gold, predicted):
    if gold is None and predicted is None:
        return 0, 0, 0

    if gold == predicted:
        return 1, 0, 0

    if gold is None and predicted is not None:
        return 0, 1, 0

    if gold is not None and predicted is None:
        return 0, 0, 1

    return 0, 1, 1


def calculate_metrics(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    if precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def main():
    df = pd.read_csv(DATA_PATH)
    extractor = EntityExtractor(TAXONOMY_PATH)

    counts = {
        entity: {"tp": 0, "fp": 0, "fn": 0}
        for entity in ENTITIES
    }

    for _, row in df.iterrows():
        remark = str(row["cleaned_remarks"])
        prediction = extractor.extract_all(remark)

        for entity in ENTITIES:
            gold = normalize_value(row[entity], entity)
            predicted = prediction[entity]

            tp, fp, fn = update_counts(gold, predicted)

            counts[entity]["tp"] += tp
            counts[entity]["fp"] += fp
            counts[entity]["fn"] += fn

    results = {}

    for entity, values in counts.items():
        results[entity] = calculate_metrics(
            values["tp"],
            values["fp"],
            values["fn"],
        )

    total_tp = sum(values["tp"] for values in counts.values())
    total_fp = sum(values["fp"] for values in counts.values())
    total_fn = sum(values["fn"] for values in counts.values())

    results["overall"] = calculate_metrics(
        total_tp,
        total_fp,
        total_fn,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()