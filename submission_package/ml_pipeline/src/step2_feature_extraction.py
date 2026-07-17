"""Step 2: Feature extraction for phishing URL detection.

Usage:
    python src/step2_feature_extraction.py \
        --input data/processed_urls.csv \
    --output data/url_features.csv \
    --whois-cache artifacts/whois_cache.csv
"""

from __future__ import annotations

import argparse
import contextlib
import io
import ipaddress
import math
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import pandas as pd
import tldextract
import whois


WHOIS_CACHE: dict[str, int] = {}
WHOIS_REGISTRAR_CACHE: dict[str, int] = {}
DNS_CACHE: dict[str, int] = {}
WHOIS_LIVE_ENABLED = True
WHOIS_TIMEOUT_SECONDS = 3
WHOIS_MAX_LOOKUPS = 100
WHOIS_MAX_ERRORS = 50
WHOIS_LOOKUP_COUNT = 0
WHOIS_ERROR_COUNT = 0
DNS_LIVE_ENABLED = True
DNS_TIMEOUT_SECONDS = 1.0
DNS_MAX_LOOKUPS = 5000
DNS_MAX_ERRORS = 200
DNS_LOOKUP_COUNT = 0
DNS_ERROR_COUNT = 0
SUSPICIOUS_KEYWORDS = [
    "login",
    "verify",
    "update",
    "secure",
    "account",
    "bank",
    "paypal",
    "confirm",
    "password",
    "signin",
    "webscr",
]
SUSPICIOUS_PATH_KEYWORDS = [
    "wp-admin",
    "wp-includes",
    "wp-content",
    "cgi-bin",
    "signin",
    "login",
    "verify",
    "secure",
    "account",
    "update",
    "password",
    "token",
    "invoice",
    "billing",
]


def _to_datetime(value: Any) -> datetime | None:
    """Normalize whois creation date values to datetime."""
    if value is None:
        return None

    if isinstance(value, list):
        for item in value:
            dt = _to_datetime(item)
            if dt is not None:
                return dt
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        # python-whois can return ISO-like strings for some TLDs.
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    return None


def _registered_domain(url: str) -> str:
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return ""


def _subdomain_count(url: str) -> int:
    extracted = tldextract.extract(url)
    subdomain = extracted.subdomain
    if not subdomain:
        return 0
    return len([p for p in subdomain.split(".") if p])


def _url_entropy(url: str) -> float:
    if not url:
        return 0.0
    counts: dict[str, int] = {}
    for ch in url:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(url)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def uses_ip_address(url: str) -> int:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not hostname:
        return 0

    try:
        ipaddress.ip_address(hostname)
        return 1
    except ValueError:
        return 0


def get_domain_age_days(url: str) -> int:
    """Return domain age in days, or -1 when unavailable."""
    domain = _registered_domain(url)
    if not domain:
        return -1

    _populate_whois_features(domain)
    return WHOIS_CACHE.get(domain, -1)


def has_whois_registrar(url: str) -> int:
    """Return 1 if WHOIS registrar metadata is available, else 0."""
    domain = _registered_domain(url)
    if not domain:
        return 0

    _populate_whois_features(domain)
    return WHOIS_REGISTRAR_CACHE.get(domain, 0)


def _whois_query(domain: str) -> Any | None:
    """Query WHOIS with guardrails to prevent long hangs on blocked networks."""
    global WHOIS_LIVE_ENABLED, WHOIS_LOOKUP_COUNT, WHOIS_ERROR_COUNT

    if not WHOIS_LIVE_ENABLED:
        return None

    if WHOIS_LOOKUP_COUNT >= WHOIS_MAX_LOOKUPS:
        WHOIS_LIVE_ENABLED = False
        return None

    try:
        WHOIS_LOOKUP_COUNT += 1
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                return whois.whois(
                    domain,
                    timeout=WHOIS_TIMEOUT_SECONDS,
                    quiet=True,
                    ignore_socket_errors=True,
                )
    except Exception:
        WHOIS_ERROR_COUNT += 1
        if WHOIS_ERROR_COUNT >= WHOIS_MAX_ERRORS:
            WHOIS_LIVE_ENABLED = False
        return None


def _populate_whois_features(domain: str) -> None:
    """Populate WHOIS-derived caches for one domain if not already cached."""
    if domain in WHOIS_CACHE and domain in WHOIS_REGISTRAR_CACHE:
        return

    result = _whois_query(domain)
    if result is None:
        WHOIS_CACHE.setdefault(domain, -1)
        WHOIS_REGISTRAR_CACHE.setdefault(domain, 0)
        return

    raw_creation_date = (
        result.get("creation_date")
        if isinstance(result, dict)
        else getattr(result, "creation_date", None)
    )
    creation_date = _to_datetime(raw_creation_date)
    if creation_date is None:
        WHOIS_CACHE[domain] = -1
    else:
        now = datetime.now(timezone.utc)
        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=timezone.utc)
        WHOIS_CACHE[domain] = max((now - creation_date).days, 0)

    raw_registrar = (
        result.get("registrar")
        if isinstance(result, dict)
        else getattr(result, "registrar", None)
    )
    registrar_value = str(raw_registrar).strip() if raw_registrar is not None else ""
    WHOIS_REGISTRAR_CACHE[domain] = int(
        bool(registrar_value and registrar_value.lower() != "none")
    )


