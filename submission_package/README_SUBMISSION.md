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

If you want to compress this for upload, zip the entire `submission_package/` folder.
