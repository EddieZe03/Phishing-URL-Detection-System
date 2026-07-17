#!/bin/bash
# Master training script for the ultra ensemble pipeline

set -e

echo "=========================================="
echo "🚀 ULTRA ENSEMBLE TRAINING PIPELINE 🚀"
echo "=========================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DATA_DIR="${PROJECT_ROOT}/data"
ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts"
DATASET_PATH="${DATA_DIR}/processed_urls_with_all_datasets.csv"
WHOIS_CACHE="${ARTIFACTS_DIR}/whois_cache.csv"

# Step 1: Feature Engineering with Enhanced Features
echo -e "${BLUE}Step 1: Enhanced Feature Extraction${NC}"
echo "Input: $DATASET_PATH"
BASIC_FEATURES="${DATA_DIR}/url_features_all_datasets.csv"
ENHANCED_FEATURES="${DATA_DIR}/url_features_enhanced_all_datasets.csv"

if [ ! -f "$BASIC_FEATURES" ]; then
    echo -e "${YELLOW}Extracting basic features...${NC}"
    /usr/bin/python3 "${PROJECT_ROOT}/src/step2_feature_extraction.py" \
        --input "$DATASET_PATH" \
        --output "$BASIC_FEATURES" \
        --whois-cache "$WHOIS_CACHE" \
        --whois-max-lookups 500 \
        --dns-max-lookups 10000
    echo -e "${GREEN}✓ Basic features saved to $BASIC_FEATURES${NC}"
else
    echo -e "${YELLOW}Basic features already exist, skipping...${NC}"
fi

echo -e "${YELLOW}Extracting enhanced features...${NC}"
/usr/bin/python3 "${PROJECT_ROOT}/src/step2_enhanced_feature_extraction.py" \
    --input "$DATASET_PATH" \
    --output "$ENHANCED_FEATURES" \
    --whois-cache "$WHOIS_CACHE"
echo -e "${GREEN}✓ Enhanced features saved to $ENHANCED_FEATURES${NC}"

# Step 2: Train Ultra Ensemble
echo ""
echo -e "${BLUE}Step 2: Training Ultra Ensemble (with Calibration & Advanced Optimization)${NC}"
ULTRA_ENSEMBLE_DIR="${ARTIFACTS_DIR}/ensemble_ultra_all_datasets"
mkdir -p "$ULTRA_ENSEMBLE_DIR"

/usr/bin/python3 "${PROJECT_ROOT}/src/step4_ultra_ensemble.py" \
    --input "$ENHANCED_FEATURES" \
    --output-dir "$ULTRA_ENSEMBLE_DIR" \
    --optimize-beta 2.0 \
    --min-precision 0.70 \
    --calibration-method isotonic \
    --calibration-folds 5

echo -e "${GREEN}✓ Ultra ensemble trained and saved to $ULTRA_ENSEMBLE_DIR${NC}"

# Step 3: Model Comparison (Optional)
if command -v python3 &> /dev/null; then
    echo ""
    echo -e "${BLUE}Step 3: Model Comparison${NC}"
    
    OLD_ENSEMBLE="${ARTIFACTS_DIR}/ensemble_all_datasets/soft_voting_ensemble.joblib"
    NEW_ENSEMBLE="${ULTRA_ENSEMBLE_DIR}/ultra_ensemble_calibrated.joblib"
    
    if [ -f "$OLD_ENSEMBLE" ] && [ -f "$NEW_ENSEMBLE" ]; then
        python3 << 'EOF'
import sys
import joblib
import pandas as pd
from pathlib import Path

# Quick comparison
print("\n📊 Model Comparison Summary")
print("=" * 60)

old_path = Path("artifacts/ensemble_all_datasets/soft_voting_ensemble.joblib")
new_path = Path("artifacts/ensemble_ultra_all_datasets/ultra_ensemble_calibrated.joblib")

if old_path.exists():
    old_model = joblib.load(old_path)
    print(f"✓ Old Model (Soft Voting): {type(old_model).__name__}")
    
if new_path.exists():
    new_model = joblib.load(new_path)
    print(f"✓ New Model (Ultra Ensemble): {type(new_model).__name__}")
    
old_metrics = Path("artifacts/ensemble_all_datasets/metrics.csv")
new_metrics = Path("artifacts/ensemble_ultra_all_datasets/ultra_metrics.csv")

if old_metrics.exists() and new_metrics.exists():
    old_df = pd.read_csv(old_metrics)
    new_df = pd.read_csv(new_metrics)
    
    print("\nTest Set Improvements:")
    print("-" * 60)
    
    old_test = old_df[old_df['split'] == 'test'].iloc[0] if 'split' in old_df.columns else old_df.iloc[-1]
    new_test = new_df[new_df['split'] == 'test'].iloc[0]
    
    metrics_to_compare = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc']
    
    for metric in metrics_to_compare:
        if metric in old_test and metric in new_test:
            old_val = float(old_test[metric])
            new_val = float(new_test[metric])
            change = new_val - old_val
            change_pct = (change / old_val * 100) if old_val != 0 else 0
            
            arrow = "📈" if change > 0.001 else "📉" if change < -0.001 else "➡️"
            print(f"{arrow} {metric.upper():12s}: {old_val:.4f} → {new_val:.4f} ({change_pct:+.2f}%)")

print("=" * 60)
EOF
    fi
fi

# Step 4: Instructions for Deployment
echo ""
echo -e "${GREEN}=========================================="
echo "✅ ULTRA ENSEMBLE PIPELINE COMPLETE! ✅"
echo "==========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Review metrics in: ${ULTRA_ENSEMBLE_DIR}/ultra_metrics.csv"
echo "2. Update backend with new model:"
echo "   export FINAL_MODEL_PATH=\"${ULTRA_ENSEMBLE_DIR}/ultra_ensemble_calibrated.joblib\""
echo "   export PHISHING_THRESHOLD=\$(cat ${ULTRA_ENSEMBLE_DIR}/ultra_threshold.txt)"
echo ""
echo "3. To deploy:"
echo "   cd ${PROJECT_ROOT}"
echo "   FINAL_MODEL_PATH=\"${ULTRA_ENSEMBLE_DIR}/ultra_ensemble_calibrated.joblib\" \\"
echo "   PHISHING_THRESHOLD=\$(cat ${ULTRA_ENSEMBLE_DIR}/ultra_threshold.txt) \\"
echo "   python3 app.py"
echo ""
echo -e "${BLUE}Model Features:${NC}"
echo "✓ 15+ advanced URL features (punycode, entropy variants, brand impersonation)"
echo "✓ 5-6 base learners (RF, GB, XGB, ET, LGB*, CB*) with stacking"
echo "✓ Probability calibration (isotonic regression)"
echo "✓ Advanced threshold optimization (F-beta + Youden's index)"
echo "✓ Class weighting for better recall on phishing URLs"
echo ""
echo "*LGB and CB available if lightgbm and catboost are installed"
echo ""