def dns_resolves(url: str) -> int:
    """Return 1 if the hostname resolves via DNS, else 0."""
    global DNS_LIVE_ENABLED, DNS_LOOKUP_COUNT, DNS_ERROR_COUNT

    parsed = urlparse(url)
    host = (parsed.hostname or "").strip()
    if not host:
        return 0

    if host in DNS_CACHE:
        return DNS_CACHE[host]

    if not DNS_LIVE_ENABLED:
        DNS_CACHE[host] = 0
        return 0

    if DNS_LOOKUP_COUNT >= DNS_MAX_LOOKUPS:
        DNS_LIVE_ENABLED = False
        DNS_CACHE[host] = 0
        return 0

    previous_timeout = socket.getdefaulttimeout()
    try:
        DNS_LOOKUP_COUNT += 1
        socket.setdefaulttimeout(DNS_TIMEOUT_SECONDS)
        socket.gethostbyname(host)
        DNS_CACHE[host] = 1
        return 1
    except Exception:
        DNS_ERROR_COUNT += 1
        if DNS_ERROR_COUNT >= DNS_MAX_ERRORS:
            DNS_LIVE_ENABLED = False
        DNS_CACHE[host] = 0
        return 0
    finally:
        socket.setdefaulttimeout(previous_timeout)


def redirection_count(url: str) -> int:
    """Approximate redirection markers by counting embedded protocol patterns."""
    # Example suspicious pattern: https://example.com/http://phishing.com
    protocol_occurrences = len(re.findall(r"https?://", url, flags=re.IGNORECASE))
    return max(protocol_occurrences - 1, 0)


def _load_whois_cache(path: Path) -> None:
    if not path.exists():
        return

    try:
        cache_df = pd.read_csv(path, on_bad_lines="skip")
    except Exception:
        return

    if "domain" not in cache_df.columns or "age_days" not in cache_df.columns:
        return

    for _, row in cache_df.iterrows():
        domain = str(row["domain"]).strip()
        if not domain:
            continue
        try:
            WHOIS_CACHE[domain] = int(row["age_days"])
        except ValueError:
            WHOIS_CACHE[domain] = -1

        if "registrar_available" in cache_df.columns:
            try:
                WHOIS_REGISTRAR_CACHE[domain] = int(row["registrar_available"])
            except ValueError:
                WHOIS_REGISTRAR_CACHE[domain] = 0


