import pandas as pd
import re
from collections import Counter
from pathlib import Path
import json


MLS_ABBREVIATIONS = [
    "br", "bd", "bdrm", "bedrm",
    "ba", "bth", "bath",
    "sqft", "sq ft", "sq. ft.", "sf",
    "w/", "w/o",
    "mbr", "mbdrm",
    "bsmt", "fin bsmt",
    "gar", "att gar", "det gar",
    "kit", "lr", "dr", "fr",
    "rm", "lvl", "flr",
    "hw", "hdwd",
    "appl", "appls",
    "hoa",
    "fp", "fplc",
    "ac", "a/c",
    "pkg", "prkg",
    "incl", "excl",
    "yr", "yrs",
    "approx",
    "renov", "rehab",
    "condo", "sfh",
]


def find_common_tokens(text_series, top_n=50):
    all_text = " ".join(text_series.fillna("").astype(str).str.lower())
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z/\.]*\b", all_text)
    return Counter(tokens).most_common(top_n)


def detect_mls_abbreviations(text_series):
    all_text = " ".join(text_series.fillna("").astype(str).str.lower())

    abbreviation_counts = {}

    for abbr in MLS_ABBREVIATIONS:
        escaped_abbr = re.escape(abbr)

        # Special handling for abbreviations with symbols like w/, w/o, a/c
        if "/" in abbr:
            pattern = escaped_abbr
        else:
            pattern = rf"\b{escaped_abbr}\b"

        count = len(re.findall(pattern, all_text, flags=re.IGNORECASE))

        if count > 0:
            abbreviation_counts[abbr] = count

    return dict(sorted(abbreviation_counts.items(), key=lambda x: x[1], reverse=True))


def profile_column(df, column_name):
    text_series = df[column_name].fillna("").astype(str)

    profile = {
        "row_count": len(df),

        "null_count": int(df[column_name].isnull().sum()),
        "null_rate": float(df[column_name].isnull().mean()),

        "avg_length": float(text_series.str.len().mean()),

        "html_count": int(
            text_series.str.contains(r"<[^>]+>", regex=True).sum()
        ),

        "price_k_or_m_count": int(
            text_series.str.contains(
                r"\$?\d+(?:\.\d+)?\s*[kKmM]\b",
                regex=True
            ).sum()
        ),

        "sqft_count": int(
            text_series.str.contains(
                r"\b(sqft|sq ft|sq\. ft\.|sf)\b",
                case=False,
                regex=True
            ).sum()
        ),

        "slash_abbreviation_count": int(
            text_series.str.contains(
                r"\bw/|\bw/o",
                case=False,
                regex=True
            ).sum()
        ),

        "bed_bath_abbreviation_count": int(
            text_series.str.contains(
                r"\b\d+\s*(br|bd|bdrm|bedrm|ba|bth|bath)\b",
                case=False,
                regex=True
            ).sum()
        ),

        "detected_mls_abbreviations": detect_mls_abbreviations(text_series),

        "common_tokens": find_common_tokens(text_series, top_n=50),
    }

    return profile


def main():
    input_path = Path("data/processed/listing_sample.csv")
    output_path = Path("data/processed/text_profile_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)

    profile = profile_column(df, "remarks")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=4)

    print(profile)


if __name__ == "__main__":
    main()