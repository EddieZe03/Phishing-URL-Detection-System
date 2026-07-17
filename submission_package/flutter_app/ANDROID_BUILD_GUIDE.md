# Android Build & Installation Guide

## Prerequisites
- Flutter SDK installed on Windows
- Android Studio or Android SDK tools installed
- Android phone with USB debugging enabled
- USB cable to connect phone to computer

## Step 1: Enable USB Debugging on Phone

1. Go to **Settings → About Phone**
2. Tap **Build Number** 7 times to enable Developer Options
3. Go back to **Settings → Developer Options**
4. Enable **USB Debugging**
5. Connect phone to computer via USB cable

## Step 2: Configure API URL (Recommended: USB Reverse)

You no longer need to hardcode a LAN IP in code.

The app reads API URL in this order:
- Runtime override (`ApiService.setBaseUrl(...)`)
- Build-time define (`--dart-define=API_BASE_URL=...`)
- Platform default (Android emulator `10.0.2.2`, iOS/web `localhost`)

For **Android physical phone over USB cable**, use ADB reverse so phone can call laptop localhost:

```bash
adb reverse tcp:5000 tcp:5000
```

Then your phone can reach backend at:

```text
http://127.0.0.1:5000
```

## Step 3: Build APK on Windows

Open Command Prompt/PowerShell and navigate to the flutter_app folder:

```bash
cd /workspaces/FYP/flutter_app

# Install dependencies
flutter pub get

# Build APK (debug version for phone testing)
flutter build apk --debug
```

### Recommended: Run Automatic Environment Check First

Use the included PowerShell scripts to verify setup and run build in one flow:

```powershell
cd /workspaces/FYP/flutter_app

# Check Flutter + Android SDK + adb + doctor status
powershell -ExecutionPolicy Bypass -File .\scripts\check_android_env.ps1

# If check passes, run full debug build pipeline
powershell -ExecutionPolicy Bypass -File .\scripts\build_debug_android.ps1
```

If you prefer double-click or Command Prompt, use the batch wrappers:

```bat
scripts\check_android_env.bat
scripts\build_debug_android.bat
```

The APK will be generated at:
```
flutter_app/build/app/outputs/apk/debug/app-debug.apk
```

## Step 4: Install APK on Phone

**Option A: Using Flutter (Easiest)**
```bash
flutter install
```
This automatically installs the app on your connected phone.

If you want to install the APK manually after building:
```bash
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

**Option B: Manual Installation**
```bash
# List connected devices
flutter devices

# Install specific APK manually
adb install build/app/outputs/apk/debug/app-debug.apk
```

## Step 5: Grant Permissions

When you first run the app, Android will ask for:
- ✅ Camera permission (for QR scanning)
- ✅ Internet permission (automatically granted)

Tap **Allow** for camera access.

## Step 6: Connect to Flask Backend

1. Make sure Flask backend is running on your Windows PC:
   ```bash
   python app.py
   ```

2. If using Android physical phone via USB, run:
   ```bash
   adb reverse tcp:5000 tcp:5000
   ```

3. If needed, pass API URL at run/build time:
   ```bash
   flutter run --dart-define=API_BASE_URL=http://127.0.0.1:5000
   ```

4. Backend should respond at `http://127.0.0.1:5000` from the phone app when ADB reverse is active.

5. Open Phish Guard app on Android phone and start scanning!

## Building Release APK (Optional)

For distribution, create a release APK:

```bash
flutter build apk --release
```

The release APK will be smaller and faster, but requires signing with your own key.

## Troubleshooting

**App won't connect to Flask backend:**
- Make sure Flask app is running: `python app.py`
- Re-run USB reverse mapping: `adb reverse tcp:5000 tcp:5000`
- Verify reverse mapping exists: `adb reverse --list`
- If USB reverse is unavailable, fallback to LAN and run with:
   `flutter run --dart-define=API_BASE_URL=http://<PC_IP>:5000`
- Firewall may still block port 5000 on host

**Flutter not recognized:**
- Add Flutter to PATH: [https://flutter.dev/docs/get-started/install/windows](https://flutter.dev/docs/get-started/install/windows)

**ADB not found:**
- Install Android SDK: [https://developer.android.com/studio](https://developer.android.com/studio)
- Add Android SDK/platform-tools to PATH

**No Android SDK found:**
- Set `ANDROID_HOME` to `C:\Users\<YourUser>\AppData\Local\Android\Sdk`
- Add `%ANDROID_HOME%\platform-tools` to PATH
- Restart terminal and run:
   ```bash
   flutter doctor -v
   ```

**Camera permission denied:**
- Go to **Phone Settings → Apps → Phish Guard → Permissions → Camera**
- Enable camera access
