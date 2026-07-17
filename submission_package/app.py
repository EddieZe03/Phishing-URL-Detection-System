from __future__ import annotations

import os
import html
import hashlib
import json
import re
import time
from pathlib import Path
import traceback
from typing import Any
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import joblib
import pandas as pd
import tldextract
from flask import Flask, jsonify, render_template, request

from src.output_handler import format_output
from src.step2_feature_extraction import extract_features_from_urls

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
_MODEL_PATH_FROM_ENV = os.getenv("FINAL_MODEL_PATH", "").strip()
_MODEL_DOWNLOAD_URL = os.getenv("MODEL_DOWNLOAD_URL", "").strip()
_MODEL_DOWNLOAD_SHA256 = os.getenv("MODEL_DOWNLOAD_SHA256", "").strip().lower()
_RUNTIME_MODEL_PATH = Path(
    os.getenv(
        "RUNTIME_MODEL_PATH",
        str(BASE_DIR / "artifacts" / "runtime" / "soft_voting_ensemble.joblib"),
    )
).expanduser()

MODEL_CANDIDATE_PATHS = [
    Path(_MODEL_PATH_FROM_ENV).expanduser() if _MODEL_PATH_FROM_ENV else None,
    _RUNTIME_MODEL_PATH,
    BASE_DIR / "artifacts" / "ensemble_all_datasets_retry" / "soft_voting_ensemble.joblib",
    BASE_DIR / "artifacts" / "ensemble_all_datasets" / "soft_voting_ensemble.joblib",
    BASE_DIR / "artifacts" / "final_submission" / "soft_voting_ensemble.joblib",
]

FINAL_MODEL_PATH = BASE_DIR / "artifacts" / "ensemble_all_datasets_retry" / "soft_voting_ensemble.joblib"
FINAL_THRESHOLD = 0.565
UNCERTAIN_LOWER_BOUND = float(os.getenv("UNCERTAIN_LOWER_BOUND", "0.45"))
UNCERTAIN_UPPER_BOUND = float(os.getenv("UNCERTAIN_UPPER_BOUND", "0.65"))
WHOIS_CACHE_PATH = BASE_DIR / "artifacts" / "whois_cache.csv"
MODEL_DISPLAY_NAME = "Soft Voting Ensemble (Retry Balanced Sample)"
EXPECTED_FEATURE_COLUMNS = [
    "url_length",
    "num_dots",
    "has_at_symbol",
    "has_hyphen",
    "uses_ip_address",
    "domain_age_days",
    "whois_registrar_available",
    "dns_resolves",
    "domain_age_available",
    "is_new_domain_30d",
    "num_subdomains",
    "path_length",
    "path_depth",
    "query_length",
    "num_digits",
    "num_special_chars",
    "has_encoded_chars",
    "has_suspicious_tld",
    "suspicious_keyword_count",
    "suspicious_path_keyword_count",
    "has_wp_path",
    "url_entropy",
    "uses_https",
    "redirection_count",
]

