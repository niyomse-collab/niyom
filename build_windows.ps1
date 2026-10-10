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

Write-Host "Downloading optional Face Protect models..."
$faceModelDir = ".\\models\\face"
New-Item -ItemType Directory -Force -Path $faceModelDir | Out-Null

$gfpganUrl = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
$gfpganPath = Join-Path $faceModelDir "GFPGANv1.4.pth"
Invoke-WebRequest -Uri $gfpganUrl -OutFile $gfpganPath
$expectedGfpganHash = "e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad"
$actualGfpganHash = (Get-FileHash -Algorithm SHA256 $gfpganPath).Hash.ToLower()
if ($actualGfpganHash -ne $expectedGfpganHash) {
    throw "GFPGANv1.4 SHA256 mismatch: $actualGfpganHash"
}

$retinaUrl = "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth"
$retinaPath = Join-Path $faceModelDir "detection_Resnet50_Final.pth"
Invoke-WebRequest -Uri $retinaUrl -OutFile $retinaPath
$expectedRetinaHash = "6d1de9c2944f2ccddca5f5e010ea5ae64a39845a86311af6fdf30841b0a5a16d"
$actualRetinaHash = (Get-FileHash -Algorithm SHA256 $retinaPath).Hash.ToLower()
if ($actualRetinaHash -ne $expectedRetinaHash) {
    throw "RetinaFace SHA256 mismatch: $actualRetinaHash"
}

# FaceXLib FaceRestoreHelper initializes ParseNet even with use_parse=False.
# Package it up front so a normal installed app never tries to write a
# .partial download under C:\Program Files at runtime.
$parserUrl = "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth"
$parserPath = Join-Path $faceModelDir "parsing_parsenet.pth"
Invoke-WebRequest -Uri $parserUrl -OutFile $parserPath
$expectedParserHash = "3d558d8d0e42c20224f13cf5a29c79eba2d59913419f945545d8cf7b72920de2"
$actualParserHash = (Get-FileHash -Algorithm SHA256 $parserPath).Hash.ToLower()
if ($actualParserHash -ne $expectedParserHash) {
    throw "ParseNet SHA256 mismatch: $actualParserHash"
}
Write-Host "FACE MODELS VERIFIED"

Write-Host "Validating ARM core + optional face module imports..."
& $py -m py_compile run.py signprint_ai\app_v2.py signprint_ai\arm_core_adapter.py signprint_ai\face_module\__init__.py signprint_ai\face_module\face_protection.py app\device\device_manager.py app\engine\engine_manager.py app\engine\realesrgan_engine.py tools\generate_brand_assets.py
if ($LASTEXITCODE -ne 0) { throw "Python source validation failed" }

& $py -c "exec(open('pyi_rth_basicsr_compat.py', encoding='utf-8').read()); from app.engine.realesrgan_engine import RealESRGANEngine; from gfpgan.archs.gfpganv1_clean_arch import GFPGANv1Clean; from facexlib.utils.face_restoration_helper import FaceRestoreHelper; print('ARM + Face Protect imports OK')"
if ($LASTEXITCODE -ne 0) { throw "ARM/Face module import validation failed" }

Remove-Item build, dist, release -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Building V2 UI + ARM V2.2.8 PyTorch Core..."
& $py -m PyInstaller --noconfirm --clean ".\NiyomsilV2ArmCore.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ARM Core build failed" }

$exe = ".\dist\NiyomsilAIEnhancer\NiyomsilAIEnhancer.exe"
$packedModel = ".\dist\NiyomsilAIEnhancer\_internal\models\RealESRGAN_x4plus.pth"
$packedGfpgan = ".\dist\NiyomsilAIEnhancer\_internal\models\face\GFPGANv1.4.pth"
$packedRetina = ".\dist\NiyomsilAIEnhancer\_internal\models\face\detection_Resnet50_Final.pth"
$packedParser = ".\dist\NiyomsilAIEnhancer\_internal\models\face\parsing_parsenet.pth"

if (-not (Test-Path $exe)) {
    throw "V2 executable was not generated."
}
if (-not (Test-Path $packedModel)) {
    throw "RealESRGAN_x4plus.pth was not packaged."
}
if (-not (Test-Path $packedGfpgan)) {
    throw "GFPGANv1.4.pth was not packaged."
}
if (-not (Test-Path $packedRetina)) {
    throw "RetinaFace detector model was not packaged."
}
if (-not (Test-Path $packedParser)) {
    throw "FaceXLib ParseNet model was not packaged."
}

