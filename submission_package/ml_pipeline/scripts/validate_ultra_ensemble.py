#!/usr/bin/env python3
"""Validation script for ultra ensemble dependencies and basic functionality."""

import sys
from pathlib import Path

def check_dependencies():
    """Check if all required and optional dependencies are available."""
    deps = {
        "required": [
            ("pandas", "pandas"),
            ("sklearn", "scikit-learn"),
            ("xgboost", "xgboost"),
            ("tldextract", "tldextract"),
            ("whois", "python-whois"),
            ("joblib", "joblib"),
            ("flask", "flask"),
        ],
        "optional": [
            ("lightgbm", "lightgbm"),
            ("catboost", "catboost"),
        ],
    }
    
    print("=" * 60)
    print("🔍 ULTRA ENSEMBLE DEPENDENCY CHECK")
    print("=" * 60)
    
    all_good = True
    
    print("\n📦 Required Dependencies:")
    for import_name, package_name in deps["required"]:
        try:
            __import__(import_name)
            print(f"  ✓ {package_name}")
        except ImportError:
            print(f"  ✗ {package_name} (MISSING)")
            all_good = False
    
    print("\n📦 Optional Dependencies (for maximum performance):")
    optional_available = []
    for import_name, package_name in deps["optional"]:
        try:
            __import__(import_name)
            print(f"  ✓ {package_name}")
            optional_available.append(package_name)
        except ImportError:
            print(f"  ⚠ {package_name} (optional)")
    
    print("\n" + "=" * 60)
    
    if not all_good:
        print("❌ Missing required dependencies!")
        print("\nInstall with:")
        print("  pip install -r requirements.txt")
        return False
    
    if len(optional_available) == 2:
        print("✅ All dependencies installed! Maximum performance enabled.")
        print(f"   Base learners: 6 (RF, GB, XGB, ET, LGB, CB)")
    elif len(optional_available) == 1:
        print("✅ Core dependencies installed. Optional library available.")
        print(f"   Base learners: 5 (RF, GB, XGB, ET, {optional_available[0].upper()})")
    else:
        print("✅ Core dependencies installed.")
        print(f"   Base learners: 4 (RF, GB, XGB, ET)")
        print(f"\n💡 Tip: Install lightgbm and catboost for +1-2% accuracy boost:")
        print(f"   pip install lightgbm catboost")
    
    return True


def check_model_paths():
    """Check if expected model paths exist."""
    print("\n" + "=" * 60)
    print("📁 MODEL PATH CHECK")
    print("=" * 60)
    
    base = Path("artifacts")
    
    models_to_check = [
        ("Old Ensemble", base / "ensemble_all_datasets" / "soft_voting_ensemble.joblib"),
        ("Stacked Ensemble", base / "ensemble_stronger" / "stacked_ensemble.joblib"),
    ]
    
    print("\nExisting models:")
    for name, path in models_to_check:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  ✓ {name}: {path} ({size_mb:.1f} MB)")
        else:
            print(f"  ✗ {name}: {path} (not found)")
    
    ultra_path = base / "ensemble_ultra_all_datasets"
    if ultra_path.exists():
        print(f"  ✓ Ultra Ensemble: {ultra_path} (exists)")
    else:
        print(f"  ⚠ Ultra Ensemble: {ultra_path} (not yet trained)")


def check_data_files():
    """Check if required data files exist."""
    print("\n" + "=" * 60)
    print("📊 DATA FILES CHECK")
    print("=" * 60)
    
    data = Path("data")
    
    files_to_check = [
        ("Original URLs", data / "processed_urls.csv"),
        ("All Datasets Combined", data / "processed_urls_with_all_datasets.csv"),
        ("Basic Features", data / "url_features_all_datasets.csv"),
        ("Enhanced Features", data / "url_features_enhanced_all_datasets.csv"),
    ]
    
    print("\nData files:")
    for name, path in files_to_check:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{int(size_mb * 1024)} KB"
            print(f"  ✓ {name}: {path} ({size_str})")
        else:
            print(f"  ⚠ {name}: {path} (not found)")


def main():
    """Run all checks."""
    try:
        deps_ok = check_dependencies()
        check_model_paths()
        check_data_files()
        
        print("\n" + "=" * 60)
        if deps_ok:
            print("✅ All checks passed!")
            print("\n🚀 Ready to train ultra ensemble:")
            print("   bash scripts/train_ultra_ensemble.sh")
        else:
            print("❌ Please install missing dependencies first.")
            sys.exit(1)
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during checks: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
