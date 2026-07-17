#!/usr/bin/env python3
"""Benchmark model-only vs hybrid (model + threat-intel fusion) detection quality.

Outputs:
- artifacts/results/hybrid_ablation_predictions.csv
- artifacts/results/hybrid_ablation_metrics.json
"""

from __future__ import annotations

import csv
import json
import os
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Deterministic defaults. Can be overridden by CLI flags below.
os.environ.setdefault("THREAT_INTEL_ENABLED", "true")
os.environ.setdefault("THREAT_INTEL_URLHAUS_ENABLED", "true")
os.environ.setdefault("THREAT_INTEL_TIMEOUT_SEC", "2.0")
os.environ.setdefault("THREAT_INTEL_CACHE_TTL_SEC", "21600")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import _normalize_input_url, _run_hybrid_detection, predict_url_label  # noqa: E402


@dataclass(frozen=True)
class TestCase:
    url: str
    expected_label: str  # "Phishing" or "Legitimate"
    category: str


TEST_CASES: list[TestCase] = [
    TestCase("https://www.google.com", "Legitimate", "popular_legitimate"),
    TestCase("https://github.com", "Legitimate", "popular_legitimate"),
    TestCase("https://www.youtube.com", "Legitimate", "popular_legitimate"),
    TestCase("https://www.wikipedia.org", "Legitimate", "popular_legitimate"),
    TestCase("https://www.amazon.com", "Legitimate", "popular_legitimate"),
    TestCase("https://www.microsoft.com", "Legitimate", "popular_legitimate"),
    TestCase("https://www.linkedin.com", "Legitimate", "popular_legitimate"),
    TestCase("https://www.apple.com", "Legitimate", "popular_legitimate"),
    TestCase("https://www.paypal.com", "Legitimate", "banking_legitimate"),
    TestCase("https://www.chase.com", "Legitimate", "banking_legitimate"),
    TestCase("https://www.bankofamerica.com", "Legitimate", "banking_legitimate"),
    TestCase("https://www.wellsfargo.com", "Legitimate", "banking_legitimate"),
    TestCase("https://www.harvard.edu", "Legitimate", "education_legitimate"),
    TestCase("https://www.stanford.edu", "Legitimate", "education_legitimate"),
    TestCase("https://www.mit.edu", "Legitimate", "education_legitimate"),
    TestCase("http://192.168.1.1/login", "Phishing", "ip_phishing"),
    TestCase("http://123.45.67.89/secure", "Phishing", "ip_phishing"),
    TestCase("https://10.0.0.1/banking", "Phishing", "ip_phishing"),
    TestCase("https://www.g00gle.com/signin", "Phishing", "typosquat_phishing"),
    TestCase("https://www.paypa1.com/login", "Phishing", "typosquat_phishing"),
    TestCase("https://paypal.com-secure.verify-account.com", "Phishing", "subdomain_trick"),
    TestCase("https://www.google.com.malicious-site.com/login", "Phishing", "subdomain_trick"),
    TestCase("https://account-amazon.com.phishing.net", "Phishing", "subdomain_trick"),
    TestCase("https://bit.ly.secure-login.xyz/verify?id=12345", "Phishing", "obfuscated_phishing"),
    TestCase("http://urgentverification-paypal-account-suspended.com", "Phishing", "obfuscated_phishing"),
    TestCase("https://paypal.com@malicious.com", "Phishing", "at_symbol_trick"),
    TestCase("https://amazon.com@phishing.net/login", "Phishing", "at_symbol_trick"),
    TestCase("https://secure-banking.tk", "Phishing", "suspicious_tld"),
    TestCase("https://paypal-verify.cf", "Phishing", "suspicious_tld"),
    TestCase("https://account-recovery.ml", "Phishing", "suspicious_tld"),
]


def _safe_label(label: str) -> str:
    normalized = (label or "").strip().lower()
    if normalized == "phishing":
        return "Phishing"
    if normalized == "legitimate":
        return "Legitimate"
    return "Uncertain"


