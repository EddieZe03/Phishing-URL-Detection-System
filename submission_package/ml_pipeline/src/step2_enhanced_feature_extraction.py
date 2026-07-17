"""Step 2 Enhanced: Advanced feature extraction for phishing URL detection.

Extends the basic feature set with punycode detection, entropy variants,
character distribution analysis, domain reputation signals, and more.

Usage:
    python src/step2_enhanced_feature_extraction.py \
        --input data/processed_urls.csv \
        --output data/url_features_enhanced.csv \
        --whois-cache artifacts/whois_cache.csv
"""

from __future__ import annotations

import re
import math
from pathlib import Path
from urllib.parse import urlparse
from typing import cast
import argparse

import pandas as pd
import tldextract

# Import existing feature extraction for reuse
from step2_feature_extraction import (
    extract_features_from_urls,
    _registered_domain,
    _subdomain_count,
    _url_entropy,
    uses_ip_address,
    get_domain_age_days,
    has_whois_registrar,
    dns_resolves,
    redirection_count,
)


# High-risk TLDs associated with phishing and abuse
HIGH_RISK_TLDS = {
    "tk", "ml", "ga", "cf", "gq", "xyz", "top", "work", "bid", "download",
    "science", "accountant", "party", "link", "review", "cricket", "stream",
    "date", "loan", "country", "faith", "forum", "gdn", "info", "online",
    "pw", "cc", "host", "click", "date", "download", "site", "space",
    "website", "shop", "trade"
}

# Common phishing target brands for impersonation detection
PHISHING_TARGET_BRANDS = {
    "amazon", "apple", "google", "microsoft", "facebook", "twitter", "linkedin",
    "paypal", "ebay", "bank", "banking", "payoneer", "stripe", "square", "crypto",
    "bitcoin", "ethereum", "coinbase", "binance", "netflix", "disney", "hulu",
    "spotify", "adobe", "office", "zoom", "slack", "telegram", "whatsapp",
    "instagram", "pinterest", "reddit", "github", "gitlab", "npm", "pypi"
}


def _is_punycode(url: str) -> int:
    """Detect if URL uses punycode encoding (IDN homograph attack indicator)."""
    if "xn--" in url.lower():
        return 1
    return 0


def _hostname_has_punycode(url: str) -> int:
    """More specific: punycode in hostname only."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if "xn--" in hostname:
            return 1
    except Exception:
        pass
    return 0


def _brand_impersonation_score(url: str) -> int:
    """Count how many phishing target brands appear in the URL."""
    lower = url.lower()
    count = 0
    for brand in PHISHING_TARGET_BRANDS:
        # Check for brand with word boundaries or common separators
        pattern = rf"\b{re.escape(brand)}\b|{re.escape(brand)}-|-{re.escape(brand)}"
        if re.search(pattern, lower):
            count += 1
    return min(count, 3)  # Cap at 3


def _entropy_variants(url: str) -> tuple[float, float, float]:
    """Return entropy of domain, path, and query separately."""
    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    
    def entropy(s: str) -> float:
        if not s:
            return 0.0
        counts: dict[str, int] = {}
        for ch in s:
            counts[ch] = counts.get(ch, 0) + 1
        total = len(s)
        ent = 0.0
        for count in counts.values():
            p = count / total
            ent -= p * math.log2(p) if p > 0 else 0
        return ent
    
    return entropy(domain), entropy(path), entropy(query)


def _consonant_vowel_ratio(text: str) -> float:
    """Ratio of consonants to vowels; high values indicate random/obfuscated text."""
    vowels = set("aeiouAEIOU")
    consonants = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")
    
    vowel_count = sum(1 for ch in text if ch in vowels)
    consonant_count = sum(1 for ch in text if ch in consonants)
    
    if vowel_count == 0:
        return float(consonant_count)
    return consonant_count / vowel_count


def _rare_char_count(url: str) -> int:
    """Count rare/unusual characters in URL that might indicate obfuscation."""
    # Rare punctuation and symbols often used in obfuscation
    rare_chars = set("!$&'()*+,;=?@[]{}|\\<>\"^`~#%")
    return sum(1 for ch in url if ch in rare_chars)


def _numeric_domain_ratio(url: str) -> float:
    """Ratio of digits to letters in domain; high values suggest obfuscation."""
    try:
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()
        if not domain:
            return 0.0
        letters = sum(1 for ch in domain if ch.isalpha())
        digits = sum(1 for ch in domain if ch.isdigit())
        if letters == 0:
            return 1.0 if digits > 0 else 0.0
        return digits / letters
    except Exception:
        return 0.0


def _has_non_standard_port(url: str) -> int:
    """Detect non-standard ports (phishing often uses 8080, 8888, etc.)."""
    try:
        parsed = urlparse(url)
        port = parsed.port
        if port is None:
            return 0
        # Standard ports: 80, 443, 8443
        if port in {80, 443, 8443}:
            return 0
        # Non-standard ports are suspicious
        return 1
    except Exception:
        return 0


def _longest_label_length(url: str) -> int:
    """Longest label (between dots) in domain; unusually long labels suggest phishing."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return 0
        labels = hostname.split(".")
        return max(len(label) for label in labels) if labels else 0
    except Exception:
        return 0


