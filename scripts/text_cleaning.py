import re
import html
import unicodedata
from pathlib import Path

import pandas as pd


class TextCleaner:
    def __init__(self):
        self.abbrev_map = {
            "br": "bedroom",
            "bd": "bedroom",
            "bdrm": "bedroom",
            "bedrm": "bedroom",
            "ba": "bathroom",
            "bth": "bathroom",
            "bath": "bathroom",
            "sqft": "square feet",
            "sq ft": "square feet",
            "sq. ft.": "square feet",
            "sf": "square feet",
            "w/": "with",
            "w/o": "without",
            "mbr": "master bedroom",
            "mbdrm": "master bedroom",
            "bsmt": "basement",
            "fin bsmt": "finished basement",
            "gar": "garage",
            "att gar": "attached garage",
            "det gar": "detached garage",
            "kit": "kitchen",
            "lr": "living room",
            "dr": "dining room",
            "fr": "family room",
            "rm": "room",
            "lvl": "level",
            "flr": "floor",
            "hw": "hardwood",
            "hdwd": "hardwood",
            "appl": "appliance",
            "appls": "appliances",
            "hoa": "homeowners association",
            "fp": "fireplace",
            "fplc": "fireplace",
            "ac": "air conditioning",
            "a/c": "air conditioning",
            "pkg": "parking",
            "prkg": "parking",
            "incl": "included",
            "excl": "excluded",
            "yr": "year",
            "yrs": "years",
            "approx": "approximately",
            "renov": "renovated",
            "rehab": "rehabilitated",
            "condo": "condominium",
            "sfh": "single family home",
        }

    def clean_text(self, text):
        text = self.handle_missing(text)
        text = self.normalize_unicode(text)
        text = self.remove_html(text)
        text = self.lowercase_text(text)
        text = self.normalize_prices(text)
        text = self.normalize_measurements(text)
        text = self.expand_bed_bath_counts(text)
        text = self.expand_abbreviations(text)
        text = self.normalize_punctuation(text)
        text = self.normalize_whitespace(text)
        return text.strip()

    def handle_missing(self, text):
        if pd.isna(text):
            return ""
        return str(text)

    def normalize_unicode(self, text):
        text = html.unescape(text)
        text = unicodedata.normalize("NFKC", text)
        return text

    def remove_html(self, text):
        return re.sub(r"<[^>]+>", " ", text)

    def lowercase_text(self, text):
        return text.lower()

    def normalize_prices(self, text):
        text = re.sub(
            r"\$?\b(\d+(?:\.\d+)?)\s*k\b",
            lambda m: str(int(float(m.group(1)) * 1000)),
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\$?\b(\d+(?:\.\d+)?)\s*m\b",
            lambda m: str(int(float(m.group(1)) * 1_000_000)),
            text,
            flags=re.IGNORECASE,
        )

        return text

    def normalize_measurements(self, text):
        text = re.sub(
            r"\b(\d{1,3}(?:,\d{3})+)\b",
            lambda m: m.group(1).replace(",", ""),
            text,
        )

        text = re.sub(
            r"\b(sq\.?\s*ft\.?|sqft|sf)\b",
            "square feet",
            text,
            flags=re.IGNORECASE,
        )

        return text

    def expand_bed_bath_counts(self, text):
        text = re.sub(
            r"\b(\d+)\s*(br|bd|bdrm|bedrm)\b",
            r"\1 bedroom",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\b(\d+)\s*(ba|bth)\b",
            r"\1 bathroom",
            text,
            flags=re.IGNORECASE,
        )

        return text

    def expand_abbreviations(self, text):
        sorted_abbrevs = sorted(
            self.abbrev_map.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for abbr, full in sorted_abbrevs:
            escaped_abbr = re.escape(abbr)

            if "/" in abbr:
                pattern = escaped_abbr
            else:
                pattern = rf"\b{escaped_abbr}\b"

            text = re.sub(pattern, full, text, flags=re.IGNORECASE)

        return text

    def normalize_punctuation(self, text):
        text = re.sub(r"\s*/\s*", " ", text)
        text = re.sub(r"[!]{2,}", "!", text)
        text = re.sub(r"[.]{2,}", ".", text)
        text = re.sub(r"[^a-zA-Z0-9\s.,!?$-]", " ", text)

        return text

    def normalize_whitespace(self, text):
        return re.sub(r"\s+", " ", text)


def clean_dataset(
    input_path="data/processed/listing_sample.csv",
    output_path="data/processed/listing_sample_cleaned.csv",
    text_column="remarks",
):
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)

    cleaner = TextCleaner()

    cleaned_column = f"cleaned_{text_column}"
    df[cleaned_column] = df[text_column].apply(cleaner.clean_text)

    df.to_csv(output_path, index=False)

    print(f"Cleaned dataset saved to: {output_path}")
    print(f"New column created: {cleaned_column}")


def main():
    clean_dataset()


if __name__ == "__main__":
    main()