import re
import csv
import nltk
from pathlib import Path
from typing import Dict, List, Tuple


class ListingSummarizer:

    CATEGORY_KEYWORDS = {
        "interior_features": [
            "kitchen", "floor", "floors", "hardwood", "carpet", "bath", "bathroom",
            "bedroom", "closet", "fireplace", "appliances", "stainless", "granite",
            "counter", "cabinet", "suite",
        ],
        "exterior_features": [
            "garage", "yard", "patio", "deck", "porch", "roof", "driveway",
            "fence", "pool", "landscaping", "lot", "backyard",
        ],
        "location_neighborhood": [
            "school", "schools", "downtown", "shopping", "park", "parks",
            "near", "close", "neighborhood", "transportation", "train", "highway",
        ],
        "property_condition": [
            "updated", "renovated", "new", "fresh", "remodeled", "modern",
            "move in ready", "move-in ready", "maintained", "improvements",
        ],
        "layout_space": [
            "open concept", "floor plan", "basement", "room", "space",
            "living", "dining", "family", "level", "story",
        ],
        "financial_terms": [
            "price", "affordable", "investment", "rental", "income",
            "hoa", "tax", "taxes", "value",
        ],
        "utilities_systems": [
            "hvac", "heating", "cooling", "air", "water", "sewer",
            "electric", "mechanical", "furnace",
        ],
        "general_marketing": [
            "beautiful", "charming", "spacious", "must", "rare",
            "opportunity", "welcome", "perfect", "amazing",
        ],
    }

    FEATURE_EXCLUSIONS = {
        "bedroom",
        "bath",
        "bathroom",
        "price",
    }

    def __init__(
        self,
        listings_path: str | Path = "data/processed/listing_sample_cleaned.csv",
    ) -> None:
        self._ensure_nltk_tokenizer()
        self.feature_keywords = self._flatten_feature_keywords()
        self.valid_cities = self._load_cities(Path(listings_path))

    def _ensure_nltk_tokenizer(self) -> None:
        """Ensure NLTK sentence-tokenization resources are available."""
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)

        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            try:
                nltk.download("punkt_tab", quiet=True)
            except Exception:
                pass

    def _flatten_feature_keywords(self) -> List[str]:

        keywords = set()

        for category_words in self.CATEGORY_KEYWORDS.values():
            for keyword in category_words:
                normalized = keyword.strip().lower()
                if normalized and normalized not in self.FEATURE_EXCLUSIONS:
                    keywords.add(normalized)

        # Longer phrases first is useful for readability/debugging.
        return sorted(keywords, key=lambda x: (-len(x.split()), -len(x), x))

    @staticmethod
    def contains_bedroom_info(sentence: str) -> bool:

        pattern = r"\b\d+(?:\.\d+)?\s*[- ]?\s*(?:bedrooms?|beds?|bd|bdrm)\b"
        return bool(re.search(pattern, sentence, flags=re.IGNORECASE))

    @staticmethod
    def contains_bathroom_info(sentence: str) -> bool:

        pattern = r"\b\d+(?:\.\d+)?\s*[- ]?\s*(?:bathrooms?|baths?|ba)\b"
        return bool(re.search(pattern, sentence, flags=re.IGNORECASE))

    @staticmethod
    def contains_price_info(sentence: str) -> bool:

        pattern = r"\$\s*\d[\d,]*(?:\.\d+)?\s*[kKmM]?\b"
        return bool(re.search(pattern, sentence))

    def contains_city_info(self, sentence: str) -> bool:

        for city in self.valid_cities:
            city_pattern = rf"(?<!\w){re.escape(city)}(?!\w)"
            if re.search(city_pattern, sentence, flags=re.IGNORECASE):
                return True

        return False

    def count_feature_occurrences(self, sentence: str) -> int:

        total = 0

        for keyword in self.feature_keywords:
            # Use word-style boundaries so "park" does not match "parking".
            pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
            matches = re.findall(pattern, sentence, flags=re.IGNORECASE)
            total += len(matches)

        return total

    def score_sentence(self, sentence: str) -> Tuple[int, Dict[str, int]]:
        """
        Score one sentence and return both the total score and a breakdown.
        """
        breakdown = {
            "bedroom": 0,
            "bathroom": 0,
            "price": 0,
            "city": 0,
            "features": 0,
        }

        if self.contains_bedroom_info(sentence):
            breakdown["bedroom"] = 3

        if self.contains_bathroom_info(sentence):
            breakdown["bathroom"] = 3

        if self.contains_price_info(sentence):
            breakdown["price"] = 3

        if self.contains_city_info(sentence):
            breakdown["city"] = 3

        breakdown["features"] = self.count_feature_occurrences(sentence)

        total_score = sum(breakdown.values())
        return total_score, breakdown

    def extractive_summary(
        self,
        remarks: str,
        num_sentences: int = 3,
    ) -> str:
        """
        Rank sentences using the rule-based scoring system and return
        the top sentences in their original order.
        """
        if not remarks or not remarks.strip():
            return ""

        if num_sentences <= 0:
            return ""

        sentences = nltk.sent_tokenize(remarks.strip())

        if len(sentences) <= num_sentences:
            return " ".join(sentences)

        scored_sentences = []

        for index, sentence in enumerate(sentences):
            score, breakdown = self.score_sentence(sentence)

            scored_sentences.append(
                {
                    "index": index,
                    "sentence": sentence,
                    "score": score,
                    "breakdown": breakdown,
                }
            )

        # Rank by score descending.
        # If scores tie, keep the earlier sentence ahead.
        ranked_sentences = sorted(
            scored_sentences,
            key=lambda item: (-item["score"], item["index"]),
        )

        top_sentences = ranked_sentences[:num_sentences]

        # Restore the original listing order for readability.
        top_sentences.sort(key=lambda item: item["index"])

        return " ".join(item["sentence"] for item in top_sentences)

    def rank_sentences(self, remarks: str) -> List[Dict]:

        if not remarks or not remarks.strip():
            return []

        sentences = nltk.sent_tokenize(remarks.strip())
        scored_sentences = []

        for index, sentence in enumerate(sentences):
            score, breakdown = self.score_sentence(sentence)

            scored_sentences.append(
                {
                    "index": index,
                    "sentence": sentence,
                    "score": score,
                    "breakdown": breakdown,
                }
            )

        return sorted(
            scored_sentences,
            key=lambda item: (-item["score"], item["index"]),
        )


    def _load_cities(self, path: Path) -> List[str]:
        cities = set()

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)

                for row in reader:
                    city = (row.get("L_City") or "").strip()
                    if city:
                        cities.add(city)

        except (FileNotFoundError, OSError):
            pass

        return sorted(cities, key=len, reverse=True)


if __name__ == "__main__":
    remarks = (
        "Gated Privacy with views of Lake Oroville.  This 18.49 parcel has 2 building areas.  Upper level house was burned.  Mobile home remains.  Separate Gate.  Lower parcel has another gate and an updated cottage.  PGE is available.  Well is in the detached shed.  Easily accessible with level parking and spacious front deck.  Perfect place to relax, create, and enjoy the seclusion and beautiful sunsets.  Nearby Highway 70 has Butte Cal Fire Station, Yankee Hill Hardware/post office, grocery, fuel and Toni's cafe with covered outdoor seating and views. Country living with Chico and Oroville just down the hill.  Feather River Canyon is one of the most beautiful locations in California."
    )

    summarizer = ListingSummarizer()

    summary = summarizer.extractive_summary(
        remarks=remarks,
        num_sentences=3,
    )

    print("SUMMARY:")
    print(summary)

    print("\nRANKING:")
    for result in summarizer.rank_sentences(remarks):
        print(
            f'Score={result["score"]} | '
            f'{result["breakdown"]} | '
            f'{result["sentence"]}'
        )