_MODEL: Any | None = None
_MODEL_PATH: Path | None = None
PHISHING_THRESHOLD = float(os.getenv("PHISHING_THRESHOLD", str(FINAL_THRESHOLD)))
THREAT_INTEL_ENABLED = os.getenv("THREAT_INTEL_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
THREAT_INTEL_URLHAUS_ENABLED = os.getenv("THREAT_INTEL_URLHAUS_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
THREAT_INTEL_TIMEOUT_SEC = float(os.getenv("THREAT_INTEL_TIMEOUT_SEC", "2.0"))
THREAT_INTEL_CACHE_TTL_SEC = int(os.getenv("THREAT_INTEL_CACHE_TTL_SEC", "21600"))
THREAT_INTEL_MODEL_WEIGHT = float(os.getenv("THREAT_INTEL_MODEL_WEIGHT", "0.72"))
THREAT_INTEL_CACHE_PATH = Path(
    os.getenv(
        "THREAT_INTEL_CACHE_PATH",
        str(BASE_DIR / "artifacts" / "threat_intel_cache.json"),
    )
).expanduser()

_THREAT_INTEL_CACHE: dict[str, dict[str, Any]] | None = None

TRUSTED_DOMAINS = {
    "youtube.com",
    "google.com",
    "wikipedia.org",
    "github.com",
    "stackoverflow.com",
    "reddit.com",
    "openai.com",
    "chatgpt.com",
    "microsoft.com",
    "apple.com",
    "amazon.com",
    "paypal.com",
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "harvard.edu",
    "stanford.edu",
    "mit.edu",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
}

HIGH_RISK_BRAND_TOKENS = {
    "aol",
    "remax",
    "paypal",
    "microsoft",
    "office365",
    "outlook",
    "appleid",
    "icloud",
    "chase",
    "wellsfargo",
    "bankofamerica",
    "amazon",
    "facebook",
    "instagram",
    "linkedin",
    "hsbc",
    "abn",
    "amro",
    "barclays",
    "citibank",
    "discover",
}

BANKING_ENDPOINT_KEYWORDS = {
    "identification",
    "verify",
    "confirm",
    "authenticate",
    "authorization",
    "activation",
}

HIGH_RISK_MAIL_STACK_TOKENS = {"zimbra", "owa", "exch", "webmail"}
HIGH_RISK_PATH_TOKENS = {
    "plugins",
    "tmp",
    "components",
    "com_newsfeeds",
    "cadastro",
    "verify",
    "update",
    "secure",
    "billing",
}


def _load_threat_intel_cache() -> dict[str, dict[str, Any]]:
    global _THREAT_INTEL_CACHE

    if _THREAT_INTEL_CACHE is not None:
        return _THREAT_INTEL_CACHE

    cache: dict[str, dict[str, Any]] = {}
    try:
        if THREAT_INTEL_CACHE_PATH.exists() and THREAT_INTEL_CACHE_PATH.is_file():
            loaded = json.loads(THREAT_INTEL_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key, value in loaded.items():
                    if isinstance(key, str) and isinstance(value, dict):
                        cache[key] = value
    except Exception:
        app.logger.warning("Threat-intel cache load failed. Starting with an empty cache.")

    _THREAT_INTEL_CACHE = cache
    return _THREAT_INTEL_CACHE


def _save_threat_intel_cache() -> None:
    cache = _load_threat_intel_cache()
    try:
        THREAT_INTEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        THREAT_INTEL_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        app.logger.warning("Threat-intel cache save failed.")


def _get_cached_threat_intel(url: str) -> dict[str, Any] | None:
    cache = _load_threat_intel_cache()
    item = cache.get(url)
    if not isinstance(item, dict):
        return None

    ts = item.get("timestamp")
    if not isinstance(ts, (int, float)):
        return None

    if time.time() - float(ts) > THREAT_INTEL_CACHE_TTL_SEC:
        return None

    cached_result = item.get("result")
    if isinstance(cached_result, dict):
        return cached_result
    return None


def _set_cached_threat_intel(url: str, result: dict[str, Any]) -> None:
    cache = _load_threat_intel_cache()
    cache[url] = {
        "timestamp": time.time(),
        "result": result,
    }
    _save_threat_intel_cache()


def _urlhaus_lookup(url: str) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        payload = urlencode({"url": url}).encode("utf-8")
        request_obj = Request(
            "https://urlhaus-api.abuse.ch/v1/url/",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "PhishGuardThreatIntel/1.0",
            },
            method="POST",
        )
        with urlopen(request_obj, timeout=THREAT_INTEL_TIMEOUT_SEC) as response:
            body = response.read().decode("utf-8", errors="ignore")

        parsed = json.loads(body)
        query_status = str(parsed.get("query_status", "")).lower()
        is_malicious = query_status == "ok"

        return {
            "checked": True,
            "provider": "urlhaus",
            "verdict": "malicious" if is_malicious else "not_listed",
            "malicious": is_malicious,
            "confidence": 1.0 if is_malicious else 0.0,
            "reason": (
                "URL is listed in URLhaus threat feed."
                if is_malicious
                else "URL not found in URLhaus threat feed."
            ),
            "latency_ms": round((time.perf_counter() - started_at) * 1000.0, 2),
        }
    except Exception as exc:
        return {
            "checked": False,
            "provider": "urlhaus",
            "verdict": "unknown",
            "malicious": False,
            "confidence": 0.0,
            "reason": f"Threat feed unavailable: {exc}",
            "latency_ms": round((time.perf_counter() - started_at) * 1000.0, 2),
        }


def _check_threat_intel(url: str) -> dict[str, Any]:
    if not THREAT_INTEL_ENABLED:
        return {
            "checked": False,
            "provider": "disabled",
            "verdict": "unknown",
            "malicious": False,
            "confidence": 0.0,
            "reason": "Threat intelligence disabled.",
            "latency_ms": 0.0,
            "cache_hit": False,
        }

    cached = _get_cached_threat_intel(url)
    if cached is not None:
        cached_copy = dict(cached)
        cached_copy["cache_hit"] = True
        return cached_copy

    if THREAT_INTEL_URLHAUS_ENABLED:
        result = _urlhaus_lookup(url)
    else:
        result = {
            "checked": False,
            "provider": "none",
            "verdict": "unknown",
            "malicious": False,
            "confidence": 0.0,
            "reason": "No threat-intel provider enabled.",
            "latency_ms": 0.0,
        }

    result["cache_hit"] = False
    _set_cached_threat_intel(url, result)
    return result


def _apply_intel_fusion(
    model_label: str,
    model_score: float,
    model_reason: str,
    intel: dict[str, Any],
) -> tuple[str, float, str, bool]:
    # Conservative fusion strategy:
    # - Intel positives can escalate risk.
    # - Non-listed/unknown intel does not reduce model risk.
    if not bool(intel.get("malicious", False)):
        return model_label, model_score, model_reason, False

    fused_score = max(
        model_score,
        (THREAT_INTEL_MODEL_WEIGHT * model_score)
        + ((1.0 - THREAT_INTEL_MODEL_WEIGHT) * 1.0),
    )

    fused_label = model_label
    fused_reason = model_reason

    if fused_score >= FINAL_THRESHOLD:
        fused_label = "Phishing"

    if (
        fused_label != model_label
        or "urlhaus" in str(intel.get("provider", "")).lower()
    ):
        fused_reason = (
            f"{model_reason} Threat-intel escalation applied: {intel.get('reason', '')} "
            f"(fused score={fused_score:.4f})."
        ).strip()

    return fused_label, fused_score, fused_reason, True


def _run_hybrid_detection(url: str) -> dict[str, Any]:
    started_at = time.perf_counter()
    model_label, model_score, model_reason = predict_url_label(url)
    model_inference_ms = (time.perf_counter() - started_at) * 1000.0

    intel = _check_threat_intel(url)
    fused_label, fused_score, fused_reason, fusion_applied = _apply_intel_fusion(
        model_label,
        model_score,
        model_reason,
        intel,
    )

    return {
        "label": fused_label,
        "phishing_score": fused_score,
        "reason": fused_reason,
        "model_label": model_label,
        "model_phishing_score": model_score,
        "model_reason": model_reason,
        "model_inference_ms": round(model_inference_ms, 2),
        "threat_intel": intel,
        "fusion_applied": fusion_applied,
    }


def _resolve_model_path() -> Path:
    """Load only the final submission model."""
    downloaded_path = _download_model_if_configured()
    if downloaded_path is not None and downloaded_path.exists() and downloaded_path.is_file():
        return downloaded_path

    for candidate in MODEL_CANDIDATE_PATHS:
        if candidate is None:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate

    searched_paths = [str(p) for p in MODEL_CANDIDATE_PATHS if p is not None]
    raise FileNotFoundError(
        "Final ensemble model not found. Searched: " + " | ".join(searched_paths)
    )


def _download_model_if_configured() -> Path | None:
    """Download model from external storage when configured for cloud deploys."""
    if not _MODEL_DOWNLOAD_URL:
        return None

    target = _RUNTIME_MODEL_PATH
    if target.exists() and target.is_file() and target.stat().st_size > 0:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()

    with urlopen(_MODEL_DOWNLOAD_URL, timeout=120) as response, temp_file.open("wb") as out_file:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
            digest.update(chunk)

    if temp_file.stat().st_size == 0:
        raise RuntimeError("Downloaded model file is empty.")

    if _MODEL_DOWNLOAD_SHA256 and digest.hexdigest().lower() != _MODEL_DOWNLOAD_SHA256:
        temp_file.unlink(missing_ok=True)
        raise RuntimeError("Downloaded model checksum does not match MODEL_DOWNLOAD_SHA256.")

    temp_file.replace(target)
    return target


def _get_model() -> Any:
    """Lazy-load model so server startup stays lightweight."""
    global _MODEL, _MODEL_PATH, PHISHING_THRESHOLD

    if _MODEL is not None:
        return _MODEL

    _MODEL_PATH = _resolve_model_path()
    _MODEL = joblib.load(_MODEL_PATH)
    return _MODEL


def _registered_domain(url: str) -> str:
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    host = urlparse(url).hostname
    return host or ""


def _normalize_input_url(raw_url: str) -> str:
    """Accept URLs with or without scheme and normalize for model inference."""
    # Decode common copied HTML entities (e.g. &amp;) before parsing features.
    url = html.unescape(raw_url.strip())
    if not url:
        return ""
    if "://" in url:
        return url
    return f"http://{url}"


def _is_probable_url(raw_text: str) -> bool:
    """Best-effort URL detection for mixed QR payloads and plain text."""
    text = html.unescape(raw_text.strip())
    if not text:
        return False

    lowered = text.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        parsed = urlparse(text)
        return bool(parsed.netloc)

    # Accept obvious host-style strings such as www.example.com/path.
    if text.startswith("www."):
        return True

    # Must include a dot-separated host token and no whitespace.
    if any(ch.isspace() for ch in text):
        return False

    host_candidate = text.split("/", 1)[0].split("?", 1)[0]
    if "." not in host_candidate:
        return False
    return bool(re.search(r"[A-Za-z]", host_candidate))


def _normalize_qr_payload(raw_text: str) -> str:
    """Normalize scanned QR payload text by removing whitespace separators."""
    return "".join(raw_text.strip().split())


def _candidate_emvco_payload(raw_text: str) -> str:
    """Extract EMVCo candidate from raw QR text (allowing URI-style prefixes)."""
    payload = _normalize_qr_payload(raw_text)
    # Some wallets expose payment payload as http://<payload> or https://<payload>.
    payload = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", payload)
    return payload


def _parse_emvco_tlv(payload: str) -> dict[str, str]:
    """Parse a flat EMVCo TLV payload into tag-value pairs."""
    values: dict[str, str] = {}
    i = 0
    n = len(payload)

    while i + 4 <= n:
        tag = payload[i:i + 2]
        length_text = payload[i + 2:i + 4]
        if not length_text.isdigit():
            break

        length = int(length_text)
        start = i + 4
        end = start + length
        if end > n:
            break

        values[tag] = payload[start:end]
        i = end

    return values


def _is_probable_emvco_payload(raw_text: str) -> bool:
    """Detect EMVCo-style merchant/payment QR payloads (including DuitNow)."""
    payload = _candidate_emvco_payload(raw_text)
    if len(payload) < 24:
        return False

    if not payload.startswith("0002"):
        return False

    if not payload.isdigit() and not payload.isalnum():
        return False

    fields = _parse_emvco_tlv(payload)
    if fields.get("00") not in {"01", "02"}:
        return False

    # Common EMVCo payment markers: transaction currency (53), country code (58), CRC (63).
    if "53" in fields and "58" in fields and "63" in fields:
        return True

    # Fallback marker for payment account templates in tags 26..51.
    for tag_num in range(26, 52):
        if f"{tag_num:02d}" in fields:
            return True

    return False


def _emvco_summary(raw_text: str) -> str:
    """Return a short user-facing summary from EMVCo fields when present."""
    payload = _candidate_emvco_payload(raw_text)
    fields = _parse_emvco_tlv(payload)

    merchant_name = fields.get("59", "")
    merchant_city = fields.get("60", "")
    country_code = fields.get("58", "")

    parts: list[str] = []
    if merchant_name:
        parts.append(f"merchant: {merchant_name}")
    if merchant_city:
        parts.append(f"city: {merchant_city}")
    if country_code:
        parts.append(f"country: {country_code}")

    if not parts:
        return "Detected an EMVCo-style payment QR payload."

    return "Detected an EMVCo-style payment QR payload (" + ", ".join(parts) + ")."


def _emvco_details(raw_text: str) -> dict[str, str]:
    """Return a compact set of useful EMVCo payment QR fields."""
    payload = _candidate_emvco_payload(raw_text)
    fields = _parse_emvco_tlv(payload)

    details: dict[str, str] = {}
    if fields.get("59"):
        details["merchant_name"] = fields["59"]
    if fields.get("60"):
        details["merchant_city"] = fields["60"]
    if fields.get("58"):
        details["country_code"] = fields["58"]
    if fields.get("00"):
        details["payload_format"] = fields["00"]

    return details


def _path_and_query_text(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    return f"{path}?{query}"


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _should_override_brand_mismatch(
    url: str,
    domain: str,
    suspicious_keyword_count: int,
    suspicious_path_count: int,
    path_depth: int,
    num_subdomains: int,
    has_encoded_chars: int,
) -> bool:
    if domain in TRUSTED_DOMAINS:
        return False

    text = _path_and_query_text(url)
    brand_hits = [token for token in HIGH_RISK_BRAND_TOKENS if token in text]
    if not brand_hits:
        return False

    # Brand appears in path/query but not in host/domain: common impersonation signal.
    mismatch_hits = [token for token in brand_hits if token not in domain]
    if not mismatch_hits:
        return False

    structural_signal = (
        suspicious_keyword_count >= 1
        or suspicious_path_count >= 1
        or path_depth >= 2
        or num_subdomains >= 2
        or has_encoded_chars == 1
    )
    return structural_signal


def _should_override_mail_stack(url: str, domain: str, path_depth: int) -> bool:
    if domain in TRUSTED_DOMAINS:
        return False

    text = _path_and_query_text(url)
    stack_hits = sum(1 for token in HIGH_RISK_MAIL_STACK_TOKENS if token in text)
    return stack_hits >= 2 and path_depth >= 2


def _should_override_php_trap(
    url: str,
    domain: str,
    suspicious_keyword_count: int,
    suspicious_path_count: int,
    path_depth: int,
) -> bool:
    if domain in TRUSTED_DOMAINS:
        return False

    text = _path_and_query_text(url)
    has_php_endpoint = ".php" in text
    risky_tokens = sum(1 for token in HIGH_RISK_PATH_TOKENS if token in text)

    return has_php_endpoint and path_depth >= 2 and (
        risky_tokens >= 2 or suspicious_keyword_count >= 1 or suspicious_path_count >= 1
    )


def _should_override_hosted_form(url: str, domain: str) -> bool:
    host = _host(url)
    text = _path_and_query_text(url)

    # Common hosted phishing pattern using Google-hosted form endpoints.
    if domain == "google.com" and host.startswith("docs.google.com"):
        if ("/viewform" in text or "formkey=" in text) and "/a/" in text:
            return True

    return False


def _should_override_wp_login(url: str, domain: str, path_depth: int) -> bool:
    """Detect WordPress admin + login pattern even on old domains."""
    if domain in TRUSTED_DOMAINS:
        return False

    text = _path_and_query_text(url)
    has_wp_path = "wp-admin" in text or "wp-includes" in text or "wp-content" in text
    has_login_pattern = "login" in text or "signin" in text or "password.php" in text
    
    return has_wp_path and has_login_pattern


def _should_override_banking_brand_endpoint(
    url: str,
    domain: str,
    path_depth: int,
) -> bool:
    """Detect banking brand tokens with sensitive endpoints in deep paths."""
    if domain in TRUSTED_DOMAINS:
        return False

    text = _path_and_query_text(url)
    full_url_text = url.lower()
    
    # Check for banking brand tokens
    brand_hits = [token for token in {"hsbc", "abn", "barclays", "citibank"} if token in text]
    if not brand_hits:
        return False
    
    # Check for sensitive banking endpoints
    endpoint_hits = [token for token in BANKING_ENDPOINT_KEYWORDS if token in text]
    if not endpoint_hits:
        return False
    
    # Require reasonable path depth
    return path_depth >= 2


def _should_override_short_php_endpoint(
    url: str,
    domain: str,
    domain_age_days: int,
) -> bool:
    """Detect suspicious short PHP filenames on new/unknown domains."""
    if domain in TRUSTED_DOMAINS:
        return False

    text = _path_and_query_text(url)
    
    # Check for short PHP endpoints (< 8 chars including extension)
    if ".php" not in text:
        return False
    
    # Extract just the PHP filename
    parts = text.split("/")
    php_files = [p for p in parts if ".php" in p]
    
    if not php_files:
        return False
    
    # Check if any PHP file is suspiciously short (like M5.php)
    short_php_files = [f for f in php_files if len(f) <= 8]
    
    if not short_php_files:
        return False
    
    # This is suspicious on new/unknown domains
    return domain_age_days < 0 or domain_age_days > 5475  # New or very old domain


def _should_override_embedded_domain_pattern(url: str, domain: str, path_depth: int) -> bool:
    """Detect embedded domain patterns in path (e.g., shopgreenmall.net/tomatodesign.net/...)."""
    if domain in TRUSTED_DOMAINS:
        return False

    path_text = urlparse(url).path.lower()
    
    # Count dots in the path part (embedded domain indicators)
    path_dots = path_text.count(".")
    
    # If path has multiple dots and is deep, suggests embedded domain
    if path_dots >= 2 and path_depth >= 4:
        # Check for suspicious patterns like brand names in path
        for brand in {"hsbc", "mybanklogin", "paypal", "amazon", "apple", "microsoft"}:
            if brand in path_text:
                return True
    
    return False


def _align_features_to_model(features: pd.DataFrame) -> pd.DataFrame:
    """Align runtime features to the locked schema used for the final submission model."""
    aligned = features.copy()

    for col in EXPECTED_FEATURE_COLUMNS:
        if col not in aligned.columns:
            aligned[col] = 0

    return aligned[EXPECTED_FEATURE_COLUMNS]


def _safe_int_feature(features: pd.DataFrame, column: str, default: int = 0) -> int:
    """Safely read an integer feature from extraction output with a fallback."""
    try:
        if column not in features.columns:
            return default
        value = features[column].iloc[0]
        if pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def predict_url_label(url: str) -> tuple[str, float, str]:
    model = _get_model()

    features = extract_features_from_urls(
        pd.Series([url]),
        whois_cache_path=WHOIS_CACHE_PATH,
        whois_timeout=1,
        whois_max_lookups=1,
        whois_max_errors=1,
        dns_timeout=0.2,
        dns_max_lookups=100,
        dns_max_errors=20,
    )

    aligned_features = _align_features_to_model(features)
    probabilities = model.predict_proba(aligned_features)[0]
    phishing_probability = float(probabilities[1])
    domain = _registered_domain(url).lower()

    suspicious_path_count = _safe_int_feature(features, "suspicious_path_keyword_count", 0)
    suspicious_keyword_count = _safe_int_feature(features, "suspicious_keyword_count", 0)
    has_wp_path = _safe_int_feature(features, "has_wp_path", 0)
    domain_age_days = _safe_int_feature(features, "domain_age_days", -1)
    dns_resolves = _safe_int_feature(features, "dns_resolves", 0)
    uses_ip_address = _safe_int_feature(features, "uses_ip_address", 0)
    has_suspicious_tld = _safe_int_feature(features, "has_suspicious_tld", 0)
    path_depth = _safe_int_feature(features, "path_depth", 0)
    num_subdomains = _safe_int_feature(features, "num_subdomains", 0)
    has_encoded_chars = _safe_int_feature(features, "has_encoded_chars", 0)

    if (suspicious_path_count >= 1 or has_wp_path == 1) and domain_age_days < 0 and dns_resolves == 0:
        return (
            "Phishing",
            max(phishing_probability, 0.90),
            "High-risk structural override applied: suspicious path pattern with unresolved and unknown domain metadata.",
        )

    if uses_ip_address == 1 and (suspicious_path_count >= 1 or suspicious_keyword_count >= 1):
        return (
            "Phishing",
            max(phishing_probability, 0.85),
            "IP-host + suspicious keyword override applied.",
        )

    if has_suspicious_tld == 1 and suspicious_keyword_count >= 1:
        return (
            "Phishing",
            max(phishing_probability, 0.80),
            "Suspicious-TLD + phishing keyword override applied.",
        )

    if _should_override_brand_mismatch(
        url=url,
        domain=domain,
        suspicious_keyword_count=suspicious_keyword_count,
        suspicious_path_count=suspicious_path_count,
        path_depth=path_depth,
        num_subdomains=num_subdomains,
        has_encoded_chars=has_encoded_chars,
    ):
        return (
            "Phishing",
            max(phishing_probability, 0.88),
            "Brand-impersonation path override applied (brand token mismatch with host/domain).",
        )

    if _should_override_mail_stack(url=url, domain=domain, path_depth=path_depth):
        return (
            "Phishing",
            max(phishing_probability, 0.84),
            "Mail-stack path override applied (zimbra/owa/exch-style phishing pattern).",
        )

    if _should_override_php_trap(
        url=url,
        domain=domain,
        suspicious_keyword_count=suspicious_keyword_count,
        suspicious_path_count=suspicious_path_count,
        path_depth=path_depth,
    ):
        return (
            "Phishing",
            max(phishing_probability, 0.82),
            "PHP trap-path override applied (high-risk endpoint structure).",
        )

    if _should_override_hosted_form(url=url, domain=domain):
        return (
            "Phishing",
            max(phishing_probability, 0.78),
            "Hosted-form phishing override applied (google-docs form impersonation pattern).",
        )

    if _should_override_wp_login(url=url, domain=domain, path_depth=path_depth):
        return (
            "Phishing",
            max(phishing_probability, 0.86),
            "WordPress admin/login override applied (WP-admin + login endpoint pattern detected).",
        )

    if _should_override_banking_brand_endpoint(
        url=url,
        domain=domain,
        path_depth=path_depth,
    ):
        return (
            "Phishing",
            max(phishing_probability, 0.87),
            "Banking-brand endpoint override applied (brand token + sensitive endpoint match).",
        )

    if _should_override_short_php_endpoint(
        url=url,
        domain=domain,
        domain_age_days=domain_age_days,
    ):
        return (
            "Phishing",
            max(phishing_probability, 0.85),
            "Short PHP endpoint override applied (suspicious minimal script on suspicious domain).",
        )

    if _should_override_embedded_domain_pattern(url=url, domain=domain, path_depth=path_depth):
        return (
            "Phishing",
            max(phishing_probability, 0.84),
            "Embedded-domain pattern override applied (domain structure mismatch detected).",
        )

    trusted_override_safe = (
        suspicious_keyword_count == 0
        and suspicious_path_count == 0
        and has_wp_path == 0
        and has_encoded_chars == 0
        and path_depth <= 1
        and num_subdomains <= 1
    )

    if domain in TRUSTED_DOMAINS and trusted_override_safe:
        return (
            "Legitimate",
            phishing_probability,
            f"Trusted-domain override applied for {domain}. Model phishing score was {phishing_probability:.4f}.",
        )

    if UNCERTAIN_LOWER_BOUND <= phishing_probability <= UNCERTAIN_UPPER_BOUND:
        return (
            "Uncertain",
            phishing_probability,
            (
                "Borderline decision region: phishing probability is near the model "
                f"boundary ({phishing_probability:.4f})."
            ),
        )

    label = "Phishing" if phishing_probability >= FINAL_THRESHOLD else "Legitimate"
    reason = f"Threshold decision at {FINAL_THRESHOLD:.6f}."
    return label, phishing_probability, reason


@app.route("/", methods=["GET"])
def home() -> str:
    model_info = MODEL_DISPLAY_NAME if _MODEL_PATH else f"{MODEL_DISPLAY_NAME} (loading...)"
    return render_template("home.html", model_info=model_info)


@app.route("/analyze", methods=["GET"])
def analyze() -> str:
    model_info = MODEL_DISPLAY_NAME if _MODEL_PATH else f"{MODEL_DISPLAY_NAME} (loading...)"
    return render_template("index.html", model_info=model_info)


@app.route("/scan-qr", methods=["GET"])
def scan_qr() -> str:
    model_info = MODEL_DISPLAY_NAME if _MODEL_PATH else f"{MODEL_DISPLAY_NAME} (loading...)"
    return render_template("qr_scan.html", model_info=model_info)


def _predict_and_render(raw_url: str, template_name: str) -> str:
    url = _normalize_input_url(raw_url)

    if not url:
        return render_template(
            template_name,
            error_text="Please enter a URL.",
            input_url=raw_url,
            model_info=MODEL_DISPLAY_NAME,
        )

    if not _is_probable_url(raw_url):
        return render_template(
            template_name,
            error_text="Please enter a full URL such as https://example.com.",
            input_url=raw_url,
            model_info=MODEL_DISPLAY_NAME,
        )

    try:
        detection = _run_hybrid_detection(url)
        label = str(detection["label"])
        phishing_probability = float(detection["phishing_score"])
        reason = str(detection["reason"])
        output = format_output(label, phishing_probability, reason)
        return render_template(
            template_name,
            result_badge=output["result_badge"],
            result_label=output["result_label"],
            result_confidence=output["result_confidence"],
            risk_level=output["risk_level"],
            explanation_text=output["explanation_text"],
            rule_trigger=output["rule_trigger"],
            recommendations=output["recommendations"],
            input_url=raw_url,
            model_info=MODEL_DISPLAY_NAME,
        )
    except Exception as exc:
        return render_template(
            template_name,
            error_text=f"Prediction failed: {exc}",
            input_url=raw_url,
            model_info=MODEL_DISPLAY_NAME,
        )


def _predict_to_payload(raw_url: str, source: str = "url") -> tuple[dict[str, Any], int]:
    """Return structured JSON payload for mobile/API clients."""
    raw_value = str(raw_url).strip()
    if not raw_value:
        return {"ok": False, "error": "Please provide a URL."}, 400

    if source != "qr" and not _is_probable_url(raw_value):
        return {
            "ok": False,
            "error": "Please enter a full URL such as https://example.com.",
        }, 400

    # Keep a single inference path for both URL input and QR payloads.
    # QR scans are normalized into a URL-shaped string before ensemble inference.
    url = _normalize_input_url(raw_value)
    if not url:
        return {"ok": False, "error": "Please provide a URL."}, 400

    try:
        started_at = time.perf_counter()
        detection = _run_hybrid_detection(url)
        inference_ms = (time.perf_counter() - started_at) * 1000.0
        label = str(detection["label"])
        phishing_probability = float(detection["phishing_score"])
        reason = str(detection["reason"])
        output = format_output(label, phishing_probability, reason)
        return (
            {
                "ok": True,
                "input_url": raw_value,
                "normalized_url": url,
                "result": {
                    "badge": output["result_badge"],
                    "label": output["result_label"],
                    "confidence": output["result_confidence"],
                    "phishing_score": round(phishing_probability, 6),
                    "model_phishing_score": round(
                        float(detection["model_phishing_score"]),
                        6,
                    ),
                    "fused_phishing_score": round(phishing_probability, 6),
                    "threshold": FINAL_THRESHOLD,
                    "risk_level": output["risk_level"],
                    "explanation": output["explanation_text"],
                    "rule_trigger": output["rule_trigger"],
                    "recommendations": output["recommendations"],
                    "threat_intel": detection["threat_intel"],
                    "fusion_applied": bool(detection["fusion_applied"]),
                },
                "inference_ms": round(inference_ms, 2),
                "model_inference_ms": detection["model_inference_ms"],
                "model": MODEL_DISPLAY_NAME,
            },
            200,
        )
    except Exception as exc:
        app.logger.error("Prediction failed for URL '%s': %s", url, exc)
        app.logger.debug(traceback.format_exc())
        return {"ok": False, "error": f"Prediction failed: {exc}"}, 500


@app.route("/predict", methods=["POST"])
def predict() -> str:
    raw_url = request.form.get("url", "").strip()
    return _predict_and_render(raw_url, "index.html")


@app.route("/predict-qr", methods=["POST"])
def predict_qr() -> str:
    raw_url = request.form.get("url", "").strip()
    return _predict_and_render(raw_url, "qr_scan.html")


@app.route("/api/health", methods=["GET"])
def api_health() -> Any:
    return jsonify({"ok": True, "service": "phish-guard", "model": MODEL_DISPLAY_NAME}), 200


@app.route("/api/predict", methods=["POST"])
def api_predict() -> Any:
    payload = request.get_json(silent=True) or {}
    raw_url = str(payload.get("url", "")).strip()
    source = str(payload.get("source", "url")).strip().lower()
    response, status_code = _predict_to_payload(raw_url, source=source)
    return jsonify(response), status_code


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=False, use_reloader=False, host="0.0.0.0", port=port)
