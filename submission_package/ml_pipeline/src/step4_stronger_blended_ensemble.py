"""Train a stronger but resource-friendly blended ensemble.

Usage:
    /usr/bin/python3 src/step4_stronger_blended_ensemble.py \
        --input data/url_features.csv \
        --output-dir artifacts/ensemble_stronger
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
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
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train stronger blended ensemble")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--target-column", type=str, default="is_phishing")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cv-folds", type=int, default=2)
    parser.add_argument("--optimize-beta", type=float, default=2.0)
    parser.add_argument("--min-precision", type=float, default=0.75)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=180000,
        help="Stratified cap on total rows for faster training in limited environments",
    )
    return parser.parse_args()


def build_base_models() -> list[tuple[str, object]]:
    return [
        (
            "rf",
            RandomForestClassifier(
                n_estimators=120,
                max_depth=18,
                min_samples_leaf=2,
                class_weight={0: 1.0, 1: 2.0},
                random_state=RANDOM_STATE,
                n_jobs=2,
            ),
        ),
        (
            "gb",
            GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.05,
                max_depth=3,
                random_state=RANDOM_STATE,
            ),
        ),
        (
            "xgb",
            XGBClassifier(
                n_estimators=220,
                learning_rate=0.05,
                max_depth=5,
                min_child_weight=1,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="binary:logistic",
                eval_metric="logloss",
                scale_pos_weight=2.0,
                random_state=RANDOM_STATE,
                n_jobs=2,
            ),
        ),
        (
            "et",
            ExtraTreesClassifier(
                n_estimators=120,
                max_depth=None,
                min_samples_leaf=1,
                class_weight={0: 1.0, 1: 1.8},
                random_state=RANDOM_STATE,
                n_jobs=2,
            ),
        ),
    ]


def _oof_probabilities(
    models: list[tuple[str, object]],
    X: pd.DataFrame,
    y: pd.Series,
    folds: int,
) -> list[np.ndarray]:
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    streams = [np.zeros(len(y), dtype=float) for _ in models]

    for train_idx, val_idx in splitter.split(X, y):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr = y.iloc[train_idx]

        for stream_idx, (_, model) in enumerate(models):
            fold_model = clone(model)
            fold_model.fit(X_tr, y_tr)
            streams[stream_idx][val_idx] = fold_model.predict_proba(X_val)[:, 1]

    return streams


def _weighted_probability(probs: list[np.ndarray], weights: list[float]) -> np.ndarray:
    total_weight = float(sum(weights))
    return sum(w * p for w, p in zip(weights, probs)) / total_weight


def _search_threshold(
    y_true: pd.Series,
    y_prob: np.ndarray,
    beta: float,
    min_precision: float,
) -> tuple[float, float]:
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    if len(thresholds) == 0:
        return 0.5, 0.0

    best_threshold = 0.5
    best_score = -1.0

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

    if best_score < 0:
        eps = 1e-12
        fbeta_scores = (1 + beta**2) * precisions[:-1] * recalls[:-1] / (
            beta**2 * precisions[:-1] + recalls[:-1] + eps
        )
        idx = int(np.nanargmax(fbeta_scores))
        best_threshold = float(thresholds[idx])
        best_score = float(fbeta_scores[idx])

    return best_threshold, best_score


def _search_best_weights_and_threshold(
    y_true: pd.Series,
    prob_streams: list[np.ndarray],
    beta: float,
    min_precision: float,
) -> tuple[list[float], float, float]:
    # Randomized but deterministic search to keep runtime bounded.
    rng = np.random.default_rng(RANDOM_STATE)
    candidates = rng.uniform(0.5, 4.0, size=(200, 4))

    best_weights = [1.0, 1.0, 1.0, 1.0]
    best_threshold = 0.5
    best_score = -1.0

    for row in candidates:
        weights = [float(x) for x in row]
        y_prob = _weighted_probability(prob_streams, weights)
        threshold, score = _search_threshold(y_true, y_prob, beta, min_precision)

        if score > best_score:
            best_score = score
            best_weights = weights
            best_threshold = threshold

    return best_weights, best_threshold, best_score


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


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)
    if args.target_column not in df.columns:
        raise ValueError(f"Missing target column: {args.target_column}")

    X = df.drop(columns=[args.target_column])
    y = df[args.target_column].astype(int)

    if args.max_rows > 0 and len(df) > args.max_rows:
        frac = float(args.max_rows) / float(len(df))
        sampled = df.groupby(args.target_column, group_keys=False).sample(
            frac=frac,
            random_state=RANDOM_STATE,
        )
        sampled = sampled.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)
        X = sampled.drop(columns=[args.target_column])
        y = sampled[args.target_column].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    base_models = build_base_models()
    oof_probs = _oof_probabilities(base_models, X_train, y_train, folds=args.cv_folds)

    best_weights, threshold, tuning_score = _search_best_weights_and_threshold(
        y_train,
        oof_probs,
        beta=args.optimize_beta,
        min_precision=args.min_precision,
    )

    ensemble = VotingClassifier(
        estimators=[(name, model) for name, model in base_models],
        voting="soft",
        weights=best_weights,
        n_jobs=1,
    )
    ensemble.fit(X_train, y_train)

    y_test_prob = ensemble.predict_proba(X_test)[:, 1]
    test_metrics = _evaluate(y_test, y_test_prob, threshold)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "stronger_blended_ensemble.joblib"
    threshold_path = args.output_dir / "stronger_blended_threshold.txt"
    metrics_path = args.output_dir / "stronger_blended_metrics.csv"

    joblib.dump(ensemble, model_path)
    threshold_path.write_text(f"{threshold:.6f}\n", encoding="utf-8")

    metrics = {
        "tuning_fbeta": float(tuning_score),
        "weight_rf": float(best_weights[0]),
        "weight_gb": float(best_weights[1]),
        "weight_xgb": float(best_weights[2]),
        "weight_et": float(best_weights[3]),
        **test_metrics,
    }
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)

    print("Stronger blended ensemble training complete")
    print(pd.DataFrame([metrics]).to_string(index=False))
    print(f"Saved model to {model_path}")
    print(f"Saved threshold to {threshold_path}")
    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
