import json
import re
from pathlib import Path

import pandas as pd


INPUT_PATH = "data/processed/top_bigrams.csv"
OUTPUT_PATH = "data/processed/taxonomy.json"
TERM_COL = "bigram"
CITY_SOURCE_PATH = "data/processed/listing_sample.csv"
POSSIBLE_CITY_COLUMNS = ["city", "L_City", "City", "CITY"]



# Fallback city/location names. The script will ALSO try to learn city names
# directly from listing_sample.csv, so you do not have to manually maintain
# every city that appears in the data.
KNOWN_LOCATION_PHRASES = {
    "los angeles", "san francisco", "san diego", "san jose",
    "sacramento", "long beach", "oakland", "fresno", "anaheim",
    "irvine", "pasadena", "santa ana", "santa monica", "beverly hills",
    "newport beach", "huntington beach", "riverside", "glendale",
    "burbank", "torrance", "malibu", "ventura", "ontario",
    "palm springs", "santa barbara"
}


def load_city_names() -> set[str]:
    """
    Load city names from the listing sample when possible.

    This is better than relying only on hard-coded location keywords because
    taxonomy bigrams can be literal place names such as "los angeles".
    """
    city_names = {normalize_term(name) for name in KNOWN_LOCATION_PHRASES}

    path = Path(CITY_SOURCE_PATH)
    if not path.exists():
        return city_names

    try:
        city_df = pd.read_csv(path)
    except Exception:
        return city_names

    city_col = next(
        (col for col in POSSIBLE_CITY_COLUMNS if col in city_df.columns),
        None
    )

    if city_col is None:
        return city_names

    for value in city_df[city_col].dropna().astype(str):
        city = normalize_term(value)
        if city and city != "nan":
            city_names.add(city)

    return city_names


# Eight categories chosen to be useful in later weeks:
# - Week 3: amenity / feature detection
# - Week 4: query parsing and filtering
# - Week 6: listing signal extraction
CATEGORY_KEYWORDS = {
    "property_type": {
        "phrases": {
            "single family", "single-family", "multi family", "multi-family",
            "town house", "townhome", "town home", "condo unit",
            "condominium unit", "duplex unit", "triplex unit",
            "mobile home", "manufactured home"
        },
        "tokens": {
            "condo", "condominium", "townhouse", "townhome", "duplex",
            "triplex", "fourplex", "bungalow", "ranch", "colonial",
            "apartment", "villa", "cottage", "loft", "residence",
            "manufactured", "mobile"
        },
    },

    "interior_features": {
        "phrases": {
            "hardwood floors", "hardwood flooring", "stainless steel",
            "granite countertops", "granite counters", "updated kitchen",
            "walk in", "walk-in closet", "walk in closet",
            "double vanity", "vaulted ceilings", "central air"
        },
        "tokens": {
            "kitchen", "floor", "floors", "flooring", "hardwood", "carpet",
            "tile", "closet", "closets", "appliance", "appliances",
            "stainless", "granite", "counter", "counters", "countertop",
            "countertops", "cabinet", "cabinets", "ceiling", "ceilings",
            "vanity", "shower", "tub", "laundry", "pantry"
        },
    },

    "exterior_features": {
        "phrases": {
            "fenced yard", "fenced backyard", "large yard", "corner lot",
            "private yard", "roof deck", "covered patio"
        },
        "tokens": {
            "yard", "backyard", "frontyard", "patio", "deck", "porch",
            "roof", "driveway", "fence", "fenced", "landscaping",
            "landscape", "lot", "balcony", "terrace", "garden",
            "siding", "exterior"
        },
    },

    "amenities": {
        "phrases": {
            "swimming pool", "community pool", "private pool",
            "attached garage", "detached garage", "two car",
            "three car", "fitness center", "club house",
            "gated community", "tennis court", "basketball court"
        },
        "tokens": {
            "pool", "garage", "fireplace", "gym", "clubhouse", "spa",
            "sauna", "elevator", "tennis", "golf", "playground",
            "security", "doorman", "concierge", "storage"
        },
    },

    "property_condition": {
        "phrases": {
            "move ready", "move in", "move-in ready", "new construction",
            "recently updated", "fully renovated", "newly renovated",
            "needs work", "fixer upper", "turn key", "turnkey home"
        },
        "tokens": {
            "updated", "renovated", "remodeled", "remodel", "modern",
            "new", "fresh", "maintained", "improved", "improvements",
            "turnkey", "fixer", "rehab", "restored", "upgraded",
            "upgrade", "original", "condition"
        },
    },

    "layout_space": {
        "phrases": {
            "open concept", "open floor", "floor plan", "living room",
            "dining room", "family room", "primary suite",
            "master suite", "master bedroom", "primary bedroom",
            "finished basement", "full basement", "bonus room"
        },
        "tokens": {
            "bedroom", "bedrooms", "bathroom", "bathrooms", "bath",
            "baths", "basement", "suite", "living", "dining", "family",
            "room", "rooms", "space", "level", "levels", "story",
            "stories", "loft", "den", "office", "foyer", "attic",
            "study"
        },
    },

    "location_features": {
        "phrases": {
            "near downtown", "close downtown", "near schools",
            "close schools", "walking distance", "public transportation",
            "water front", "waterfront property", "cul de",
            "cul-de-sac", "near shopping", "los angeles", "san francisco", "san diego",
            "san jose", "long beach", "santa monica", "beverly hills",
            "newport beach", "huntington beach", "palm springs"
        },
        "tokens": {
            "school", "schools", "downtown", "shopping", "park", "parks",
            "neighborhood", "transportation", "transit", "train",
            "highway", "freeway", "waterfront", "lakefront", "beach",
            "beachfront", "river", "lake", "city", "village",
            "community", "district", "corner"
        },
    },

    "financing_terms": {
        "phrases": {
            "seller financing", "owner financing", "cash only",
            "fha approved", "va approved", "assumable loan",
            "investment property", "rental income", "hoa fee",
            "hoa fees", "property tax", "property taxes"
        },
        "tokens": {
            "price", "priced", "affordable", "investment", "investor",
            "rental", "rent", "income", "hoa", "tax", "taxes",
            "value", "financing", "finance", "mortgage", "loan",
            "fha", "va", "cash", "lease", "leasing", "assumable",
            "foreclosure", "shortsale"
        },
    },
}


