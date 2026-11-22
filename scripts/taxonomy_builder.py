import os
import re
from collections import Counter

import nltk
import pandas as pd
from nltk.corpus import stopwords
from nltk.util import ngrams


INPUT_FILE = "data/processed/listing_sample.csv"
OUTPUT_FILE = "data/processed/top_bigrams.csv"


def download_nltk_resources():

    resources = [
        ("tokenizers/punkt", "punkt"),
        ("corpora/stopwords", "stopwords"),
    ]

    for resource_path, download_name in resources:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            nltk.download(download_name)


def clean_text(text):
    
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_stop_words():

    stop_words = set(stopwords.words("english"))

    custom_stop_words = {
        # General filler words
        "just", "also", "even", "still", "really", "very", "much",
        "many", "more", "most", "less", "well", "may", "might",
        "could", "would", "should", "get", "gets", "got",
        "make", "makes", "made", "come", "comes", "coming",
        "see", "look", "looks", "looking",

        # Generic listing / real-estate words
        "home", "property", "properties", "house", "unit", "units",
        "room", "rooms", "area", "areas", "main",

        # Marketing filler
        "welcome", "beautiful", "charming", "amazing", "wonderful",
        "perfect", "great", "rare", "opportunity", "lovely",
        "stunning", "desirable", "fantastic", "gorgeous",

        # Listing boilerplate
        "please", "contact", "information", "buyer", "buyers",
        "seller", "sellers", "agent", "agents", "listing", "listed",
        "showing", "showings",
    }

    return stop_words | custom_stop_words


def extract_bigrams(text_series, top_n=200):

    stop_words = get_stop_words()
    freq = Counter()

    for text in text_series.dropna().astype(str):
        cleaned_text = clean_text(text)
        tokens = nltk.word_tokenize(cleaned_text)

        for first, second in ngrams(tokens, 2):
            if (
                first not in stop_words
                and second not in stop_words
                and len(first) > 2
                and len(second) > 2
                and not first.isdigit()
                and not second.isdigit()
            ):
                freq[(first, second)] += 1

    results = []

    for bigram, count in freq.most_common(top_n):
        results.append({
            "bigram": " ".join(bigram),
            "count": count,
        })

    return pd.DataFrame(results)


def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"{INPUT_FILE} does not exist. "
            "Run scripts/data_loading.py first."
        )

    os.makedirs("data/processed", exist_ok=True)

    print(f"Reading {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)

    if "remarks" not in df.columns:
        raise ValueError("The CSV file must contain a column named 'remarks'.")

    print("Extracting top 200 bigrams...")
    bigram_df = extract_bigrams(df["remarks"], top_n=200)

    bigram_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved top bigrams to {OUTPUT_FILE}")
    print()
    print("Top 20 bigrams:")
    print(bigram_df.head(20).to_string(index=False))


if __name__ == "__main__":
    download_nltk_resources()
    main()
