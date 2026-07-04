import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.text_cleaning import TextCleaner


@pytest.fixture
def cleaner():
    return TextCleaner()


TEXT_CLEANING_CASES = [
    ("priced at 450k", ["450000"]),
    ("priced at 450K", ["450000"]),
    ("listed for $450k", ["450000"]),
    ("home under 500 k", ["500000"]),
    ("luxury home for 1.2m", ["1200000"]),
    ("luxury home for $1.2m", ["1200000"]),
    ("asking 2M", ["2000000"]),
    ("price reduced to 750000", ["750000"]),

    ("3br home", ["3 bedroom"]),
    ("4bd house", ["4 bedroom"]),
    ("2bdrm condo", ["2 bedroom"]),
    ("5bedrm property", ["5 bedroom"]),
    ("2ba unit", ["2 bathroom"]),
    ("3bth home", ["3 bathroom"]),
    ("3br/2ba home", ["3 bedroom", "2 bathroom"]),
    ("4 BR / 3 BA property", ["4 bedroom", "3 bathroom"]),

    ("2000 sqft home", ["2000 square feet"]),
    ("2000 sq ft home", ["2000 square feet"]),
    ("2,000 sqft home", ["2000 square feet"]),
    ("1,250 sq. ft. condo", ["1250 square feet"]),
    ("850 sf studio", ["850 square feet"]),

    ("home w/ garage", ["with garage"]),
    ("home w/o garage", ["without garage"]),
    ("fin bsmt included", ["finished basement"]),
    ("large bsmt", ["basement"]),
    ("2 car gar", ["garage"]),
    ("att gar included", ["attached garage"]),
    ("det gar in back", ["detached garage"]),

    ("updated kit", ["kitchen"]),
    ("large lr", ["living room"]),
    ("formal dr", ["dining room"]),
    ("cozy fr", ["family room"]),
    ("extra rm", ["room"]),
    ("main lvl", ["level"]),
    ("second flr", ["floor"]),

    ("hw floors", ["hardwood"]),
    ("hdwd floors", ["hardwood"]),
    ("new appl", ["appliance"]),
    ("new appls", ["appliances"]),
    ("monthly hoa fee", ["homeowners association"]),
    ("wood burning fp", ["fireplace"]),
    ("beautiful fplc", ["fireplace"]),
    ("central ac", ["air conditioning"]),
    ("central a/c", ["air conditioning"]),

    ("private pkg", ["parking"]),
    ("easy prkg", ["parking"]),
    ("washer incl", ["included"]),
    ("fridge excl", ["excluded"]),
    ("built last yr", ["year"]),
    ("updated 2 yrs ago", ["years"]),
    ("approx 2000 sqft", ["approximately", "2000 square feet"]),
    ("fully renov home", ["renovated"]),
    ("recent rehab property", ["rehabilitated"]),
    ("modern condo", ["condominium"]),
    ("beautiful sfh", ["single family home"]),

    ("beautiful home <br> move in ready", ["beautiful home", "move in ready"]),
    ("<p>updated kitchen</p>", ["updated kitchen"]),
    ("great&nbsp;home", ["great home"]),
    ("Beautiful    home     with   garage", ["beautiful home with garage"]),
    ("BEAUTIFUL HOME", ["beautiful home"]),
    (None, [""]),
    ("", [""]),
]


@pytest.mark.parametrize("raw_text, expected_parts", TEXT_CLEANING_CASES)
def test_text_cleaning_cases(cleaner, raw_text, expected_parts):
    cleaned = cleaner.clean_text(raw_text)

    for expected in expected_parts:
        assert expected in cleaned


def test_abbreviation_dictionary_has_30_plus_mappings(cleaner):
    assert len(cleaner.abbrev_map) >= 30


def test_clean_text_returns_string(cleaner):
    cleaned = cleaner.clean_text("3br home")
    assert isinstance(cleaned, str)


def test_clean_text_strips_outer_whitespace(cleaner):
    cleaned = cleaner.clean_text("   3br home   ")
    assert cleaned == cleaned.strip()


def test_clean_text_combined_example(cleaner):
    raw = "Beautiful 3br/2ba home w/ 2,000 sqft priced at 450k <br>"
    cleaned = cleaner.clean_text(raw)

    assert "3 bedroom" in cleaned
    assert "2 bathroom" in cleaned
    assert "with" in cleaned
    assert "2000 square feet" in cleaned
    assert "450000" in cleaned
    assert "<br>" not in cleaned