def _save_whois_cache(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    domains = set(WHOIS_CACHE.keys()) | set(WHOIS_REGISTRAR_CACHE.keys())
    rows = [
        {
            "domain": d,
            "age_days": WHOIS_CACHE.get(d, -1),
            "registrar_available": WHOIS_REGISTRAR_CACHE.get(d, 0),
        }
        for d in domains
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _count_suspicious_keywords(url: str) -> int:
    lower = url.lower()
    return sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in lower)


def _count_suspicious_path_keywords(url: str) -> int:
    path = (urlparse(url).path or "").lower()
    return sum(1 for kw in SUSPICIOUS_PATH_KEYWORDS if kw in path)


def _path_depth(url: str) -> int:
    path = (urlparse(url).path or "").strip("/")
    if not path:
        return 0
    return len([segment for segment in path.split("/") if segment])


def extract_features_from_urls(
    url_series: pd.Series,
    whois_cache_path: Path | None = None,
    whois_timeout: int = 3,
    whois_max_lookups: int = 100,
    whois_max_errors: int = 50,
    dns_timeout: float = 1.0,
    dns_max_lookups: int = 5000,
    dns_max_errors: int = 200,
) -> pd.DataFrame:
    """Extract lexical, domain, and heuristic features from URL strings."""
    global WHOIS_TIMEOUT_SECONDS, WHOIS_MAX_LOOKUPS, WHOIS_MAX_ERRORS
    global WHOIS_LOOKUP_COUNT, WHOIS_ERROR_COUNT, WHOIS_LIVE_ENABLED
    global DNS_TIMEOUT_SECONDS, DNS_MAX_LOOKUPS, DNS_MAX_ERRORS
    global DNS_LOOKUP_COUNT, DNS_ERROR_COUNT, DNS_LIVE_ENABLED

    WHOIS_TIMEOUT_SECONDS = whois_timeout
    WHOIS_MAX_LOOKUPS = whois_max_lookups
    WHOIS_MAX_ERRORS = whois_max_errors
    WHOIS_LOOKUP_COUNT = 0
    WHOIS_ERROR_COUNT = 0
    WHOIS_LIVE_ENABLED = True
    DNS_TIMEOUT_SECONDS = dns_timeout
    DNS_MAX_LOOKUPS = dns_max_lookups
    DNS_MAX_ERRORS = dns_max_errors
    DNS_LOOKUP_COUNT = 0
    DNS_ERROR_COUNT = 0
    DNS_LIVE_ENABLED = True

    urls = url_series.fillna("").astype(str).str.strip()

    if whois_cache_path is not None:
        _load_whois_cache(whois_cache_path)

    domains = urls.apply(_registered_domain)

    features = pd.DataFrame()
    features["url_length"] = urls.str.len()
    features["num_dots"] = urls.str.count(r"\.")
    features["has_at_symbol"] = urls.str.contains("@", regex=False).astype(int)
    features["has_hyphen"] = urls.str.contains("-", regex=False).astype(int)
    features["uses_ip_address"] = urls.apply(uses_ip_address)
    features["domain_age_days"] = urls.apply(get_domain_age_days)
    features["whois_registrar_available"] = urls.apply(has_whois_registrar)
    features["dns_resolves"] = urls.apply(dns_resolves)
    features["domain_age_available"] = (features["domain_age_days"] >= 0).astype(int)
    features["is_new_domain_30d"] = (
        (features["domain_age_days"] >= 0) & (features["domain_age_days"] <= 30)
    ).astype(int)
    features["num_subdomains"] = urls.apply(_subdomain_count)
    features["path_length"] = urls.apply(lambda u: len(urlparse(u).path or ""))
    features["path_depth"] = urls.apply(_path_depth)
    features["query_length"] = urls.apply(lambda u: len(urlparse(u).query or ""))
    features["num_digits"] = urls.str.count(r"\d")
    features["num_special_chars"] = urls.str.count(r"[^A-Za-z0-9]")
    features["has_encoded_chars"] = urls.str.contains("%", regex=False).astype(int)
    features["has_suspicious_tld"] = domains.str.endswith(
        (".tk", ".ml", ".ga", ".cf", ".gq", ".xyz")
    ).astype(int)
    features["suspicious_keyword_count"] = urls.apply(_count_suspicious_keywords)
    features["suspicious_path_keyword_count"] = urls.apply(_count_suspicious_path_keywords)
    features["has_wp_path"] = urls.str.contains(
        r"wp-admin|wp-includes|wp-content", regex=True
    ).astype(int)
    features["url_entropy"] = urls.apply(_url_entropy)
    features["uses_https"] = urls.str.startswith("https://").astype(int)
    features["redirection_count"] = urls.apply(redirection_count)

    if whois_cache_path is not None:
        _save_whois_cache(whois_cache_path)

    return cast(pd.DataFrame, features)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 2 feature extraction for phishing URL detection"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url-column", type=str, default="url")
    parser.add_argument("--target-column", type=str, default="is_phishing")
    parser.add_argument(
        "--whois-cache",
        type=Path,
        default=Path("artifacts/whois_cache.csv"),
        help="CSV cache for WHOIS domain_age_days lookups",
    )
    parser.add_argument(
        "--whois-timeout",
        type=int,
        default=3,
        help="Timeout (seconds) per WHOIS lookup",
    )
    parser.add_argument(
        "--whois-max-lookups",
        type=int,
        default=100,
        help="Maximum live WHOIS queries per run before stopping",
    )
    parser.add_argument(
        "--whois-max-errors",
        type=int,
        default=50,
        help="Maximum WHOIS query errors before disabling live WHOIS",
    )
    parser.add_argument(
        "--dns-timeout",
        type=float,
        default=1.0,
        help="Timeout (seconds) per DNS lookup",
    )
    parser.add_argument(
        "--dns-max-lookups",
        type=int,
        default=5000,
        help="Maximum DNS lookups per run before stopping",
    )
    parser.add_argument(
        "--dns-max-errors",
        type=int,
        default=200,
        help="Maximum DNS lookup errors before disabling DNS lookups",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)
    if args.url_column not in df.columns:
        raise ValueError(f"Missing URL column: {args.url_column}")

    feature_df = extract_features_from_urls(
        df[args.url_column],
        whois_cache_path=args.whois_cache,
        whois_timeout=args.whois_timeout,
        whois_max_lookups=args.whois_max_lookups,
        whois_max_errors=args.whois_max_errors,
        dns_timeout=args.dns_timeout,
        dns_max_lookups=args.dns_max_lookups,
        dns_max_errors=args.dns_max_errors,
    )

    if args.target_column in df.columns:
        feature_df[args.target_column] = df[args.target_column]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    feature_df.to_csv(args.output, index=False)

    print(f"Saved {len(feature_df)} rows to {args.output}")
    print(f"WHOIS cache path: {args.whois_cache}")
    print(f"WHOIS lookups attempted: {WHOIS_LOOKUP_COUNT}")
    print(f"WHOIS lookup errors: {WHOIS_ERROR_COUNT}")
    print(f"WHOIS live enabled after run: {WHOIS_LIVE_ENABLED}")
    print(f"DNS lookups attempted: {DNS_LOOKUP_COUNT}")
    print(f"DNS lookup errors: {DNS_ERROR_COUNT}")
    print(f"DNS live enabled after run: {DNS_LIVE_ENABLED}")
    print("Feature columns:", list(feature_df.columns))


if __name__ == "__main__":
    main()