# Some words can plausibly belong to more than one category.
# This priority is used only when categories receive the same score.
CATEGORY_PRIORITY = [
    "property_type",
    "amenities",
    "property_condition",
    "location_features",
    "financing_terms",
    "layout_space",
    "interior_features",
    "exterior_features",
]


def normalize_term(term: str) -> str:
    """Normalize a taxonomy term for matching."""
    term = str(term).lower().strip()
    term = term.replace("-", " ")
    term = re.sub(r"\s+", " ", term)
    return term


def assign_category(term: str, city_names: set[str]) -> str:
    """
    Assign a bigram to the best matching category.

    Method:
    1. Normalize the term.
    2. Give strong weight to explicit phrase matches.
    3. Give one point for each keyword token that appears.
    4. Choose the category with the highest score.
    5. If nothing matches, return 'uncategorized'.
    """
    normalized = normalize_term(term)
    term_tokens = set(normalized.split())

    # Literal city names are location features even if they contain no
    # generic words like "city", "downtown", or "neighborhood".
    if normalized in city_names:
        return "location_features"

    scores = {}

    for category, rules in CATEGORY_KEYWORDS.items():
        score = 0

        # Exact / contained phrase rules are stronger than individual tokens.
        for phrase in rules["phrases"]:
            normalized_phrase = normalize_term(phrase)
            if normalized_phrase == normalized:
                score += 5
            elif normalized_phrase in normalized:
                score += 3

        # Token matches.
        for keyword in rules["tokens"]:
            if keyword in term_tokens:
                score += 1

        scores[category] = score

    best_score = max(scores.values())

    if best_score == 0:
        return "uncategorized"

    tied_categories = [
        category
        for category, score in scores.items()
        if score == best_score
    ]

    for category in CATEGORY_PRIORITY:
        if category in tied_categories:
            return category

    return tied_categories[0]


def main():
    df = pd.read_csv(INPUT_PATH)

    if TERM_COL not in df.columns:
        raise ValueError(
            f"Expected a '{TERM_COL}' column in {INPUT_PATH}. "
            f"Found: {list(df.columns)}"
        )

    city_names = load_city_names()

    terms = []

    # Process every row in top_bigrams.csv.
    # If taxonomy_builder produced 200 bigrams, this creates up to 200 terms.
    for _, row in df.iterrows():
        term = str(row[TERM_COL]).strip()

        if not term or term.lower() == "nan":
            continue

        category = assign_category(term, city_names)

        terms.append({
            "id": f"term_{len(terms) + 1:03d}",
            "term": term,
            "category": category,
        })

    category_counts = {
        category: sum(1 for item in terms if item["category"] == category)
        for category in CATEGORY_KEYWORDS
    }

    uncategorized_count = sum(
        1 for item in terms if item["category"] == "uncategorized"
    )

    taxonomy = {
        "metadata": {
            "project": "real_estate_nlp",
            "description": (
                "Real-estate terminology taxonomy generated from the top "
                "listing-remark bigrams and categorized for downstream NLP tasks."
            ),
            "num_terms": len(terms),
            "num_categories": 8,
            "uncategorized_count": uncategorized_count,
            "category_counts": category_counts,
        },
        "categories": list(CATEGORY_KEYWORDS.keys()),
        "terms": terms,
    }

    Path("data/processed").mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(taxonomy, file, indent=2)

    print(f"Saved {len(terms)} terms to {OUTPUT_PATH}")
    print(f"Loaded {len(city_names)} known/data-derived city names for location matching.")
    print()
    print("Category counts:")
    for category, count in category_counts.items():
        print(f"  {category}: {count}")

    print(f"  uncategorized: {uncategorized_count}")


if __name__ == "__main__":
    main()
