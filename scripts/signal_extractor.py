from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.entity_extractor import EntityExtractor


class SignalExtractor:
    """
    Week 6 SignalExtractor following the handbook structure exactly.

    Output:
    {
        "listing_id": ...,
        "entities": ...,
        "amenities": ...,
        "condition_keywords": ...,
        "financing_terms": ...,
        "location_features": ...
    }

    Week 3 EntityExtractor is reused for structured entities.
    Week 1 taxonomy is used specifically for amenity matching.
    """

    def __init__(
        self,
        taxonomy_path: str | Path = "taxonomy/taxonomy_week1.json",
        entity_extractor: EntityExtractor | None = None,
    ) -> None:
        self.taxonomy_path = Path(taxonomy_path)
        self.taxonomy = self._load_taxonomy(self.taxonomy_path)

        self.extractor = (
            entity_extractor
            if entity_extractor is not None
            else EntityExtractor(str(self.taxonomy_path))
        )

        # Only the Week 1 "amenities" category is used directly here.
        self.amenity_terms = self._load_amenity_terms()

    def _load_taxonomy(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("taxonomy JSON must contain an object")

        return data

    def _load_amenity_terms(self) -> list[str]:
        """Get only terms categorized as amenities in the Week 1 taxonomy."""
        amenities: list[str] = []

        for item in self.taxonomy.get("terms", []):
            if item.get("category") != "amenities":
                continue

            term = str(item.get("term", "")).strip()
            if term and term not in amenities:
                amenities.append(term)

        return amenities

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        pattern = rf"\b{re.escape(phrase)}\b"
        return re.search(pattern, text, re.IGNORECASE) is not None

    def _match_amenities(self, remarks: str) -> list[str]:
        """
        Match amenity terms from the Week 1 taxonomy.
        """
        if not isinstance(remarks, str) or not remarks.strip():
            return []

        found: list[str] = []

        for term in self.amenity_terms:
            if self._contains_phrase(remarks, term):
                found.append(term)

        return found

    def _extract_condition(self, remarks: str) -> list[str]:
        """
        Detect property-condition signals.

        These are Week 6 signal rules, rather than returning the entire
        Week 1 property_condition taxonomy category.
        """
        condition_patterns = {
            "updated": [
                r"\bupdated\b",
                r"\brecently updated\b",
                r"\bnewly updated\b",
            ],
            "renovated": [
                r"\brenovated\b",
                r"\bfully renovated\b",
                r"\brecently renovated\b",
                r"\bnewly renovated\b",
            ],
            "remodeled": [
                r"\bremodeled\b",
                r"\bremodelled\b",
            ],
            "new construction": [
                r"\bnew construction\b",
                r"\bbrand new\b",
            ],
            "move-in ready": [
                r"\bmove[- ]in ready\b",
                r"\bmove in ready\b",
            ],
            "fixer upper": [
                r"\bfixer[- ]upper\b",
                r"\bneeds work\b",
            ],
        }

        found: list[str] = []

        for label, patterns in condition_patterns.items():
            if any(re.search(pattern, remarks, re.IGNORECASE) for pattern in patterns):
                found.append(label)

        return found

    def _extract_financing(self, remarks: str) -> list[str]:
        """
        Detect financing-related listing signals.
        """
        financing_patterns = {
            "seller financing": [
                r"\bseller financing\b",
                r"\bseller finance\b",
            ],
            "owner financing": [
                r"\bowner financing\b",
                r"\bowner finance\b",
            ],
            "cash only": [
                r"\bcash only\b",
            ],
            "FHA": [
                r"\bfha\b",
                r"\bfha approved\b",
            ],
            "VA": [
                r"\bva\b",
                r"\bva approved\b",
            ],
            "assumable loan": [
                r"\bassumable (?:loan|mortgage)\b",
            ],
        }

        found: list[str] = []

        for label, patterns in financing_patterns.items():
            if any(re.search(pattern, remarks, re.IGNORECASE) for pattern in patterns):
                found.append(label)

        return found

    def _extract_location(self, remarks: str) -> list[str]:
        """
        Detect descriptive location features from remarks.

        This is for features such as proximity to parks, schools, downtown,
        transit, waterfront, etc. The listing's structured city field is not
        copied into this list because the handbook calls this
        'location_features'.
        """
        location_patterns = {
            "near downtown": [
                r"\bnear downtown\b",
                r"\bclose to downtown\b",
                r"\bminutes from downtown\b",
            ],
            "near schools": [
                r"\bnear schools?\b",
                r"\bclose to schools?\b",
            ],
            "near parks": [
                r"\bnear parks?\b",
                r"\bclose to parks?\b",
            ],
            "near shopping": [
                r"\bnear shopping\b",
                r"\bclose to shopping\b",
            ],
            "public transportation": [
                r"\bpublic transportation\b",
                r"\bpublic transit\b",
                r"\bnear transit\b",
                r"\bnear train\b",
            ],
            "walking distance": [
                r"\bwalking distance\b",
                r"\bwalkable\b",
            ],
            "waterfront": [
                r"\bwaterfront\b",
                r"\blakefront\b",
                r"\bbeachfront\b",
            ],
            "cul-de-sac": [
                r"\bcul[- ]de[- ]sac\b",
            ],
            "easy highway access": [
                r"\beasy access to (?:the )?(?:highway|freeway)\b",
                r"\bnear (?:the )?(?:highway|freeway)\b",
            ],
        }

        found: list[str] = []

        for label, patterns in location_patterns.items():
            if any(re.search(pattern, remarks, re.IGNORECASE) for pattern in patterns):
                found.append(label)

        return found

    def extract_signals(self, listing_record: dict[str, Any]) -> dict[str, Any]:
        """
        Extract Week 6 signals from one listing record.
        """
        if not isinstance(listing_record, dict):
            raise TypeError("listing_record must be a dictionary")

        remarks = listing_record.get("L_Remarks", "") or ""
        remarks = str(remarks)

        # Get the Week 3 extraction result.
        week3_entities = self.extractor.extract_all(remarks)

        # Week 6 schema keeps only the structured numeric entities here.
        # Amenities are returned separately at the top level.
        entities = {
            "bedrooms": week3_entities.get("bedrooms"),
            "bathrooms": week3_entities.get("bathrooms"),
            "price": week3_entities.get("price"),
            "sqft": week3_entities.get("sqft"),
        }

        # Get amenities from the Week 1 taxonomy.
        amenities = self._match_amenities(remarks)

        # Return the Week 6 JSON-schema-compatible structure directly.
        return {
            "listing_id": listing_record.get("L_ListingID"),
            "entities": entities,
            "amenities": amenities,
            "condition_keywords": self._extract_condition(remarks),
            "financing_terms": self._extract_financing(remarks),
            "location_features": self._extract_location(remarks),
        }


if __name__ == "__main__":
    signal_extractor = SignalExtractor(
        taxonomy_path="taxonomy/taxonomy_week1.json"
    )

    sample_listing = {
        "L_ListingID": "TEST_001",
        "L_Remarks": (
            "Updated 3 bedroom 2 bath home with a swimming pool, "
            "seller financing available, and close to downtown."
        ),
    }

    result = signal_extractor.extract_signals(sample_listing)
    print(json.dumps(result, indent=2))
