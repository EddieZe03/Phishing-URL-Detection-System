"""Step 1b: Integrate malicious_phish.csv with existing datasets and retrain.

This script combines the large malicious_phish.csv dataset with your existing
phishing and legitimate URLs to create a more diverse training dataset.

Usage:
    python src/step1_integrate_malicious_phish.py \
        --input malicious_phish.csv \
        --dataset-phishing dataset_phishing.csv \
        --phishing-dataset data/PhiUSIIL_Phishing_URL_Dataset.csv \
        --legitimate-dataset data/new_data_urls.csv \
        --output data/processed_urls_with_malicious.csv
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


def load_malicious_phish(csv_path: Path) -> pd.DataFrame:
    """Load malicious_phish.csv and convert type column to binary labels.

    Phishing URLs -> label 1
    Benign URLs -> label 0
    Defacement URLs are treated as non-phishing for binary classification.
    """
    df = pd.read_csv(csv_path)
    url_col = find_url_column(df)

    normalized = pd.DataFrame()
    normalized["url"] = df[url_col].astype(str).str.strip()

    # Map type to binary label: phishing->1, others->0
    type_col = df["type"].astype(str).str.lower().str.strip()
    normalized["is_phishing"] = (type_col == "phishing").astype(int)

    return normalized


def load_dataset_phishing_status(csv_path: Path) -> pd.DataFrame:
    """Load dataset_phishing.csv and map status to binary labels."""
    df = pd.read_csv(csv_path)
    url_col = find_url_column(df)

    normalized = pd.DataFrame()
    normalized["url"] = df[url_col].astype(str).str.strip()

    status_col = df["status"].astype(str).str.lower().str.strip()
    normalized["is_phishing"] = (status_col == "phishing").astype(int)

    return normalized


def filter_valid_http_urls(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows where URL starts with http:// or https://."""
    pattern = r"^https?://"
    mask = df["url"].str.match(pattern, na=False)
    return cast(pd.DataFrame, df.loc[mask].copy())


def combine_and_preprocess(
    phishing_paths: Iterable[Path],
    legitimate_path: Path,
    malicious_phish_path: Path | None,
    dataset_phishing_path: Path | None,
) -> pd.DataFrame:
    """Load, merge, clean and return a preprocessed dataframe."""
    frames: list[pd.DataFrame] = []

    # Load original phishing datasets
    for path in phishing_paths:
        df = load_dataset(path, label=PHISHING_LABEL)
        frames.append(df)
        print(f"Loaded {len(df)} phishing URLs from {path.name}")

    # Load original legitimate dataset
    df_legit = load_dataset(legitimate_path, label=LEGITIMATE_LABEL)
    frames.append(df_legit)
    print(f"Loaded {len(df_legit)} legitimate URLs from {legitimate_path.name}")

    # Load malicious_phish.csv if provided
    if malicious_phish_path and malicious_phish_path.exists():
        df_malicious = load_malicious_phish(malicious_phish_path)
        phishing_count = (df_malicious["is_phishing"] == 1).sum()
        benign_count = (df_malicious["is_phishing"] == 0).sum()
        print(
            f"Loaded {len(df_malicious)} URLs from {malicious_phish_path.name} "
            f"({phishing_count} phishing, {benign_count} benign)"
        )
        frames.append(df_malicious)

    # Load dataset_phishing.csv if provided
    if dataset_phishing_path and dataset_phishing_path.exists():
        df_dataset_phishing = load_dataset_phishing_status(dataset_phishing_path)
        phishing_count = (df_dataset_phishing["is_phishing"] == 1).sum()
        benign_count = (df_dataset_phishing["is_phishing"] == 0).sum()
        print(
            f"Loaded {len(df_dataset_phishing)} URLs from {dataset_phishing_path.name} "
            f"({phishing_count} phishing, {benign_count} legitimate)"
        )
        frames.append(df_dataset_phishing)

    # Combine all
    combined = pd.concat(frames, ignore_index=True)
    print(f"\nBefore cleaning: {len(combined)} total URLs")

    # Clean
    combined = combined.dropna(subset=["url", "is_phishing"])
    combined = combined.drop_duplicates(subset=["url"])
    combined = filter_valid_http_urls(combined)
    combined = combined.reset_index(drop=True)

    print(f"After cleaning: {len(combined)} URLs")
    print(f"Class distribution:\n{combined['is_phishing'].value_counts().rename('count').sort_index()}")
    
    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integrate malicious_phish.csv with existing datasets"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("malicious_phish.csv"),
        help="Path to malicious_phish.csv",
    )
    parser.add_argument(
        "--phishing-dataset",
        type=Path,
        nargs="+",
        default=[Path("PhiUSIIL_Phishing_URL_Dataset.csv")],
        help="One or more phishing dataset CSV paths",
    )
    parser.add_argument(
        "--dataset-phishing",
        type=Path,
        default=Path("dataset_phishing.csv"),
        help="Path to dataset_phishing.csv (must include status column)",
    )
    parser.add_argument(
        "--legitimate-dataset",
        type=Path,
        default=Path("new_data_urls.csv"),
        help="Legitimate dataset CSV path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for combined preprocessed data",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    processed = combine_and_preprocess(
        phishing_paths=args.phishing_dataset,
        legitimate_path=args.legitimate_dataset,
        malicious_phish_path=args.input,
        dataset_phishing_path=args.dataset_phishing,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    processed.to_csv(args.output, index=False)

    print(f"\n✅ Saved {len(processed)} combined URLs to {args.output}")


if __name__ == "__main__":
    main()
