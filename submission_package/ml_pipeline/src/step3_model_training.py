"""Step 3: Train individual ensemble models and evaluate baseline performance.

Usage:
    python src/step3_model_training.py \
        --input data/url_features.csv \
        --output-dir artifacts/base_models
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

import joblib

RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 3 model training for phishing URL detection"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--target-column", type=str, default="is_phishing")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--optimize-beta",
        type=float,
        default=2.0,
        help="Beta for F-beta threshold optimization (beta>1 favors recall)",
    )
    return parser.parse_args()


def _best_threshold(y_true: pd.Series, y_prob: np.ndarray, beta: float) -> float:
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    if len(thresholds) == 0:
        return 0.5

    eps = 1e-12
    fbeta = (1 + beta**2) * precisions[:-1] * recalls[:-1] / (
        beta**2 * precisions[:-1] + recalls[:-1] + eps
    )
    idx = int(np.nanargmax(fbeta))
    return float(thresholds[idx])


def evaluate_predictions(
    y_true: pd.Series, y_prob: np.ndarray, threshold: float
) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    # These rates support report analysis for phishing risk (missed attacks vs false alarms).
    false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "threshold": float(threshold),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
        "fpr": float(false_positive_rate),
        "fnr": float(false_negative_rate),
    }


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)
    if args.target_column not in df.columns:
        raise ValueError(f"Missing target column: {args.target_column}")

    X = df.drop(columns=[args.target_column])
    y = df[args.target_column].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=140,
            max_depth=20,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            class_weight={0: 1.0, 1: 1.8},
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "xgboost": XGBClassifier(
            n_estimators=450,
            learning_rate=0.05,
            max_depth=6,
            min_child_weight=1,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=1.8,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | str]] = []

    for model_name, model in models.items():
        model.fit(X_train, y_train)
        y_prob = model.predict_proba(X_test)[:, 1]
        threshold = _best_threshold(y_test, y_prob, beta=args.optimize_beta)

        metrics = evaluate_predictions(y_test, y_prob, threshold=threshold)
        rows.append({"model": model_name, **metrics})

        model_path = args.output_dir / f"{model_name}.joblib"
        joblib.dump(model, model_path)
        threshold_path = args.output_dir / f"{model_name}_threshold.txt"
        threshold_path.write_text(f"{threshold:.6f}\n", encoding="utf-8")

    metrics_df = pd.DataFrame(rows)
    primary_metrics = metrics_df[
        ["model", "accuracy", "precision", "recall", "f1", "threshold"]
    ]
    error_analysis = metrics_df[["model", "tn", "fp", "fn", "tp", "fpr", "fnr"]]

    metrics_path = args.output_dir / "baseline_metrics.csv"
    errors_path = args.output_dir / "baseline_error_analysis.csv"

    primary_metrics.to_csv(metrics_path, index=False)
    error_analysis.to_csv(errors_path, index=False)

    print("Baseline model metrics:")
    print(primary_metrics.to_string(index=False))
    print(f"Saved metrics to {metrics_path}")
    print(f"Saved error analysis to {errors_path}")


if __name__ == "__main__":
    main()
