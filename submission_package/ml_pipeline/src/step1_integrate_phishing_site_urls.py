"""Step 1c: Integrate phishing_site_urls.csv dataset.

This script integrates the phishing_site_urls.csv dataset (549K+ URLs) into your training pipeline.

Usage:
    python src/step1_integrate_phishing_site_urls.py \
        --input phishing_site_urls.csv \
        --output data/phishing_site_urls_prepared.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integrate phishing_site_urls dataset for model training"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("phishing_site_urls.csv"),
        help="Path to the phishing_site_urls dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/phishing_site_urls_prepared.csv"),
        help="Output path for prepared dataset",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Loading phishing_site_urls dataset from {args.input}...")
    df = pd.read_csv(args.input)
    print(f"Original shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")

    # Normalize column names (case-insensitive)
    df.columns = df.columns.str.lower()

    # Map 'bad' label to 'Phishing', 'good' to 'Legitimate'
    if "label" in df.columns:
        label_mapping = {
            "bad": "Phishing",
            "good": "Legitimate",
            "phishing": "Phishing",
            "legitimate": "Legitimate",
        }
        df["label"] = df["label"].str.lower().map(label_mapping)

    # Remove rows with unknown labels
    df = df[df["label"].notna()]
    print(f"After label mapping: {df.shape}")

    # Rename columns to match standard format (URL, Label)
    df = df.rename(columns={"url": "URL", "label": "Label"})

    # Ensure required columns exist
    required_columns = ["URL", "Label"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in dataset")

    # Remove duplicate URLs
    n_before = len(df)
    df = df.drop_duplicates(subset=["URL"])
    n_after = len(df)
    print(f"Removed {n_before - n_after} duplicate URLs. Remaining: {n_after}")

    # Remove URLs with empty/null values
    df = df.dropna(subset=["URL", "Label"])
    print(f"After removing nulls: {df.shape}")

    # Display label distribution
    print(f"\nLabel distribution:")
    print(df["Label"].value_counts())

    # Save prepared dataset
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nPrepared dataset saved to {args.output}")


if __name__ == "__main__":
    main()
