"""Merge external dataset with existing training data.

This script combines the external Phishing_Legitimate dataset with your existing
extracted URL features to create a larger, more diverse training dataset.

Usage:
    python src/merge_datasets.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    # Paths
    external_dataset_path = Path("data/external_dataset_prepared.csv")
    existing_dataset_path = Path("data/url_features.csv")
    merged_output_path = Path("data/merged_training_data.csv")

    # Check if external dataset has been prepared
    if not external_dataset_path.exists():
        print(f"⚠️ External dataset not found at {external_dataset_path}")
        print("Run 'python src/step1_integrate_external_dataset.py' first")
        return

    if not existing_dataset_path.exists():
        print(f"⚠️ Existing dataset not found at {existing_dataset_path}")
        return

    print("Loading datasets...")
    external_df = pd.read_csv(external_dataset_path)
    existing_df = pd.read_csv(existing_dataset_path)

    print(f"External dataset shape: {external_df.shape}")
    print(f"Existing dataset shape: {existing_df.shape}")
    print(f"External columns: {list(external_df.columns)}")
    print(f"Existing columns: {list(existing_df.columns)}")

    # Get common columns (intersection of feature columns)
    external_features = set(external_df.columns) - {"is_phishing"}
    existing_features = set(existing_df.columns) - {"is_phishing"}
    
    common_features = external_features.intersection(existing_features)
    
    if common_features:
        print(f"\n✅ Found {len(common_features)} common features:")
        print(f"   {sorted(common_features)}")
        
        # Merge using only common features
        external_subset = external_df[list(common_features) + ["is_phishing"]]
        existing_subset = existing_df[list(common_features) + ["is_phishing"]]
        
        merged_df = pd.concat(
            [existing_subset, external_subset], 
            ignore_index=True
        )
        
        print(f"\n📊 Merged dataset shape: {merged_df.shape}")
        print(f"Class distribution:\n{merged_df['is_phishing'].value_counts()}")
        print(f"Duplicate samples: {merged_df.duplicated().sum()}")
        
        # Remove duplicates if any
        merged_df = merged_df.drop_duplicates()
        print(f"After removing duplicates: {merged_df.shape}")
        
        # Save merged dataset
        merged_df.to_csv(merged_output_path, index=False)
        print(f"\n✅ Merged dataset saved to {merged_output_path}")
    else:
        print("\n⚠️ No common features found between datasets.")
        print("The external dataset has different features than your existing dataset.")
        print("\nOptions:")
        print("1. Use the external dataset alone: Step 2 & 3 with external_dataset_prepared.csv")
        print("2. Align the feature extraction pipelines")
        print("3. Use the external dataset to train separate models")


if __name__ == "__main__":
    main()
