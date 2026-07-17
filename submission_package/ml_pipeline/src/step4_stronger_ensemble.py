"""Train a stronger phishing ensemble using stacked learning.

Usage:
    /usr/bin/python3 src/step4_stronger_ensemble.py \
        --input data/url_features.csv \
        --output-dir artifacts/ensemble_stronger
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train stacked ensemble for phishing URL detection"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--target-column", type=str, default="is_phishing")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--optimize-beta",
        type=float,
        default=2.0,
        help="Beta for F-beta threshold search (beta>1 favors recall)",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=0.75,
        help="Minimum precision constraint during threshold search",
    )
    return parser.parse_args()


def _search_threshold(
    y_true: pd.Series,
    y_prob: np.ndarray,
    beta: float,
    min_precision: float,
) -> tuple[float, float, float]:
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    if len(thresholds) == 0:
        return 0.5, 0.0, 0.0

    best_threshold = 0.5
    best_score = -1.0
    best_precision = 0.0

    for idx, threshold in enumerate(thresholds):
        precision = float(precisions[idx])
        recall = float(recalls[idx])

        if precision < min_precision:
            continue

        denom = beta**2 * precision + recall
        score = 0.0 if denom <= 0 else (1 + beta**2) * precision * recall / denom
        if score > best_score:
            best_score = score
            best_threshold = float(threshold)
            best_precision = precision

    # If no threshold satisfies the precision floor, fall back to best F-beta.
    if best_score < 0:
        eps = 1e-12
        fbeta_scores = (1 + beta**2) * precisions[:-1] * recalls[:-1] / (
            beta**2 * precisions[:-1] + recalls[:-1] + eps
        )
        idx = int(np.nanargmax(fbeta_scores))
        best_threshold = float(thresholds[idx])
        best_score = float(fbeta_scores[idx])
        best_precision = float(precisions[idx])

    return best_threshold, best_score, best_precision


def _evaluate(y_true: pd.Series, y_prob: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, y_pred, beta=2.0, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
        "fpr": float(fpr),
        "fnr": float(fnr),
        "threshold": float(threshold),
    }


def build_stacked_model() -> StackingClassifier:
    base_estimators = [
        (
            "rf",
            RandomForestClassifier(
                n_estimators=180,
                max_depth=20,
                min_samples_leaf=1,
                class_weight={0: 1.0, 1: 2.0},
                random_state=RANDOM_STATE,
                n_jobs=2,
            ),
        ),
        (
            "gb",
            GradientBoostingClassifier(
                random_state=RANDOM_STATE,
                n_estimators=250,
                learning_rate=0.05,
                max_depth=3,
            ),
        ),
        (
            "xgb",
            XGBClassifier(
                n_estimators=400,
                learning_rate=0.05,
                max_depth=7,
                min_child_weight=1,
                subsample=0.85,
                colsample_bytree=0.85,
                reg_alpha=0.1,
                reg_lambda=1.2,
                objective="binary:logistic",
                eval_metric="logloss",
                scale_pos_weight=2.0,
                random_state=RANDOM_STATE,
                n_jobs=2,
            ),
        ),
        (
            "extra_trees",
            ExtraTreesClassifier(
                n_estimators=200,
                max_depth=None,
                min_samples_leaf=1,
                class_weight={0: 1.0, 1: 1.8},
                random_state=RANDOM_STATE,
                n_jobs=2,
            ),
        ),
    ]

    meta_learner = LogisticRegression(
        class_weight={0: 1.0, 1: 1.6},
        max_iter=3000,
        random_state=RANDOM_STATE,
    )

    return StackingClassifier(
        estimators=base_estimators,
        final_estimator=meta_learner,
        cv=3,
        passthrough=True,
        stack_method="predict_proba",
        n_jobs=1,
    )


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)
    if args.target_column not in df.columns:
        raise ValueError(f"Missing target column: {args.target_column}")

    X = df.drop(columns=[args.target_column])
    y = df[args.target_column].astype(int)

    # Three-way split avoids tuning threshold on test data.
    X_train, X_temp, y_train, y_temp = train_test_split(
        X,
        y,
        test_size=0.30,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp,
        y_temp,
        test_size=0.50,
        random_state=RANDOM_STATE,
        stratify=y_temp,
    )

    model = build_stacked_model()
    model.fit(X_train, y_train)

    y_val_prob = model.predict_proba(X_val)[:, 1]
    threshold, tuning_score, tuning_precision = _search_threshold(
        y_val,
        y_val_prob,
        beta=args.optimize_beta,
        min_precision=args.min_precision,
    )

    val_metrics = _evaluate(y_val, y_val_prob, threshold)
    y_test_prob = model.predict_proba(X_test)[:, 1]
    test_metrics = _evaluate(y_test, y_test_prob, threshold)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "stacked_ensemble.joblib"
    threshold_path = args.output_dir / "stacked_threshold.txt"
    metrics_path = args.output_dir / "stacked_metrics.csv"

    joblib.dump(model, model_path)
    threshold_path.write_text(f"{threshold:.6f}\n", encoding="utf-8")

    metrics_df = pd.DataFrame(
        [
            {
                "split": "validation",
                "tuning_fbeta": float(tuning_score),
                "tuning_precision": float(tuning_precision),
                **val_metrics,
            },
            {
                "split": "test",
                "tuning_fbeta": float(tuning_score),
                "tuning_precision": float(tuning_precision),
                **test_metrics,
            },
        ]
    )
    metrics_df.to_csv(metrics_path, index=False)

    print("Stacked ensemble training complete")
    print(metrics_df.to_string(index=False))
    print(f"Saved model to {model_path}")
    print(f"Saved threshold to {threshold_path}")
    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