def _domain_label_count(url: str) -> int:
    """Number of labels (parts separated by dots) in domain."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return 0
        return len([l for l in hostname.split(".") if l])
    except Exception:
        return 0


def _has_multiple_hyphens_in_domain(url: str) -> int:
    """Multiple hyphens in domain are a phishing indicator."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return 0
        # Count hyphens; if >= 2, it's suspicious
        return 1 if hostname.count("-") >= 2 else 0
    except Exception:
        return 0


def _url_length_category(url: str) -> int:
    """Categorical encoding of URL length: 0=short, 1=medium, 2=long, 3=very_long."""
    length = len(url)
    if length < 50:
        return 0
    elif length < 100:
        return 1
    elif length < 150:
        return 2
    else:
        return 3


def _fragment_length(url: str) -> int:
    """Length of the fragment/anchor; phishing URLs sometimes hide domain in fragment."""
    try:
        parsed = urlparse(url)
        fragment = (parsed.fragment or "")
        return len(fragment)
    except Exception:
        return 0


def _has_fragment_url(url: str) -> int:
    """Detect if URL has a fragment that looks like another URL."""
    try:
        parsed = urlparse(url)
        fragment = (parsed.fragment or "").lower()
        if "http" in fragment or "://" in fragment:
            return 1
    except Exception:
        pass
    return 0


def extract_enhanced_features(url_series: pd.Series) -> pd.DataFrame:
    """Extract advanced features for phishing detection."""
    urls = url_series.fillna("").astype(str).str.strip()
    
    features = pd.DataFrame()
    
    # Punycode features
    features["has_punycode"] = urls.apply(_is_punycode)
    features["hostname_has_punycode"] = urls.apply(_hostname_has_punycode)
    
    # Brand impersonation
    features["brand_impersonation_score"] = urls.apply(_brand_impersonation_score)
    
    # Entropy variants
    domain_ent, path_ent, query_ent = zip(*urls.apply(_entropy_variants))
    features["domain_entropy"] = domain_ent
    features["path_entropy"] = path_ent
    features["query_entropy"] = query_ent
    
    # Character distribution
    features["rare_char_count"] = urls.apply(_rare_char_count)
    features["numeric_domain_ratio"] = urls.apply(_numeric_domain_ratio)
    
    # Domain structure
    features["longest_domain_label"] = urls.apply(_longest_label_length)
    features["domain_label_count"] = urls.apply(_domain_label_count)
    features["has_multiple_hyphens_domain"] = urls.apply(_has_multiple_hyphens_in_domain)
    
    # Port analysis
    features["has_non_standard_port"] = urls.apply(_has_non_standard_port)
    
    # URL structure
    features["fragment_length"] = urls.apply(_fragment_length)
    features["has_fragment_url"] = urls.apply(_has_fragment_url)
    features["url_length_category"] = urls.apply(_url_length_category)
    
    return cast(pd.DataFrame, features)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enhanced feature extraction for phishing URL detection"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url-column", type=str, default="url")
    parser.add_argument("--target-column", type=str, default="is_phishing")
    parser.add_argument(
        "--whois-cache",
        type=Path,
        default=Path("artifacts/whois_cache.csv"),
        help="CSV cache for WHOIS lookups",
    )
    parser.add_argument(
        "--include-basic-features",
        action="store_true",
        default=True,
        help="Include basic features from step2_feature_extraction.py",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    # Load data
    df = pd.read_csv(args.input)
    if args.url_column not in df.columns:
        raise ValueError(f"Missing URL column: {args.url_column}")
    
    # Extract basic features
    basic_features = extract_features_from_urls(
        df[args.url_column],
        whois_cache_path=args.whois_cache,
    )
    
    # Extract enhanced features
    enhanced_features = extract_enhanced_features(df[args.url_column])
    
    # Combine both
    combined_features = pd.concat([basic_features, enhanced_features], axis=1)
    
    # Add target if present
    if args.target_column in df.columns:
        combined_features[args.target_column] = df[args.target_column]
    
    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    combined_features.to_csv(args.output, index=False)
    
    print(f"✓ Saved {len(combined_features)} rows with {len(combined_features.columns)} features to {args.output}")
    print(f"  Basic features: {len(basic_features.columns)}")
    print(f"  Enhanced features: {len(enhanced_features.columns)}")
    print(f"  Feature list: {list(combined_features.columns)}")


if __name__ == "__main__":
    main()
