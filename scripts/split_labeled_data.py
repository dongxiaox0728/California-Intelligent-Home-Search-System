from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


INPUT_PATH = Path("data/processed/week3_labeled_sample.csv")
DEVELOPMENT_PATH = Path("data/processed/week3_development.csv")
TEST_PATH = Path("data/processed/week3_test.csv")


def main():
    df = pd.read_csv(INPUT_PATH)

    development, test = train_test_split(
        df,
        test_size=0.20,
        random_state=42,
    )

    development.to_csv(DEVELOPMENT_PATH, index=False)
    test.to_csv(TEST_PATH, index=False)

    print(f"Development rows: {len(development)}")
    print(f"Test rows: {len(test)}")


if __name__ == "__main__":
    main()