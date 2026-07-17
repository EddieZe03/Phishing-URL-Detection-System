# Phishing-URL-Detection-System
Phishing URL and Quishing Detection System using Hybrid Ensemble Learning and Flutter

# Submission Package

This folder contains the submission-ready code for the phishing URL detection project and the Flutter mobile app.

## Project Summary

Phish Guard is a phishing URL detection system that combines:

- a Flask backend for URL analysis and prediction
- an ensemble learning pipeline for phishing classification
- a Flutter app for mobile scanning and manual URL checks

The mobile app sends URLs or scanned QR payloads to the backend, and the backend returns a phishing verdict with supporting metadata.

## What Is Included

- `app.py` - Flask backend and `/api/predict` inference endpoint
- `requirements.txt` - Python dependencies for the backend and ML pipeline
- `Dockerfile` - container configuration for deployment
- `templates/` - web UI templates for the backend interface
- `static/` - frontend assets for the backend interface
- `ml_pipeline/src/` - training and feature engineering code
- `ml_pipeline/scripts/` - training and validation scripts
- `flutter_app/` - Flutter mobile application

## What Was Intentionally Left Out

- generated build output such as `build/` and `.dart_tool/`
- cached or generated model artifacts and processed CSV outputs
- large dataset files that are not needed for submission

## Main Entry Points

- Flutter app: `flutter_app/lib/main.dart`
- Flutter API client: `flutter_app/lib/services/api_service.dart`
- Backend app: `app.py`
- Backend HTML UI: `templates/`
- Ultra ensemble training script: `ml_pipeline/scripts/train_ultra_ensemble.sh`
- Ultra ensemble model code: `ml_pipeline/src/step4_ultra_ensemble.py`

## How The System Works

1. The user enters a URL manually or scans a QR code in the Flutter app.
2. The app sends the payload to the Flask backend.
3. The backend applies the phishing detection pipeline and returns a prediction.
4. The app displays the result to the user.

The backend exposes these API routes:

- `GET /api/health` for a health check
- `POST /api/predict` for URL classification

## How To Run Locally

### 1. Start the backend

From the repository root:

```bash
pip install -r requirements.txt
python app.py
```

The backend listens on `0.0.0.0` and uses port `5000` by default. You can override the port with the `PORT` environment variable.

### 2. Start the Flutter app

In a second terminal:

```bash
cd flutter_app
flutter pub get
flutter run
```

### 3. Point the Flutter app to the backend if needed

The Flutter app reads the backend URL in this order:

1. runtime override in code
2. `--dart-define=API_BASE_URL=...`
3. platform default

Useful examples:

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:5000
```

For Android emulator testing, the app can reach the host machine through `http://10.0.2.2:5000`.

For a real Android device over USB, use:

```bash
adb reverse tcp:5000 tcp:5000
```

## Suggested Demo Flow For The Panel

1. Launch the backend and confirm `GET /api/health` returns OK.
2. Open the Flutter app.
3. Enter a URL manually or scan a QR code.
4. Show the prediction result and explain that the backend performs the classification.
5. If needed, highlight the training pipeline and the ensemble model files in `ml_pipeline/src/` and `ml_pipeline/scripts/`.

## Project Structure Overview

- `app.py` handles prediction requests and HTML rendering.
- `flutter_app/` contains the mobile UI and API client.
- `ml_pipeline/src/` contains preprocessing, feature extraction, and model training logic.
- `ml_pipeline/scripts/` contains automation scripts for training and validation.
- `templates/` and `static/` support the backend web interface.

## Notes For Reviewers

- The submission package is intentionally kept lightweight so it is easy to inspect and upload.
- Generated artifacts and datasets are excluded because they can be recreated from the pipeline or are too large to bundle.
- If you want to compress the submission, zip the entire `submission_package/` folder.
