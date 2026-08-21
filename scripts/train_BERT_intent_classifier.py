from __future__ import annotations

import random

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from pathlib import Path
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

# Configuration

DATA_PATH = "data/processed/week7_real_estate_search_queries_210_labeled.csv"
MODEL_NAME = "distilbert-base-uncased"

CHECKPOINT_DIR = "data/models/intent_classifier_checkpoints"
FINAL_MODEL_DIR = "data/models/intent_classifier"

TEST_SIZE = 0.20
RANDOM_SEED = 42
MAX_LENGTH = 64


LABEL2ID = {
    "browsing": 0,
    "researching": 1,
    "high_intent_inquiry": 2,
}

ID2LABEL = {
    0: "browsing",
    1: "researching",
    2: "high_intent_inquiry",
}


# Reproducibility

def set_seed(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# Dataset loading

def load_and_split_data() -> tuple[pd.DataFrame, pd.DataFrame]:

    df = pd.read_csv(DATA_PATH)

    required_columns = {"Query", "Intent"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {sorted(missing_columns)}"
        )

    df["Query"] = df["Query"].astype(str).str.strip()
    df["Intent"] = df["Intent"].astype(str).str.strip()

    df = df[
        (df["Query"] != "")
        & (df["Intent"].isin(LABEL2ID))
    ].copy()

    df["label"] = df["Intent"].map(LABEL2ID)

    if len(df) == 0:
        raise ValueError("No valid labeled examples were found in the dataset.")

    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=df["label"],
    )

    return train_df, test_df

# Evaluation metrics

def compute_metrics(eval_pred) -> dict[str, float]:

    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    accuracy = accuracy_score(labels, predictions)

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels,
        predictions,
        average="macro",
        zero_division=0,
    )

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }

# Training

def train() -> None:
    set_seed()

    print("Loading dataset...")
    train_df, test_df = load_and_split_data()

    print(f"Training examples: {len(train_df)}")
    print(f"Test examples: {len(test_df)}")

    print("\nTraining label distribution:")
    print(train_df["Intent"].value_counts())

    print("\nTest label distribution:")
    print(test_df["Intent"].value_counts())

    train_dataset = Dataset.from_pandas(
        train_df[["Query", "label"]],
        preserve_index=False,
    )

    test_dataset = Dataset.from_pandas(
        test_df[["Query", "label"]],
        preserve_index=False,
    )

    print(f"\nLoading tokenizer: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def tokenize_batch(batch):
        return tokenizer(
            batch["Query"],
            truncation=True,
            max_length=MAX_LENGTH,
        )

    print("Tokenizing datasets...")
    train_dataset = train_dataset.map(
        tokenize_batch,
        batched=True,
        remove_columns=["Query"],
    )

    test_dataset = test_dataset.map(
        tokenize_batch,
        batched=True,
        remove_columns=["Query"],
    )

    # Dynamically pad each batch rather than padding every query to MAX_LENGTH.
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    print("Loading pretrained DistilBERT classification model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL2ID),
        label2id=LABEL2ID,
        id2label=ID2LABEL,
    )

    training_args = TrainingArguments(
        output_dir=CHECKPOINT_DIR,

        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=4,
        weight_decay=0.01,

        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="epoch",

        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,

        save_total_limit=2,
        report_to="none",
        seed=RANDOM_SEED,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        data_collator=data_collator,
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
    )

    print("\nStarting DistilBERT fine-tuning...")
    trainer.train()

    print("\nEvaluating best model on held-out test set...")
    results = trainer.evaluate()

    print("\nFinal evaluation:")
    for metric_name, value in results.items():
        if isinstance(value, float):
            print(f"{metric_name}: {value:.4f}")
        else:
            print(f"{metric_name}: {value}")

    # Save the best model and tokenizer so query_intent_classifier.py
    # can load them later for inference.
    Path(FINAL_MODEL_DIR).mkdir(parents=True, exist_ok=True)

    trainer.save_model(FINAL_MODEL_DIR)
    tokenizer.save_pretrained(FINAL_MODEL_DIR)

    print(f"\nSaved final model to: {FINAL_MODEL_DIR}")


if __name__ == "__main__":
    train()
