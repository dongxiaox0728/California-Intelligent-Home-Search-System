import json
import re
from pathlib import Path
from typing import Any


class EntityExtractor:

    def __init__(self, taxonomy_path: str):
        self.taxonomy_terms = self.load_taxonomy(taxonomy_path)

    def load_taxonomy(self, taxonomy_path: str) -> list[dict]:
        path = Path(taxonomy_path)

        with path.open("r", encoding="utf-8") as file:
            taxonomy = json.load(file)

        return taxonomy["terms"]
    
    def extract_bedrooms(self, text: str) -> int | None:
        if not isinstance(text, str) or not text.strip():
            return None

        patterns = [
            r"\b(\d+)\s*(?:bedrooms?|beds?|br|bd|bdrm)\b",
            r"\b(\d+)[-\s]+bedroom\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return int(match.group(1))

        return None

    def extract_bathrooms(self, text: str) -> float | None:
        if not isinstance(text, str) or not text.strip():
            return None

        patterns = [
            r"\b(\d+(?:\.\d+)?)\s*(?:bathrooms?|baths?|ba|bth)\b",
            r"\b(\d+(?:\.\d+)?)[-\s]+bathroom\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return float(match.group(1))

        return None

    def extract_price(self, text: str) -> int | None:
        if not isinstance(text, str) or not text.strip():
            return None

        patterns = [
            r"\$\s*([\d,]+)",
            r"\b(?:listed|priced|offered|asking)\s+"
            r"(?:at|for)?\s*\$?\s*([\d,]+)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return int(match.group(1).replace(",", ""))

        return None

    def extract_sqft(self, text: str) -> int | None:
        if not isinstance(text, str) or not text.strip():
            return None

        patterns = [
            r"\b([\d,]+)\s*(?:sqft|sq\.?\s*ft\.?|square\s+feet|"
            r"square\s+foot|sf)\b",
            r"\b([\d,]+)[-\s]+square[-\s]+foot\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return int(match.group(1).replace(",", ""))

        return None

    def extract_amenities(self, text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        amenity_groups = {
            "garage": [
                "attached garage",
                "detached garage",
                "garage",
            ],
            "kitchen": [
                "updated kitchen",
            ],
            "basement": [
                "finished basement",
                "basement",
            ],
            "fireplace": [
                "fireplace",
            ],
            "pool": [
                "pool",
            ],
            "outdoor_space": [
                "fenced yard",
                "balcony",
                "patio",
                "deck",
            ],
        }

        found_categories = []

        for category, terms in amenity_groups.items():
            for term in terms:
                pattern = rf"\b{re.escape(term)}\b"

                if re.search(pattern, text, re.IGNORECASE):
                    found_categories.append(category)
                    break

        return found_categories

    def extract_all(self, text: str) -> dict[str, Any]:
        return {
            "bedrooms": self.extract_bedrooms(text),
            "bathrooms": self.extract_bathrooms(text),
            "price": self.extract_price(text),
            "sqft": self.extract_sqft(text),
            "amenities": self.extract_amenities(text),
        }


if __name__ == "__main__":
    extractor = EntityExtractor("data/taxonomy_week3.json")

    text = (
        "beautiful 3 bedroom 2.5 bath home with 1850 sqft "
        "attached garage updated kitchen and finished basement "
        "listed at 425000"
    )

    print(extractor.extract_all(text))