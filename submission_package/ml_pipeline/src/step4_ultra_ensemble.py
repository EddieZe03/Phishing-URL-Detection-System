"""Step 4 Ultra: Advanced stacked ensemble with calibration and hybrid optimization.

Uses LightGBM, CatBoost, XGBoost, RandomForest with stacking and probability calibration.

Usage:
    /usr/bin/python3 src/step4_ultra_ensemble.py \
        --input data/url_features_enhanced.csv \
        --output-dir artifacts/ensemble_ultra
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
)
from sklearn.calibration import CalibratedClassifierCV
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
    roc_curve,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.exceptions import InvalidParameterError

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("⚠ LightGBM not available; will use alternatives")

try:
    from catboost import CatBoostClassifier
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    print("⚠ CatBoost not available; will use alternatives")


RANDOM_STATE = 42


class ManualCalibratedModel:
    """Simple wrapper to apply a fitted 1-D calibrator to base estimator probabilities.

    This keeps a picklable object for saving with `joblib.dump`.
    """

    def __init__(self, base_estimator, calibrator, method: str):
        self.base_estimator = base_estimator
        self.calibrator = calibrator
        self.method = method

    def predict_proba(self, X):
        p = self.base_estimator.predict_proba(X)[:, 1]
        if self.method == "sigmoid":
            p_cal = self.calibrator.predict_proba(p.reshape(-1, 1))[:, 1]
        else:
            p_cal = self.calibrator.transform(p)
        return np.vstack([1 - p_cal, p_cal]).T


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 4 Ultra: Advanced stacked ensemble with calibration"
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
        default=0.72,
        help="Minimum precision constraint during threshold search",
    )
    parser.add_argument(
        "--calibration-method",
        choices=["sigmoid", "isotonic"],
        default="isotonic",
        help="Probability calibration method",
    )
    parser.add_argument(
        "--calibration-folds",
        type=int,
        default=5,
        help="Cross-validation folds for calibration",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=200000,
        help="Maximum rows to use for training; dataset will be stratified-sampled if larger",
    )
    parser.add_argument(
        "--no-sampling",
        action="store_true",
        help="Disable automatic downsampling even if dataset is large",
    )
    parser.add_argument(
        "--lightweight",
        action="store_true",
        help="Use lightweight model sizes and single-threaded learners for low-resource training",
    )
    return parser.parse_args()


def _search_optimal_threshold(
    y_true: pd.Series,
    y_prob: np.ndarray,
    beta: float,
    min_precision: float,
) -> tuple[float, float, float]:
    """Find optimal threshold balancing precision, recall, and F-beta."""
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


def _youden_index_threshold(
    y_true: pd.Series, y_prob: np.ndarray
) -> float:
    """Find threshold maximizing Youden's J statistic (sensitivity + specificity - 1)."""
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    j_scores = tpr - fpr
    idx = np.argmax(j_scores)
    return float(thresholds[idx])


def _evaluate(y_true: pd.Series, y_prob: np.ndarray, threshold: float) -> dict[str, float]:
    """Comprehensive evaluation at a given threshold."""
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, y_pred, beta=2.0, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "specificity": specificity,
        "sensitivity": sensitivity,
        "fpr": fpr,
        "fnr": fnr,
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
        "threshold": float(threshold),
    }


