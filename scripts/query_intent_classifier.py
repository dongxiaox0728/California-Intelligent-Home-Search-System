from __future__ import annotations

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# Configuration

MODEL_DIR = "data/models/intent_classifier"
MAX_LENGTH = 64


# Load model once

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)

model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.to(device)
model.eval()


def predict_intent(query: str) -> dict[str, float | str]:

    query = query.strip()

    if not query:
        raise ValueError("Query cannot be empty.")

    inputs = tokenizer(
        query,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits

    probabilities = torch.softmax(logits, dim=-1)

    predicted_id = torch.argmax(probabilities, dim=-1).item()
    confidence = probabilities[0, predicted_id].item()

    intent = model.config.id2label[predicted_id]

    return {
        "intent": intent,
        "confidence": confidence,
    }


def main() -> None:
    print("Real Estate Query Intent Classifier")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        query = input("Enter a real-estate query: ").strip()

        if query.lower() in {"quit", "exit"}:
            print("Exiting classifier.")
            break

        if not query:
            print("Please enter a query.\n")
            continue

        result = predict_intent(query)

        print(f"Intent: {result['intent']}")
        print(f"Confidence: {result['confidence']:.2%}\n")


if __name__ == "__main__":
    main()
