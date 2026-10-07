param(
    [switch]$SkipAI,
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    throw "Python 3.11+ is required only to BUILD the app. The finished app does not require Python."
}
$python = $pythonCmd.Source
Write-Host "Build Python:"
& $python --version

# Recreate the build environment from the selected Python so GitHub Actions
# does not accidentally pick a newer system py launcher (for example 3.14).
if (Test-Path ".venv-build") {
    Remove-Item ".venv-build" -Recurse -Force
}
& $python -m venv .venv-build
$py = ".\.venv-build\Scripts\python.exe"

& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed" }

# Generate Windows application/installer icon from the user's Niyomsil Design logo.
& $py ".\tools\generate_brand_assets.py"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path ".\assets\app_icon.ico")) {
    throw "Could not generate Niyomsil Design Windows icon."
}

if (-not $SkipAI) {
    & powershell -ExecutionPolicy Bypass -File ".\tools\download_realesrgan_ncnn.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Real-ESRGAN download failed" }
}

Remove-Item build, dist, release -Recurse -Force -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name "NiyomsilAIEnhancer" `
    --icon ".\assets\app_icon.ico" `
    --collect-all windnd `
    --add-data "NOTICE_INDEPENDENT_PROJECT.txt;." `
    --add-data "assets;assets" `
    run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

if (-not (Test-Path ".\tools\realesrgan-ncnn-vulkan.exe")) {
    throw "AI backend download completed without realesrgan-ncnn-vulkan.exe. Build aborted."
}
New-Item -ItemType Directory -Force -Path ".\dist\NiyomsilAIEnhancer\tools" | Out-Null
Copy-Item ".\tools\realesrgan-ncnn-vulkan.exe" ".\dist\NiyomsilAIEnhancer\tools\" -Force
if (Test-Path ".\tools\models") {
    Copy-Item ".\tools\models" ".\dist\NiyomsilAIEnhancer\tools\models" -Recurse -Force
}
Get-ChildItem ".\tools" -Filter "*.dll" -ErrorAction SilentlyContinue |
    Copy-Item -Destination ".\dist\NiyomsilAIEnhancer\tools\" -Force

$packedAI = ".\dist\NiyomsilAIEnhancer\tools\realesrgan-ncnn-vulkan.exe"
if (-not (Test-Path $packedAI)) {
    throw "Real-ESRGAN was not packed into the portable app."
}
$aiSize = (Get-Item $packedAI).Length
if ($aiSize -lt 100000) {
    throw "Packed Real-ESRGAN executable is unexpectedly small."
}
if (-not (Test-Path ".\dist\NiyomsilAIEnhancer\tools\models")) {
    throw "Real-ESRGAN models folder is missing from the packaged app."
}
Write-Host "AI backend verification passed: $packedAI ($aiSize bytes)"

Copy-Item README_TH.md ".\dist\NiyomsilAIEnhancer\README_TH.md" -Force
Copy-Item THIRD_PARTY_NOTICES.md ".\dist\NiyomsilAIEnhancer\THIRD_PARTY_NOTICES.md" -Force

if (-not $SkipInstaller) {
    $isccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 was not found."
    }

    & $iscc ".\installer.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
    }

    $installer = ".\release\Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe"
    if (-not (Test-Path $installer)) {
        throw "Installer compile reported success but the expected EXE is missing."
    }
    Write-Host "Installer created: $installer"
}

Write-Host "BUILD COMPLETE"
