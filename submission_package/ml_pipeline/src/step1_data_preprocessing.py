"""Step 1: Data loading and preprocessing for phishing URL detection.

Usage:
    python src/step1_data_preprocessing.py \
    --phishing data/PhiUSIIL_Phishing_URL_Dataset.csv \
    --legitimate data/new_data_urls.csv \
        --output data/processed_urls.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, cast

import pandas as pd

URL_COLUMN_CANDIDATES = ["url", "URL", "link", "Link"]
PHISHING_LABEL = 1
LEGITIMATE_LABEL = 0


def find_url_column(df: pd.DataFrame) -> str:
    """Return the first matching URL column name, else raise an error."""
    for col in URL_COLUMN_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not find URL column. Expected one of: "
        f"{', '.join(URL_COLUMN_CANDIDATES)}"
    )


def load_dataset(csv_path: Path, label: int) -> pd.DataFrame:
    """Load one dataset and normalize it to ['url', 'is_phishing']."""
    df = pd.read_csv(csv_path)
    url_col = find_url_column(df)

    normalized = pd.DataFrame()
    normalized["url"] = df[url_col].astype(str).str.strip()
    normalized["is_phishing"] = label
    return normalized


def filter_valid_http_urls(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows where URL starts with http:// or https://."""
    pattern = r"^https?://"
    mask = df["url"].str.match(pattern, na=False)
    return cast(pd.DataFrame, df.loc[mask].copy())


def combine_and_preprocess(
    phishing_paths: Iterable[Path], legitimate_path: Path
) -> pd.DataFrame:
    """Load, merge, clean and return a preprocessed dataframe."""
    frames: list[pd.DataFrame] = []

    for path in phishing_paths:
        frames.append(load_dataset(path, label=PHISHING_LABEL))

    frames.append(load_dataset(legitimate_path, label=LEGITIMATE_LABEL))

    combined = pd.concat(frames, ignore_index=True)

    combined = combined.dropna(subset=["url", "is_phishing"])
    combined = combined.drop_duplicates(subset=["url"])
    combined = filter_valid_http_urls(combined)

    combined = combined.reset_index(drop=True)
    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 1 preprocessing for phishing URL detection datasets"
    )
    parser.add_argument(
        "--phishing",
        type=Path,
        nargs="+",
        required=True,
        help="One or more phishing dataset CSV paths",
    )
    parser.add_argument("--legitimate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    processed = combine_and_preprocess(
        phishing_paths=args.phishing,
        legitimate_path=args.legitimate,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    processed.to_csv(args.output, index=False)

    print(f"Saved {len(processed)} rows to {args.output}")
    print(processed["is_phishing"].value_counts().rename("count").sort_index())


if __name__ == "__main__":
    main()
