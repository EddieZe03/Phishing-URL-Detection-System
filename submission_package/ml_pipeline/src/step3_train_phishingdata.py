"""Train models directly on PhishingData-style tabular features.

This path is useful for benchmarking with precomputed phishing features.
It is separate from the raw-URL pipeline used by the browser/mobile inference demo.

Usage:
    python src/step3_train_phishingdata.py \
      --input data/PhishingData.csv \
      --output-dir artifacts/phishingdata_models
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_recall_curve, precision_score, recall_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

RANDOM_STATE = 42


def _normalize_col(col: str) -> str:
    c = col.strip()
    c = re.sub(r"\s+", "_", c)
    c = re.sub(r"[^A-Za-z0-9_]+", "", c)
    return c.lower()


def _find_label_column(columns: list[str]) -> str:
    candidates = ["result", "label", "class", "target"]
    for c in candidates:
        if c in columns:
            return c
    raise ValueError("Could not find label column. Expected one of: result, label, class, target")


def _to_binary_label(y: pd.Series) -> pd.Series:
    y_num = pd.to_numeric(y, errors="coerce").fillna(0)

    # Common encodings: {1,-1}, {1,0}
    unique = set(y_num.unique().tolist())
    if unique.issubset({-1, 1}):
        return (y_num == 1).astype(int)

    return (y_num > 0).astype(int)


def _best_threshold(y_true: pd.Series, y_prob: np.ndarray, beta: float) -> float:
    p, r, t = precision_recall_curve(y_true, y_prob)
    if len(t) == 0:
        return 0.5

    eps = 1e-12
    fbeta = (1 + beta**2) * p[:-1] * r[:-1] / (beta**2 * p[:-1] + r[:-1] + eps)
    idx = int(np.nanargmax(fbeta))
    return float(t[idx])


def _evaluate(y_true: pd.Series, y_prob: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "threshold": float(threshold),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train models on PhishingData tabular dataset")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--optimize-beta", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)
    df.columns = [_normalize_col(c) for c in df.columns]

    label_col = _find_label_column(df.columns.tolist())

    drop_cols = [c for c in ["index", "url"] if c in df.columns]
    X = df.drop(columns=drop_cols + [label_col]).apply(pd.to_numeric, errors="coerce").fillna(0)
    y = _to_binary_label(df[label_col])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            class_weight={0: 1.0, 1: 1.5},
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "xgboost": XGBClassifier(
            n_estimators=400,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=1.5,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | str]] = []
    trained: dict[str, object] = {}

    for name, model in models.items():
        model.fit(X_train, y_train)
        trained[name] = model
        prob = model.predict_proba(X_test)[:, 1]
        threshold = _best_threshold(y_test, prob, beta=args.optimize_beta)
        metrics = _evaluate(y_test, prob, threshold)
        rows.append({"model": name, **metrics})

        joblib.dump(model, args.output_dir / f"{name}.joblib")
        (args.output_dir / f"{name}_threshold.txt").write_text(f"{threshold:.6f}\n", encoding="utf-8")

    ensemble = VotingClassifier(
        estimators=[("rf", trained["random_forest"]), ("gb", trained["gradient_boosting"]), ("xgb", trained["xgboost"])],
        voting="soft",
    )
    ensemble.fit(X_train, y_train)
    ensemble_prob = ensemble.predict_proba(X_test)[:, 1]
    ensemble_threshold = _best_threshold(y_test, ensemble_prob, beta=args.optimize_beta)
    ensemble_metrics = _evaluate(y_test, ensemble_prob, ensemble_threshold)
    rows.append({"model": "ensemble", **ensemble_metrics})

    joblib.dump(ensemble, args.output_dir / "ensemble.joblib")
    (args.output_dir / "ensemble_threshold.txt").write_text(f"{ensemble_threshold:.6f}\n", encoding="utf-8")

    metrics_df = pd.DataFrame(rows)
    metrics_path = args.output_dir / "metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    # Save feature schema to avoid mismatch in future inference.
    (args.output_dir / "feature_columns.txt").write_text("\n".join(X.columns.tolist()) + "\n", encoding="utf-8")

    print("PhishingData training metrics:")
    print(metrics_df.to_string(index=False))
    print(f"Saved artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
