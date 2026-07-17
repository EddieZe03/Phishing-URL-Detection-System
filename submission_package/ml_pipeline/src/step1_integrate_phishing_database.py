"""Step 1d: Integrate the Phishing.Database feeds into the training pipeline.

The Phishing.Database repository publishes phishing indicators as text feeds:
- phishing-links-*.txt
- phishing-domains-*.txt
- phishing-IPs-*.txt

This script downloads the active feeds from the upstream GitHub repository,
normalizes them into URL rows, labels them as phishing, and writes a CSV that
matches the raw-URL training pipeline.

Usage:
    python src/step1_integrate_phishing_database.py \
        --output data/phishing_database_prepared.csv
"""

from __future__ import annotations

import argparse
import csv
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd


REPO_OWNER = "Phishing-Database"
REPO_NAME = "Phishing.Database"
REPO_BRANCH = "master"

ACTIVE_FEEDS = {
    "phishing-links-ACTIVE.txt": "link",
    "phishing-domains-ACTIVE.txt": "domain",
    "phishing-IPs-ACTIVE.txt": "ip",
}


@dataclass(frozen=True)
class FeedRow:
    url: str
    source_feed: str
    feed_type: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integrate Phishing.Database active feeds into training data"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/phishing_database_prepared.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=REPO_BRANCH,
        help="Git branch to read from in the upstream repository",
    )
    return parser.parse_args()


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _normalize_host_entry(entry: str) -> str:
    entry = html.unescape(entry.strip())
    if not entry:
        return ""

    parsed = urlparse(entry)
    if parsed.scheme:
        return entry

    if "/" in entry or "?" in entry or "#" in entry:
        return f"http://{entry}"

    return f"http://{entry}/"


def _iter_feed_rows(feed_name: str, content: str) -> Iterable[FeedRow]:
    feed_type = ACTIVE_FEEDS[feed_name]
    reader = csv.reader(content.splitlines())

    for row in reader:
        if not row:
            continue

        entry = row[0].strip()
        if not entry or entry.startswith("#"):
            continue

        normalized = _normalize_host_entry(entry)
        if not normalized:
            continue

        yield FeedRow(url=normalized, source_feed=feed_name, feed_type=feed_type)


def _build_feed_url(feed_name: str, branch: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/{feed_name}"


def main() -> None:
    args = parse_args()

    all_rows: list[FeedRow] = []

    for feed_name in ACTIVE_FEEDS:
        feed_url = _build_feed_url(feed_name, args.branch)
        print(f"Downloading {feed_name}...")
        try:
            content = _fetch_text(feed_url)
        except (HTTPError, URLError) as exc:
            print(f"  ✗ Failed to fetch {feed_name}: {exc}")
            continue

        rows = list(_iter_feed_rows(feed_name, content))
        print(f"  ✓ Loaded {len(rows)} rows")
        all_rows.extend(rows)

    if not all_rows:
        raise RuntimeError("No rows were loaded from Phishing.Database feeds.")

    df = pd.DataFrame(
        {
            "URL": [row.url for row in all_rows],
            "Label": ["Phishing"] * len(all_rows),
            "Source": [row.source_feed for row in all_rows],
            "FeedType": [row.feed_type for row in all_rows],
        }
    )

    before = len(df)
    df = df.drop_duplicates(subset=["URL"]).reset_index(drop=True)
    print(f"Combined rows: {before}")
    print(f"Unique URLs: {len(df)}")
    print(f"Feed type counts:\n{df['FeedType'].value_counts()}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Saved prepared dataset to {args.output}")


if __name__ == "__main__":
    main()