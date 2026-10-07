param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    throw "Python 3.12 is required to build the ARM Core package."
}

$python = $pythonCmd.Source
Write-Host "Build Python:"
& $python --version

if (Test-Path ".venv-build") {
    Remove-Item ".venv-build" -Recurse -Force
}

& $python -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw "Could not create build venv" }

$py = ".\.venv-build\Scripts\python.exe"

& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

Write-Host "Installing tested ARM V2.2.8 PyTorch CUDA runtime..."
& $py -m pip install torch==2.11.0+cu128 torchvision==0.26.0+cu128 --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw "PyTorch CUDA runtime install failed" }

& $py -m pip install -r requirements_arm_core.txt
if ($LASTEXITCODE -ne 0) { throw "ARM core dependencies install failed" }

Write-Host "Generating transparent Niyomsil Design icon..."
& $py ".\tools\generate_brand_assets.py"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path ".\assets\app_icon.ico")) {
    throw "Could not generate transparent Niyomsil Design icon."
}

Write-Host "Downloading exact RealESRGAN_x4plus model used by the tested ARM core..."
New-Item -ItemType Directory -Force -Path ".\models" | Out-Null
$modelUrl = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
$modelPath = ".\models\RealESRGAN_x4plus.pth"
Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath

$expectedModelHash = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
$actualModelHash = (Get-FileHash -Algorithm SHA256 $modelPath).Hash.ToLower()
if ($actualModelHash -ne $expectedModelHash) {
    throw "RealESRGAN_x4plus SHA256 mismatch: $actualModelHash"
}
Write-Host "MODEL SHA256 OK: $actualModelHash"

Write-Host "Validating ARM core imports..."
& $py -m py_compile run.py signprint_ai\app_v2.py signprint_ai\arm_core_adapter.py app\device\device_manager.py app\engine\engine_manager.py app\engine\realesrgan_engine.py tools\generate_brand_assets.py
if ($LASTEXITCODE -ne 0) { throw "Python source validation failed" }

& $py -c "exec(open('pyi_rth_basicsr_compat.py', encoding='utf-8').read()); from app.engine.realesrgan_engine import RealESRGANEngine; print('ARM RealESRGANEngine import OK')"
if ($LASTEXITCODE -ne 0) { throw "ARM engine import validation failed" }

Remove-Item build, dist, release -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Building V2 UI + ARM V2.2.8 PyTorch Core..."
& $py -m PyInstaller --noconfirm --clean ".\NiyomsilV2ArmCore.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ARM Core build failed" }

$exe = ".\dist\NiyomsilAIEnhancer\NiyomsilAIEnhancer.exe"
$packedModel = ".\dist\NiyomsilAIEnhancer\_internal\models\RealESRGAN_x4plus.pth"

if (-not (Test-Path $exe)) {
    throw "V2 executable was not generated."
}
if (-not (Test-Path $packedModel)) {
    throw "RealESRGAN_x4plus.pth was not packaged."
}

$packedHash = (Get-FileHash -Algorithm SHA256 $packedModel).Hash.ToLower()
if ($packedHash -ne $expectedModelHash) {
    throw "Packaged RealESRGAN model hash mismatch: $packedHash"
}

@"
NIYOMSIL DESIGN V2.0 - ARM CORE BUILD PROOF

UI:
- signprint_ai/app_v2.py
- Black/Red Niyomsil Design V2 interface

AI processing core:
- app/device/device_manager.py
- app/engine/engine_manager.py
- app/engine/realesrgan_engine.py
- signprint_ai/arm_core_adapter.py

Model:
- RealESRGAN_x4plus.pth
- SHA256: $expectedModelHash

Runtime:
- PyTorch 2.11.0 + CUDA 12.8 wheels
- TorchVision 0.26.0
- CUDA preferred automatically on supported NVIDIA GPU
- FP32 on the tested ARM path

Important:
- NCNN backend is NOT used by this build.
- No fallback to Lanczos replaces the ARM AI engine.
- No extra denoise / contrast / sharpen filter is applied after ARM AI processing.
- RGB PNG output preserves the final ARM Core pixels.
- CMYK/ICC conversion is export-only.
"@ | Set-Content ".\dist\NiyomsilAIEnhancer\ARM_CORE_BUILD_PROOF.txt" -Encoding utf8

Get-Item $exe | Format-List FullName,Length
Get-Item $packedModel | Format-List FullName,Length
Write-Host "ARM CORE MODEL VERIFIED: $packedHash"

if (-not $SkipInstaller) {
    $isccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 was not found."
    }

    Write-Host "Building Windows installer..."
    & $iscc ".\installer.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
    }

    $installer = ".\release\Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe"
    if (-not (Test-Path $installer)) {
        throw "Installer compile reported success but the expected EXE is missing."
    }

    $installerHash = (Get-FileHash -Algorithm SHA256 $installer).Hash.ToLower()
    "$installerHash  Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe" |
        Set-Content ".\release\Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe.sha256.txt" -Encoding ascii

    Get-Item $installer | Format-List FullName,Length
    Write-Host "Installer SHA256: $installerHash"
}

Write-Host "V2 ARM CORE BUILD COMPLETE"
