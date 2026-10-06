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
    --name "SignPrintAIEnhancer" `
    --collect-all windnd `
    --add-data "NOTICE_INDEPENDENT_PROJECT.txt;." `
    run.py

# Add the optional AI backend beside the frozen executable.
if (Test-Path ".\tools\realesrgan-ncnn-vulkan.exe") {
    New-Item -ItemType Directory -Force -Path ".\dist\SignPrintAIEnhancer\tools" | Out-Null
    Copy-Item ".\tools\realesrgan-ncnn-vulkan.exe" ".\dist\SignPrintAIEnhancer\tools\" -Force
    if (Test-Path ".\tools\models") { Copy-Item ".\tools\models" ".\dist\SignPrintAIEnhancer\tools\models" -Recurse -Force }
    Get-ChildItem ".\tools" -Filter "*.dll" -ErrorAction SilentlyContinue | Copy-Item -Destination ".\dist\SignPrintAIEnhancer\tools\" -Force
}
Copy-Item README_TH.md ".\dist\SignPrintAIEnhancer\README_TH.md" -Force
Copy-Item THIRD_PARTY_NOTICES.md ".\dist\SignPrintAIEnhancer\THIRD_PARTY_NOTICES.md" -Force

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
        Write-Warning "Inno Setup 6 not found. Portable app is ready under .\dist\SignPrintAIEnhancer"
    }
}
Write-Host "BUILD COMPLETE"