def build_ultra_ensemble(lightweight: bool = False) -> StackingClassifier:
    """Build an advanced stacked ensemble with multiple strong learners.

    If `lightweight` is True, use smaller learner sizes and single-threaded execution
    to reduce memory/CPU usage for constrained environments.
    """
    if lightweight:
        rf_n = 80
        gb_n = 100
        xgb_n = 150
        et_n = 100
        n_jobs_setting = 1
    else:
        rf_n = 200
        gb_n = 300
        xgb_n = 450
        et_n = 220
        n_jobs_setting = -1

    base_estimators = [
        (
            "rf",
            RandomForestClassifier(
                n_estimators=rf_n,
                max_depth=22,
                min_samples_leaf=1,
                min_samples_split=2,
                class_weight={0: 1.0, 1: 2.0},
                random_state=RANDOM_STATE,
                n_jobs=n_jobs_setting,
                verbose=0,
            ),
        ),
        (
            "gb",
            GradientBoostingClassifier(
                n_estimators=gb_n,
                learning_rate=0.05,
                max_depth=4,
                min_samples_leaf=1,
                subsample=0.85,
                random_state=RANDOM_STATE,
                verbose=0,
            ),
        ),
        (
            "xgb",
            XGBClassifier(
                n_estimators=xgb_n,
                learning_rate=0.05,
                max_depth=7,
                min_child_weight=1,
                subsample=0.87,
                colsample_bytree=0.87,
                reg_alpha=0.1,
                reg_lambda=1.0,
                objective="binary:logistic",
                eval_metric="logloss",
                scale_pos_weight=2.0,
                random_state=RANDOM_STATE,
                n_jobs=n_jobs_setting,
                verbosity=0,
            ),
        ),
        (
            "extra_trees",
            ExtraTreesClassifier(
                n_estimators=et_n,
                max_depth=24,
                min_samples_leaf=1,
                min_samples_split=2,
                class_weight={0: 1.0, 1: 1.8},
                random_state=RANDOM_STATE,
                n_jobs=n_jobs_setting,
                verbose=0,
            ),
        ),
    ]

    # Add LightGBM if available
    if LIGHTGBM_AVAILABLE:
        base_estimators.append(
            (
                "lgb",
                lgb.LGBMClassifier(
                    n_estimators=(150 if lightweight else 400),
                    learning_rate=0.05,
                    max_depth=7,
                    num_leaves=31,
                    min_child_samples=1,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    scale_pos_weight=2.0,
                    objective="binary",
                    metric="auc",
                    random_state=RANDOM_STATE,
                    n_jobs=n_jobs_setting,
                    verbose=-1,
                ),
            )
        )

    # Add CatBoost if available
    if CATBOOST_AVAILABLE:
        base_estimators.append(
            (
                "catboost",
                CatBoostClassifier(
                    iterations=(120 if lightweight else 350),
                    learning_rate=0.05,
                    max_depth=6,
                    l2_leaf_reg=1.0,
                    scale_pos_weight=2.0,
                    loss_function="Logloss",
                    eval_metric="AUC",
                    random_state=RANDOM_STATE,
                    verbose=0,
                    allow_writing_files=False,
                ),
            )
        )

    # Meta-learner with class weighting
    meta_learner = LogisticRegression(
        class_weight={0: 1.0, 1: 1.8},
        max_iter=5000,
        solver="lbfgs",
        random_state=RANDOM_STATE,
        n_jobs=n_jobs_setting,
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

    # Load data
    if not args.input.exists():
        raise FileNotFoundError(
            f"Input feature file not found: {args.input}. "
            "Run step2_enhanced_feature_extraction.py first, or pass an existing feature CSV."
        )

    df = pd.read_csv(args.input)
    if args.target_column not in df.columns:
        raise ValueError(f"Missing target column: {args.target_column}")

    X = df.drop(columns=[args.target_column])
    y = df[args.target_column].astype(int)

    # Automatic stratified sampling for very large datasets to avoid OOM
    total_rows = len(X)
    if total_rows > args.max_rows and not args.no_sampling:
        print(
            f"⚠ Large dataset detected ({total_rows} rows). Sampling to {args.max_rows} rows (stratified)."
        )
        pos = df[df[args.target_column] == 1]
        neg = df[df[args.target_column] == 0]
        pos_n = min(len(pos), args.max_rows // 2)
        neg_n = min(len(neg), args.max_rows // 2)
        sampled = pd.concat(
            [pos.sample(n=pos_n, random_state=RANDOM_STATE), neg.sample(n=neg_n, random_state=RANDOM_STATE)]
        )
        X = sampled.drop(columns=[args.target_column])
        y = sampled[args.target_column].astype(int)
        print(f"Sampled dataset: {len(X)} rows ({y.value_counts().to_dict()})")

    print(f"Dataset: {len(X)} samples, {len(X.columns)} features")
    print(f"Class distribution: {y.value_counts().to_dict()}")

    # Three-way split: train, validation, test
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=RANDOM_STATE, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=RANDOM_STATE, stratify=y_temp
    )

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # Train stacked ensemble
    print("\n🔧 Training ultra ensemble...")
    model = build_ultra_ensemble(lightweight=args.lightweight)
    model.fit(X_train, y_train)

    # Calibrate probabilities on validation set
    print("📊 Calibrating probabilities...")
    try:
        calibrated_model = CalibratedClassifierCV(
            model,
            method=args.calibration_method,
            cv="prefit",
        )
        calibrated_model.fit(X_val, y_val)
    except InvalidParameterError:
        print("⚠ CalibratedClassifierCV(cv='prefit') not supported; using manual 1-D calibrator fallback.")
        probs_val = model.predict_proba(X_val)[:, 1]
        if args.calibration_method == "sigmoid":
            from sklearn.linear_model import LogisticRegression as _LR

            lr = _LR(max_iter=1000)
            lr.fit(probs_val.reshape(-1, 1), y_val)
            calibrated_model = ManualCalibratedModel(model, lr, method="sigmoid")
        else:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(probs_val, y_val)
            calibrated_model = ManualCalibratedModel(model, iso, method="isotonic")
    except Exception as exc:  # fallback for any other calibration issues
        print(f"⚠ Calibration failed ({exc}); using uncalibrated model probabilities instead.")
        class _IdentityCalibrator:
            def predict_proba(self, X):
                p = model.predict_proba(X)[:, 1]
                return np.vstack([1 - p, p]).T

        calibrated_model = _IdentityCalibrator()

    # Generate predictions
    y_val_prob = calibrated_model.predict_proba(X_val)[:, 1]
    y_test_prob = calibrated_model.predict_proba(X_test)[:, 1]

    # Find optimal threshold
    print("⚡ Optimizing threshold...")
    threshold, tuning_score, tuning_precision = _search_optimal_threshold(
        y_val, y_val_prob, beta=args.optimize_beta, min_precision=args.min_precision
    )
    youden_threshold = _youden_index_threshold(y_val, y_val_prob)

    print(f"  F-beta optimal: {threshold:.4f} (score: {tuning_score:.4f})")
    print(f"  Youden optimal: {youden_threshold:.4f}")

    # Evaluate
    val_metrics = _evaluate(y_val, y_val_prob, threshold)
    test_metrics = _evaluate(y_test, y_test_prob, threshold)

    print("\n📈 Validation Metrics:")
    print(f"  Accuracy: {val_metrics['accuracy']:.4f} | Precision: {val_metrics['precision']:.4f}")
    print(f"  Recall: {val_metrics['recall']:.4f} | F1: {val_metrics['f1']:.4f}")
    print(f"  ROC-AUC: {val_metrics['roc_auc']:.4f} | PR-AUC: {val_metrics['pr_auc']:.4f}")

    print("\n📈 Test Metrics:")
    print(f"  Accuracy: {test_metrics['accuracy']:.4f} | Precision: {test_metrics['precision']:.4f}")
    print(f"  Recall: {test_metrics['recall']:.4f} | F1: {test_metrics['f1']:.4f}")
    print(f"  ROC-AUC: {test_metrics['roc_auc']:.4f} | PR-AUC: {test_metrics['pr_auc']:.4f}")

    # Save artifacts
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = args.output_dir / "ultra_ensemble.joblib"
    calibrated_path = args.output_dir / "ultra_ensemble_calibrated.joblib"
    threshold_path = args.output_dir / "ultra_threshold.txt"
    metrics_path = args.output_dir / "ultra_metrics.csv"

    joblib.dump(model, model_path)
    joblib.dump(calibrated_model, calibrated_path)
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

    print(f"\n✓ Saved model to {model_path}")
    print(f"✓ Saved calibrated model to {calibrated_path}")
    print(f"✓ Saved threshold to {threshold_path}")
    print(f"✓ Saved metrics to {metrics_path}")
    
    print("\n🚀 Ultra ensemble training complete!")
    print(f"   Base learners: {len(model.estimators_)}")
    print(f"   Calibration: {args.calibration_method}")
    print(f"   Optimal threshold: {threshold:.4f}")


if __name__ == "__main__":
    main()
