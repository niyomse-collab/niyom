param(
    [switch]$SkipAI,
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is required only to BUILD the app. The finished app does not require Python. Install Python, then run this script again."
}
$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
if (-not (Test-Path ".venv-build")) {
    & $python -m venv .venv-build
}
$py = ".\.venv-build\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

if (-not $SkipAI) {
    & powershell -ExecutionPolicy Bypass -File ".\tools\download_realesrgan_ncnn.ps1"
}

Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name "NiyomsilAIEnhancer" `
    --collect-all windnd `
    --add-data "NOTICE_INDEPENDENT_PROJECT.txt;." `
    --add-data "assets;assets" `
    run.py

# Add the optional AI backend beside the frozen executable.
if (-not (Test-Path ".\tools\realesrgan-ncnn-vulkan.exe")) {
    throw "AI backend download completed without realesrgan-ncnn-vulkan.exe. Build aborted to prevent low-quality fallback."
}
New-Item -ItemType Directory -Force -Path ".\dist\NiyomsilAIEnhancer\tools" | Out-Null
Copy-Item ".\tools\realesrgan-ncnn-vulkan.exe" ".\dist\NiyomsilAIEnhancer\tools\" -Force
if (Test-Path ".\tools\models") { Copy-Item ".\tools\models" ".\dist\NiyomsilAIEnhancer\tools\models" -Recurse -Force }
Get-ChildItem ".\tools" -Filter "*.dll" -ErrorAction SilentlyContinue | Copy-Item -Destination ".\dist\NiyomsilAIEnhancer\tools\" -Force

$packedAI = ".\dist\NiyomsilAIEnhancer\tools\realesrgan-ncnn-vulkan.exe"
if (-not (Test-Path $packedAI)) {
    throw "Real-ESRGAN was not packed into the portable app. Build aborted."
}
$aiSize = (Get-Item $packedAI).Length
if ($aiSize -lt 100000) {
    throw "Packed Real-ESRGAN executable is unexpectedly small. Build aborted."
}
if (-not (Test-Path ".\dist\NiyomsilAIEnhancer\tools\models")) {
    throw "Real-ESRGAN models folder is missing from the packaged app. Build aborted."
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
    if ($iscc) {
        & $iscc ".\installer.iss"
        Write-Host "Installer created under .\release"
    } else {
        Write-Warning "Inno Setup 6 not found. Portable app is ready under .\dist\NiyomsilAIEnhancer"
    }
}
Write-Host "BUILD COMPLETE"
