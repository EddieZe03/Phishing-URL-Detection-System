"""Step 1: Integrate all datasets including the new urldata.csv for maximum diversity.

This script combines:
- urldata.csv (NEW - 420K URLs)
- malicious_phish.csv (44M)
- dataset_phishing.csv (3.5M)
- Existing phishing/legitimate datasets

Usage:
    python src/step1_integrate_all_datasets.py \
        --urldata urldata.csv \
        --malicious-phish malicious_phish.csv \
        --dataset-phishing dataset_phishing.csv \
        --phishing PhiUSIIL_Phishing_URL_Dataset.csv \
        --legitimate new_data_urls.csv \
        --output data/processed_urls_with_all_datasets.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, cast

import pandas as pd

URL_COLUMN_CANDIDATES = ["url", "URL", "link", "Link"]
PHISHING_LABEL = 1
LEGITIMATE_LABEL = 0


def resolve_path(csv_path: Path | None) -> Path | None:
    """Resolve a path from cwd first, then project root when run from src/."""
    if csv_path is None:
        return None
    if csv_path.exists():
        return csv_path

    project_root_candidate = Path(__file__).resolve().parents[1] / csv_path
    if project_root_candidate.exists():
        return project_root_candidate

    return csv_path


def find_url_column(df: pd.DataFrame) -> str:
    """Return the first matching URL column name, else raise an error."""
    for col in URL_COLUMN_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not find URL column. Expected one of: "
        f"{', '.join(URL_COLUMN_CANDIDATES)}"
    )


def load_urldata(csv_path: Path) -> pd.DataFrame:
    """Load urldata.csv with 'url' and 'label' columns (good/bad)."""
    df = pd.read_csv(csv_path)
    url_col = find_url_column(df)

    normalized = pd.DataFrame()
    normalized["url"] = df[url_col].astype(str).str.strip()
    
    # Convert label: "bad" -> 1 (phishing), "good" -> 0 (legitimate)
    label_col = df["label"].astype(str).str.lower().str.strip()
    normalized["is_phishing"] = (label_col == "bad").astype(int)
    
    return normalized


def load_dataset(csv_path: Path, label: int) -> pd.DataFrame:
    """Load a dataset and normalize it to ['url', 'is_phishing']."""
    df = pd.read_csv(csv_path)
    url_col = find_url_column(df)

    normalized = pd.DataFrame()
    normalized["url"] = df[url_col].astype(str).str.strip()
    normalized["is_phishing"] = label
    return normalized


def load_malicious_phish(csv_path: Path) -> pd.DataFrame:
    """Load malicious_phish.csv and convert type column to binary labels."""
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
    urldata_path: Path | None,
    phishing_paths: Iterable[Path],
    legitimate_path: Path,
    malicious_phish_path: Path | None,
    dataset_phishing_path: Path | None,
    phishing_database_path: Path | None,
    deduplicate_urls: bool,
    http_only: bool,
) -> pd.DataFrame:
    """Load, merge, clean and return a preprocessed dataframe."""
    frames: list[pd.DataFrame] = []

    # Load NEW urldata first (highest priority for diversity)
    if urldata_path and urldata_path.exists():
        print(f"Loading urldata.csv...")
        df_urldata = load_urldata(urldata_path)
        frames.append(df_urldata)

    # Load malicious_phish
    if malicious_phish_path and malicious_phish_path.exists():
        print(f"Loading malicious_phish.csv...")
        df_malicious = load_malicious_phish(malicious_phish_path)
        frames.append(df_malicious)

    # Load dataset_phishing
    if dataset_phishing_path and dataset_phishing_path.exists():
        print(f"Loading dataset_phishing.csv...")
        df_dataset_phishing = load_dataset_phishing_status(dataset_phishing_path)
        frames.append(df_dataset_phishing)

    # Load Phishing.Database prepared feeds
    if phishing_database_path and phishing_database_path.exists():
        print(f"Loading phishing_database dataset: {phishing_database_path.name}")
        frames.append(load_dataset(phishing_database_path, label=PHISHING_LABEL))

    # Load original phishing datasets
    for path in phishing_paths:
        if path.exists():
            print(f"Loading phishing dataset: {path.name}")
            frames.append(load_dataset(path, label=PHISHING_LABEL))

    # Load legitimate dataset
    if legitimate_path.exists():
        print(f"Loading legitimate dataset: {legitimate_path.name}")
        frames.append(load_dataset(legitimate_path, label=LEGITIMATE_LABEL))

    # Combine all
    print(f"Combining {len(frames)} datasets...")
    if not frames:
        raise ValueError(
            "No datasets were loaded. Check input file paths. "
            "Tip: run from project root or pass paths like ../urldata.csv when inside src/."
        )
    combined = pd.concat(frames, ignore_index=True)

    print(f"Before filtering: {len(combined)} rows")
    
    # Clean
    combined = combined.dropna(subset=["url", "is_phishing"])

    if deduplicate_urls:
        combined = combined.drop_duplicates(subset=["url"])

    if http_only:
        combined = filter_valid_http_urls(combined)

    combined = combined.reset_index(drop=True)

    print(f"After filtering: {len(combined)} rows")
    print(f"Label distribution:\n{combined['is_phishing'].value_counts()}")

    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 1 - Integrate all datasets for phishing URL detection"
    )
    parser.add_argument("--urldata", type=Path, help="New urldata.csv file")
    parser.add_argument("--phishing", type=Path, nargs="+", help="Phishing dataset(s)")
    parser.add_argument("--legitimate", type=Path, required=True, help="Legitimate dataset")
    parser.add_argument(
        "--malicious-phish", type=Path, help="Optional malicious_phish.csv"
    )
    parser.add_argument(
        "--dataset-phishing", type=Path, help="Optional dataset_phishing.csv"
    )
    parser.add_argument(
        "--phishing-database",
        type=Path,
        help="Optional prepared Phishing.Database CSV",
    )
    parser.add_argument(
        "--disable-dedup",
        action="store_true",
        help="Keep duplicate URLs (useful for full-volume experiments)",
    )
    parser.add_argument(
        "--allow-non-http",
        action="store_true",
        help="Keep URLs that do not start with http:// or https://",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output CSV file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    args.urldata = resolve_path(args.urldata)
    args.legitimate = resolve_path(args.legitimate)
    args.malicious_phish = resolve_path(args.malicious_phish)
    args.dataset_phishing = resolve_path(args.dataset_phishing)
    args.phishing_database = resolve_path(args.phishing_database)
    args.phishing = [resolve_path(p) for p in (args.phishing or []) if resolve_path(p) is not None]

    df = combine_and_preprocess(
        urldata_path=args.urldata,
        phishing_paths=args.phishing or [],
        legitimate_path=args.legitimate,
        malicious_phish_path=args.malicious_phish,
        dataset_phishing_path=args.dataset_phishing,
        phishing_database_path=args.phishing_database,
        deduplicate_urls=not args.disable_dedup,
        http_only=not args.allow_non_http,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    print(f"✓ Saved combined dataset to {args.output}")


if __name__ == "__main__":
    main()