def _compute_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, float | int]:
    tp = fp = tn = fn = 0
    uncertain = 0

    for row in rows:
        expected = row["expected_label"]
        predicted = row[key]

        if predicted == "Uncertain":
            uncertain += 1

        predicted_is_phishing = predicted == "Phishing"
        expected_is_phishing = expected == "Phishing"

        if predicted_is_phishing and expected_is_phishing:
            tp += 1
        elif predicted_is_phishing and not expected_is_phishing:
            fp += 1
        elif (not predicted_is_phishing) and (not expected_is_phishing):
            tn += 1
        else:
            fn += 1

    total = len(rows)
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0

    return {
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "uncertain": uncertain,
        "accuracy": round(accuracy, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "fpr": round(fpr, 6),
        "fnr": round(fnr, 6),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark model-only vs hybrid phishing detection.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Run only first N test cases (0 = all).",
    )
    parser.add_argument(
        "--no-intel",
        action="store_true",
        help="Disable threat-intel lookups for a fast model-only benchmark pass.",
    )
    parser.add_argument(
        "--intel-timeout",
        type=float,
        default=None,
        help="Override threat-intel timeout seconds.",
    )
    return parser.parse_args()


def run_benchmark(limit: int = 0) -> None:
    rows: list[dict[str, Any]] = []
    cases = TEST_CASES if limit <= 0 else TEST_CASES[:limit]

    print(f"Running benchmark on {len(cases)} test cases...")

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.url}")
        normalized_url = _normalize_input_url(case.url)

        model_label, model_score, model_reason = predict_url_label(normalized_url)
        model_label = _safe_label(model_label)

        hybrid = _run_hybrid_detection(normalized_url)
        hybrid_label = _safe_label(str(hybrid["label"]))

        intel = hybrid.get("threat_intel", {}) if isinstance(hybrid, dict) else {}

        rows.append(
            {
                "category": case.category,
                "url": case.url,
                "expected_label": case.expected_label,
                "model_label": model_label,
                "model_score": round(float(model_score), 6),
                "hybrid_label": hybrid_label,
                "hybrid_score": round(float(hybrid["phishing_score"]), 6),
                "fusion_applied": bool(hybrid.get("fusion_applied", False)),
                "intel_provider": str(intel.get("provider", "")),
                "intel_verdict": str(intel.get("verdict", "")),
                "intel_malicious": bool(intel.get("malicious", False)),
                "intel_cache_hit": bool(intel.get("cache_hit", False)),
                "intel_latency_ms": round(float(intel.get("latency_ms", 0.0)), 2),
                "model_reason": model_reason,
                "hybrid_reason": str(hybrid.get("reason", "")),
            }
        )

    model_metrics = _compute_metrics(rows, "model_label")
    hybrid_metrics = _compute_metrics(rows, "hybrid_label")

    delta = {
        "accuracy_delta": round(hybrid_metrics["accuracy"] - model_metrics["accuracy"], 6),
        "recall_delta": round(hybrid_metrics["recall"] - model_metrics["recall"], 6),
        "fpr_delta": round(hybrid_metrics["fpr"] - model_metrics["fpr"], 6),
        "fnr_delta": round(hybrid_metrics["fnr"] - model_metrics["fnr"], 6),
    }

    output_dir = Path("artifacts") / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "hybrid_ablation_predictions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "test_cases": len(rows),
        "model_only": model_metrics,
        "hybrid": hybrid_metrics,
        "delta": delta,
    }

    json_path = output_dir / "hybrid_ablation_metrics.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Hybrid ablation benchmark completed")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    args = _parse_args()

    if args.no_intel:
        os.environ["THREAT_INTEL_ENABLED"] = "false"

    if args.intel_timeout is not None:
        os.environ["THREAT_INTEL_TIMEOUT_SEC"] = str(args.intel_timeout)

    run_benchmark(limit=args.limit)
