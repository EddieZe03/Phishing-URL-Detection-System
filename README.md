# Phishing-URL-Detection-System
Phishing URL and Quishing Detection System using Hybrid Ensemble Learning and Flutter

# Submission Package

This folder collects the code you should submit for the Flutter app and the ensemble learning project.

## Included

- `app.py`
- `requirements.txt`
- `Dockerfile`
- `templates/`
- `static/`
- `ml_pipeline/src/`
- `ml_pipeline/scripts/`
- `flutter_app/`

## What was intentionally left out

- Generated build output such as `build/` and `.dart_tool/`
- Cached or generated files such as model artifacts and processed CSV outputs
- Large dataset files

## Main code entry points

- Flutter app: `flutter_app/lib/main.dart`
- Backend app: `app.py`
- Ultra ensemble training: `ml_pipeline/scripts/train_ultra_ensemble.sh`
- Ultra ensemble model code: `ml_pipeline/src/step4_ultra_ensemble.py`

## Start the Flutter app

From the repository root, run:

```bash
cd flutter_app
flutter pub get
flutter run
```

If you need the backend at the same time, start `app.py` in a separate terminal before launching Flutter.
