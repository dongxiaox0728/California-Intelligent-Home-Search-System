import pandas as pd
import json
from pathlib import Path

input_path = "data/processed/top_bigrams.csv"
output_path = "data/processed/taxonomy.json"

df = pd.read_csv(input_path)

print(df.head())
print(df.columns)


term_col = "bigram"

category_keywords = {
    "interior_features": [
        "kitchen", "floor", "floors", "hardwood", "carpet", "bath", "bathroom",
        "bedroom", "closet", "fireplace", "appliances", "stainless", "granite",
        "counter", "cabinet", "suite"
    ],
    "exterior_features": [
        "garage", "yard", "patio", "deck", "porch", "roof", "driveway",
        "fence", "pool", "landscaping", "lot", "backyard"
    ],
    "location_neighborhood": [
        "school", "schools", "downtown", "shopping", "park", "parks",
        "near", "close", "neighborhood", "transportation", "train", "highway"
    ],
    "property_condition": [
        "updated", "renovated", "new", "fresh", "remodeled", "modern",
        "move", "ready", "maintained", "improvements"
    ],
    "layout_space": [
        "open", "concept", "floor plan", "basement", "room", "space",
        "living", "dining", "family", "level", "story"
    ],
    "financial_terms": [
        "price", "affordable", "investment", "rental", "income",
        "hoa", "tax", "taxes", "value"
    ],
    "utilities_systems": [
        "hvac", "heating", "cooling", "air", "water", "sewer",
        "electric", "mechanical", "furnace"
    ],
    "general_marketing": [
        "beautiful", "charming", "spacious", "must", "rare",
        "opportunity", "welcome", "perfect", "amazing"
    ]
}

def assign_category(term):
    term_lower = str(term).lower()

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in term_lower:
                return category

    return "uncategorized"

terms = []

for i, row in df.head(250).iterrows():
    term = str(row[term_col]).strip()

    if not term or term.lower() == "nan":
        continue

    terms.append({
        "id": f"term_{len(terms) + 1:03d}",
        "term": term,
        "category": assign_category(term)
    })

taxonomy = {
    "metadata": {
        "project": "real_estate_nlp",
        "description": "Real estate terminology taxonomy generated from listing remark bigrams",
        "num_terms": len(terms),
        "num_categories": 8
    },
    "categories": list(category_keywords.keys()),
    "terms": terms
}

Path("data/processed").mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(taxonomy, f, indent=2)

print(f"Saved {len(terms)} terms to {output_path}")