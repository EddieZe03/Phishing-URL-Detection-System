Param(
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"
$hasError = $false

function Write-Ok($msg) { Write-Host "[OK]  $msg" -ForegroundColor Green }
function Write-WarnMsg($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERR] $msg" -ForegroundColor Red; $script:hasError = $true }

Write-Host "Checking Flutter Android build environment..." -ForegroundColor Cyan

# 1) Flutter available
$flutterCmd = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $flutterCmd) {
    Write-Err "Flutter is not in PATH. Install Flutter and add it to PATH."
} else {
    Write-Ok "Flutter found: $($flutterCmd.Source)"
}

# 2) Java available
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if (-not $javaCmd) {
    Write-Err "Java is not in PATH. Install JDK 17+ and add it to PATH."
} else {
    Write-Ok "Java found: $($javaCmd.Source)"
}

# 3) Android SDK env vars and folders
$androidHome = $env:ANDROID_HOME
$androidSdkRoot = $env:ANDROID_SDK_ROOT
$resolvedSdk = $null

if ($androidHome -and (Test-Path $androidHome)) {
    $resolvedSdk = $androidHome
    Write-Ok "ANDROID_HOME set: $androidHome"
} elseif ($androidSdkRoot -and (Test-Path $androidSdkRoot)) {
    $resolvedSdk = $androidSdkRoot
    Write-Ok "ANDROID_SDK_ROOT set: $androidSdkRoot"
} else {
    $defaultSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
    if (Test-Path $defaultSdk) {
        $resolvedSdk = $defaultSdk
        Write-WarnMsg "ANDROID_HOME / ANDROID_SDK_ROOT not set. Found default SDK at: $defaultSdk"
        Write-WarnMsg "Set ANDROID_HOME to this path for stable builds."
    } else {
        Write-Err "Android SDK not found. Install Android Studio SDK and set ANDROID_HOME."
    }
}

if ($resolvedSdk) {
    $platformTools = Join-Path $resolvedSdk "platform-tools"
    $buildTools = Join-Path $resolvedSdk "build-tools"
    $platforms = Join-Path $resolvedSdk "platforms"
    $cmdlineTools = Join-Path $resolvedSdk "cmdline-tools"

    if (Test-Path $platformTools) { Write-Ok "platform-tools found" } else { Write-Err "Missing platform-tools folder" }
    if (Test-Path $buildTools) { Write-Ok "build-tools found" } else { Write-Err "Missing build-tools folder" }
    if (Test-Path $platforms) { Write-Ok "platforms found" } else { Write-Err "Missing platforms folder" }
    if (Test-Path $cmdlineTools) { Write-Ok "cmdline-tools found" } else { Write-WarnMsg "cmdline-tools not found (needed for sdkmanager/licenses)" }
}

# 4) adb available
$adbCmd = Get-Command adb -ErrorAction SilentlyContinue
if (-not $adbCmd) {
    Write-WarnMsg "adb not in PATH. Add %ANDROID_HOME%\\platform-tools to PATH."
} else {
    Write-Ok "adb found: $($adbCmd.Source)"
}

# 5) Flutter doctor quick validation
if ($flutterCmd) {
    Write-Host "Running flutter doctor -v..." -ForegroundColor Cyan
    $doctorOutput = & flutter doctor -v 2>&1
    if ($VerboseOutput) {
        $doctorOutput | ForEach-Object { Write-Host $_ }
    }

    $doctorText = ($doctorOutput | Out-String)
    if ($doctorText -match "No Android SDK found") {
        Write-Err "flutter doctor reports: No Android SDK found"
    }
    if ($doctorText -match "Android toolchain.*(X|not available|unable)") {
        Write-WarnMsg "Android toolchain has warnings/errors. Review flutter doctor output."
    }
}

Write-Host ""
if ($hasError) {
    Write-Host "Environment check FAILED." -ForegroundColor Red
    exit 1
} else {
    Write-Host "Environment check PASSED." -ForegroundColor Green
    exit 0
}
