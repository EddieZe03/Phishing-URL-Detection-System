"""Step 1b: Integrate external phishing dataset.

This script integrates the Phishing_Legitimate_full.csv dataset into your training pipeline.

Usage:
    python src/step1_integrate_external_dataset.py \
        --input Phishing_Legitimate_full.csv \
        --output data/external_dataset_prepared.csv

Then combine with existing data:
    python src/merge_datasets.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integrate external phishing dataset for model training"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Phishing_Legitimate_full.csv"),
        help="Path to the external phishing dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/external_dataset_prepared.csv"),
        help="Output path for prepared dataset",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Loading external dataset from {args.input}...")
    df = pd.read_csv(args.input)
    print(f"Original shape: {df.shape}")

    # Drop the 'id' column as it's not needed for training
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    
    # Rename CLASS_LABEL to is_phishing to match existing pipeline
    df = df.rename(columns={"CLASS_LABEL": "is_phishing"})
    
    # Ensure target column is numeric (0 = legitimate, 1 = phishing)
    df["is_phishing"] = df["is_phishing"].astype(int)
    
    print(f"Processed shape: {df.shape}")
    print(f"Class distribution:\n{df['is_phishing'].value_counts()}")
    print(f"Missing values:\n{df.isnull().sum().sum()}")
    
    # Create output directory if it doesn't exist
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the prepared dataset
    df.to_csv(args.output, index=False)
    print(f"\nDataset saved to {args.output}")


if __name__ == "__main__":
    main()