$packedHash = (Get-FileHash -Algorithm SHA256 $packedModel).Hash.ToLower()
if ($packedHash -ne $expectedModelHash) {
    throw "Packaged RealESRGAN model hash mismatch: $packedHash"
}
$packedGfpganHash = (Get-FileHash -Algorithm SHA256 $packedGfpgan).Hash.ToLower()
if ($packedGfpganHash -ne $expectedGfpganHash) {
    throw "Packaged GFPGAN model hash mismatch: $packedGfpganHash"
}
$packedRetinaHash = (Get-FileHash -Algorithm SHA256 $packedRetina).Hash.ToLower()
if ($packedRetinaHash -ne $expectedRetinaHash) {
    throw "Packaged RetinaFace model hash mismatch: $packedRetinaHash"
}
$packedParserHash = (Get-FileHash -Algorithm SHA256 $packedParser).Hash.ToLower()
if ($packedParserHash -ne $expectedParserHash) {
    throw "Packaged ParseNet model hash mismatch: $packedParserHash"
}

@"
NIYOMSIL DESIGN V2.1.2 - ARM CORE + FACE POPUP PORTRAIT BUILD PROOF

UI:
- signprint_ai/app_v2.py
- Black/Red Niyomsil Design V2 interface

AI processing core:
- app/device/device_manager.py
- app/engine/engine_manager.py
- app/engine/realesrgan_engine.py
- signprint_ai/arm_core_adapter.py

ARM model:
- RealESRGAN_x4plus.pth
- SHA256: $expectedModelHash

Optional Face Protect models:
- GFPGANv1.4.pth
- SHA256: $expectedGfpganHash
- detection_Resnet50_Final.pth
- SHA256: $expectedRetinaHash
- parsing_parsenet.pth
- SHA256: $expectedParserHash

Runtime:
- PyTorch 2.11.0 + CUDA 12.8 wheels
- TorchVision 0.26.0
- CUDA preferred automatically on supported NVIDIA GPU
- FP32 on the tested ARM path

Important:
- NCNN backend is NOT used by this build.
- No fallback to Lanczos replaces the ARM AI engine.
- No extra denoise / contrast / sharpen filter is applied after ARM AI processing.
- RetinaFace scans uploaded images automatically for UI selection.
- GFPGAN is applied only to faces explicitly selected by the user.
- Images with no face, or with no selected face, follow the proven V2.0.2 ARM path unchanged.
- Auto face detection uses a separate CPU helper and does not compete with the ARM CUDA render worker.
- FaceXLib ParseNet is bundled; no face model is downloaded into Program Files at runtime.
- If Face Protect fails, the ARM result is preserved.
- CMYK/ICC conversion is export-only.
"@ | Set-Content ".\dist\NiyomsilAIEnhancer\ARM_CORE_BUILD_PROOF.txt" -Encoding utf8

Get-Item $exe | Format-List FullName,Length
Get-Item $packedModel | Format-List FullName,Length
Get-Item $packedGfpgan | Format-List FullName,Length
Get-Item $packedRetina | Format-List FullName,Length
Get-Item $packedParser | Format-List FullName,Length
Write-Host "ARM CORE MODEL VERIFIED: $packedHash"
Write-Host "FACE MODELS VERIFIED: $packedGfpganHash / $packedRetinaHash / $packedParserHash"

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

    $installer = ".\release\Niyomsil-Design-AI-Enhancer-Setup-v2.1.1.exe"
    if (-not (Test-Path $installer)) {
        throw "Installer compile reported success but the expected EXE is missing."
    }

    $installerHash = (Get-FileHash -Algorithm SHA256 $installer).Hash.ToLower()
    "$installerHash  Niyomsil-Design-AI-Enhancer-Setup-v2.1.1.exe" |
        Set-Content ".\release\Niyomsil-Design-AI-Enhancer-Setup-v2.1.1.exe.sha256.txt" -Encoding ascii

    Get-Item $installer | Format-List FullName,Length
    Write-Host "Installer SHA256: $installerHash"
}

Write-Host "V2.1.2 ARM CORE + FACE POPUP PORTRAIT BUILD COMPLETE"
