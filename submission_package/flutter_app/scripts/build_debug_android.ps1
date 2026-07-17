$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "Step 1/3: Checking Android environment..." -ForegroundColor Cyan
& "$PSScriptRoot\check_android_env.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Stop: fix environment issues above, then rerun." -ForegroundColor Red
    exit 1
}

Write-Host "Step 2/3: Resolving Flutter packages..." -ForegroundColor Cyan
flutter pub get
if ($LASTEXITCODE -ne 0) {
    Write-Host "flutter pub get failed." -ForegroundColor Red
    exit 1
}

Write-Host "Step 3/3: Building debug APK..." -ForegroundColor Cyan
flutter build apk --debug
if ($LASTEXITCODE -ne 0) {
    Write-Host "APK build failed." -ForegroundColor Red
    exit 1
}

Write-Host "Build succeeded." -ForegroundColor Green
Write-Host "APK path: build\app\outputs\flutter-apk\app-debug.apk" -ForegroundColor Green
