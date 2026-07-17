"""Step 4: Train and evaluate soft voting ensemble, then save model.

Usage:
    python src/step4_ensemble_model.py \
        --input data/url_features.csv \
        --model-output artifacts/ensemble/soft_voting_ensemble.joblib
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    fbeta_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 4 soft voting ensemble for phishing URL detection"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--target-column", type=str, default="is_phishing")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=5,
        help="Stratified CV folds for out-of-fold blend/threshold tuning",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=200000,
        help="Maximum rows to use for Step 4. Use a balanced stratified sample when the input is larger.",
    )
    parser.add_argument(
        "--no-sampling",
        action="store_true",
        help="Disable row capping and train on the full dataset.",
    )
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument(
        "--optimize-beta",
        type=float,
        default=2.0,
        help="Beta for F-beta threshold optimization (beta>1 favors recall)",
    )
    parser.add_argument(
        "--tuning-metric",
        choices=["accuracy", "fbeta"],
        default="accuracy",
        help="Objective for blend and threshold search",
    )
    return parser.parse_args()


def _balanced_sample(df: pd.DataFrame, target_column: str, max_rows: int) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df

    sample_size = max_rows // 2
    positives = df[df[target_column] == 1]
    negatives = df[df[target_column] == 0]

    if len(positives) == 0 or len(negatives) == 0:
        return df.sample(n=max_rows, random_state=RANDOM_STATE)

    pos_n = min(len(positives), sample_size)
    neg_n = min(len(negatives), sample_size)

    sampled = pd.concat(
        [
            positives.sample(n=pos_n, random_state=RANDOM_STATE),
            negatives.sample(n=neg_n, random_state=RANDOM_STATE),
        ]
    )

    if len(sampled) < max_rows:
        remaining = max_rows - len(sampled)
        remainder = df.drop(sampled.index, errors="ignore")
        if len(remainder) > 0:
            sampled = pd.concat(
                [
                    sampled,
                    remainder.sample(
                        n=min(remaining, len(remainder)), random_state=RANDOM_STATE
                    ),
                ]
            )

    return sampled.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)


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


def _weighted_probability(probs: list[np.ndarray], weights: list[float]) -> np.ndarray:
    total_weight = float(sum(weights))
    if total_weight <= 0:
        raise ValueError("Weights must sum to a positive value.")
    blended = sum(w * p for w, p in zip(weights, probs)) / total_weight
    return blended


def _search_best_weights_and_threshold(
    y_true: pd.Series,
    prob_streams: list[np.ndarray],
    beta: float,
    tuning_metric: str,
) -> tuple[list[float], float, float]:
    # Small deterministic grid keeps runtime manageable while improving blend quality.
    candidate_values = [1.0, 2.0, 3.0, 4.0]
    best_weights = [1.0, 1.0, 1.0]
    best_threshold = 0.5
    best_score = -1.0

    for w_rf in candidate_values:
        for w_gb in candidate_values:
            for w_xgb in candidate_values:
                weights = [w_rf, w_gb, w_xgb]
                y_prob = _weighted_probability(prob_streams, weights)
                if tuning_metric == "accuracy":
                    threshold_candidates = np.linspace(0.05, 0.95, 181)
                    best_local_threshold = 0.5
                    best_local_score = -1.0
                    for t in threshold_candidates:
                        y_pred_local = (y_prob >= t).astype(int)
                        score_local = float(accuracy_score(y_true, y_pred_local))
                        if score_local > best_local_score:
                            best_local_score = score_local
                            best_local_threshold = float(t)
                    threshold = best_local_threshold
                else:
                    threshold = _best_threshold(y_true, y_prob, beta=beta)

                y_pred = (y_prob >= threshold).astype(int)
                if tuning_metric == "accuracy":
                    score = float(accuracy_score(y_true, y_pred))
                else:
                    score = float(fbeta_score(y_true, y_pred, beta=beta, zero_division=0))
                if score > best_score:
                    best_score = score
                    best_weights = weights
                    best_threshold = threshold

    return best_weights, float(best_threshold), float(best_score)


def _oof_probabilities(
    models: list,
    X: pd.DataFrame,
    y: pd.Series,
    folds: int,
) -> list[np.ndarray]:
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    streams = [np.zeros(len(y), dtype=float) for _ in models]

    for train_idx, val_idx in splitter.split(X, y):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr = y.iloc[train_idx]

        for stream_idx, model in enumerate(models):
            fold_model = clone(model)
            fold_model.fit(X_tr, y_tr)
            streams[stream_idx][val_idx] = fold_model.predict_proba(X_val)[:, 1]

    return streams


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)
    if args.target_column not in df.columns:
        raise ValueError(f"Missing target column: {args.target_column}")

    if not args.no_sampling and len(df) > args.max_rows:
        df = _balanced_sample(df, args.target_column, args.max_rows)
        print(f"Using balanced sample of {len(df)} rows for Step 4 training.")
    else:
        print(f"Using full dataset of {len(df)} rows for Step 4 training.")

    X = df.drop(columns=[args.target_column])
    y = df[args.target_column].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    rf_model = RandomForestClassifier(
        n_estimators=140,
        max_depth=20,
        min_samples_leaf=2,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        class_weight={0: 1.0, 1: 1.8},
    )
    gb_model = GradientBoostingClassifier(random_state=RANDOM_STATE)
    xgb_model = XGBClassifier(
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
    )

    # Tune blend weights/threshold from out-of-fold probabilities without using test data.
    base_models = [rf_model, gb_model, xgb_model]
    oof_probs = _oof_probabilities(base_models, X_train, y_train, folds=args.cv_folds)
    best_weights, threshold, best_tuning_score = _search_best_weights_and_threshold(
        y_train,
        oof_probs,
        beta=args.optimize_beta,
        tuning_metric=args.tuning_metric,
    )

    # Fit the final weighted ensemble on full training split.
    ensemble_model = VotingClassifier(
        estimators=[("rf", rf_model), ("gb", gb_model), ("xgb", xgb_model)],
        voting="soft",
        weights=best_weights,
    )

    ensemble_model.fit(X_train, y_train)
    y_prob = ensemble_model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
    false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "tuning_metric": args.tuning_metric,
        "tuning_score": float(best_tuning_score),
        "weight_rf": float(best_weights[0]),
        "weight_gb": float(best_weights[1]),
        "weight_xgb": float(best_weights[2]),
        "threshold": float(threshold),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
        "fpr": float(false_positive_rate),
        "fnr": float(false_negative_rate),
    }

    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(ensemble_model, args.model_output)

    metrics_path = args.model_output.parent / "ensemble_metrics.csv"
    error_path = args.model_output.parent / "ensemble_error_analysis.csv"
    threshold_path = args.model_output.parent / "ensemble_threshold.txt"

    metrics_df = pd.DataFrame([metrics])
    metrics_df[
        [
            "accuracy",
            "precision",
            "recall",
            "f1",
            "tuning_metric",
            "tuning_score",
            "weight_rf",
            "weight_gb",
            "weight_xgb",
            "threshold",
        ]
    ].to_csv(
        metrics_path, index=False
    )
    metrics_df[["tn", "fp", "fn", "tp", "fpr", "fnr"]].to_csv(error_path, index=False)
    threshold_path.write_text(f"{threshold:.6f}\n", encoding="utf-8")

    print("Soft voting ensemble metrics:")
    print(
        metrics_df[
            [
                "accuracy",
                "precision",
                "recall",
                "f1",
                "tuning_metric",
                "tuning_score",
                "weight_rf",
                "weight_gb",
                "weight_xgb",
                "threshold",
            ]
        ].to_string(index=False)
    )
    print(f"Saved ensemble model to {args.model_output}")
    print(f"Saved ensemble metrics to {metrics_path}")
    print(f"Saved ensemble error analysis to {error_path}")
    print(f"Saved ensemble threshold to {threshold_path}")


if __name__ == "__main__":
    main()
