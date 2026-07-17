"""Step 0: Download and normalize raw datasets for Step 1.

This script prepares the three CSV files expected by Step 1:
- data/phishtank.csv
- data/openphish.csv
- data/kaggle_legitimate.csv

Usage example:
    python src/step0_download_data.py \
        --phishtank-path data/raw/phishtank_input.csv \
        --legitimate-path data/raw/kaggle_legitimate_input.csv

You can provide each source either as a local path or URL.
For OpenPhish, the default source is https://openphish.com/feed.txt.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

URL_COLUMN_CANDIDATES = ["url", "URL", "link", "Link"]
DEFAULT_OPENPHISH_URL = "https://openphish.com/feed.txt"


def find_url_column(df: pd.DataFrame) -> str:
    for col in URL_COLUMN_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(
        "Could not find URL column. Expected one of: "
        f"{', '.join(URL_COLUMN_CANDIDATES)}"
    )


def _is_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def _load_txt_lines(source: str) -> list[str]:
    if _is_url(source):
        with urlopen(source) as response:  # nosec B310
            text = response.read().decode("utf-8", errors="ignore")
    else:
        text = Path(source).read_text(encoding="utf-8", errors="ignore")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines


def _load_url_dataframe(source: str, is_text_feed: bool) -> pd.DataFrame:
    if is_text_feed:
        rows = _load_txt_lines(source)
        return pd.DataFrame({"url": rows})

    df = pd.read_csv(source)
    url_col = find_url_column(df)
    return pd.DataFrame({"url": df[url_col].astype(str).str.strip()})


def _pick_source(path_value: str | None, url_value: str | None, label: str) -> str:
    if path_value:
        return path_value
    if url_value:
        return url_value
    raise ValueError(f"Missing source for {label}. Provide --{label}-path or --{label}-url.")


def _save_normalized(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clean_df = df.dropna(subset=["url"]).copy()
    clean_df["url"] = clean_df["url"].astype(str).str.strip()
    clean_df = clean_df[clean_df["url"] != ""]
    clean_df = clean_df.loc[~clean_df["url"].duplicated()].reset_index(drop=True)

    clean_df.to_csv(output_path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 0 dataset preparation for phishing URL detection"
    )

    parser.add_argument("--phishtank-path", type=str, default=None)
    parser.add_argument("--phishtank-url", type=str, default=None)

    parser.add_argument("--openphish-path", type=str, default=None)
    parser.add_argument("--openphish-url", type=str, default=DEFAULT_OPENPHISH_URL)

    parser.add_argument("--legitimate-path", type=str, default=None)
    parser.add_argument("--legitimate-url", type=str, default=None)

    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    phishtank_source = _pick_source(args.phishtank_path, args.phishtank_url, "phishtank")
    openphish_source = _pick_source(args.openphish_path, args.openphish_url, "openphish")
    legitimate_source = _pick_source(
        args.legitimate_path, args.legitimate_url, "legitimate"
    )

    phishtank_df = _load_url_dataframe(phishtank_source, is_text_feed=False)
    openphish_df = _load_url_dataframe(openphish_source, is_text_feed=True)
    legitimate_df = _load_url_dataframe(legitimate_source, is_text_feed=False)

    phishtank_out = args.output_dir / "phishtank.csv"
    openphish_out = args.output_dir / "openphish.csv"
    legitimate_out = args.output_dir / "kaggle_legitimate.csv"

    _save_normalized(phishtank_df, phishtank_out)
    _save_normalized(openphish_df, openphish_out)
    _save_normalized(legitimate_df, legitimate_out)

    print(f"Saved: {phishtank_out} ({len(phishtank_df)} rows before final clean)")
    print(f"Saved: {openphish_out} ({len(openphish_df)} rows before final clean)")
    print(f"Saved: {legitimate_out} ({len(legitimate_df)} rows before final clean)")


if __name__ == "__main__":
    main()
