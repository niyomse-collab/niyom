# Standalone TEST installer build. Keeps every existing main/stable release intact.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = (Get-Command python -ErrorAction Stop).Source
& $python -m venv ".venv-independent-build"
if ($LASTEXITCODE -ne 0) { throw "Could not create independent virtualenv" }
$py = ".\.venv-independent-build\Scripts\python.exe"

& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed" }
& $py -m pip install torch==2.11.0+cu128 torchvision==0.26.0+cu128 --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw "PyTorch CUDA install failed" }
& $py -m pip install -r requirements_arm_core.txt
if ($LASTEXITCODE -ne 0) { throw "Image runtime install failed" }
& $py "tools\generate_brand_assets.py"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path ".\assets\app_icon.ico")) {
  throw "Could not generate NiyomSilp app icon"
}

New-Item -ItemType Directory -Force -Path ".\models\face" | Out-Null
$items = @(
  @{
    Url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
    Rel="models\RealESRGAN_x4plus.pth"
    Sha="4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
  },
  @{
    Url="https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
    Rel="models\face\GFPGANv1.4.pth"
    Sha="e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad"
  },
  @{
    Url="https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth"
    Rel="models\face\detection_Resnet50_Final.pth"
    Sha="6d1de9c2944f2ccddca5f5e010ea5ae64a39845a86311af6fdf30841b0a5a16d"
  }
)
foreach ($item in $items) {
  if (Test-Path $item.Rel) {
    $cachedHash = (Get-FileHash -Algorithm SHA256 $item.Rel).Hash.ToLower()
    if ($cachedHash -ne $item.Sha) { Remove-Item -Force $item.Rel }
  }
  if (-not (Test-Path $item.Rel)) { Invoke-WebRequest -Uri $item.Url -OutFile $item.Rel }
  $hash = (Get-FileHash -Algorithm SHA256 $item.Rel).Hash.ToLower()
  if ($hash -ne $item.Sha) { throw "Model hash mismatch: $($item.Rel)" }
}

& $py -m py_compile run_independent_test.py independent_core\desktop_adapter.py independent_core\gui_test.py independent_core\engine.py independent_core\icc_external_export.py independent_core\icc_library.py independent_core\print_output.py
if ($LASTEXITCODE -ne 0) { throw "Syntax validation failed" }

# Only remove TEST build outputs; never touch dist/NiyomsilAIEnhancer.
Remove-Item ".\dist\NiyomSilpCoreTEST" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path ".\release-independent" | Out-Null
& $py -m PyInstaller --noconfirm --clean ".\NiyomSilpIndependentTest.spec"
if ($LASTEXITCODE -ne 0) { throw "Independent PyInstaller build failed" }

$folder = ".\dist\NiyomSilpCoreTEST"
$exe = Join-Path $folder "NiyomSilpCoreTEST.exe"
if (-not (Test-Path $exe)) { throw "Independent EXE missing" }
foreach ($item in $items) {
  $packed = Join-Path $folder ("_internal\" + $item.Rel)
  if (-not (Test-Path $packed)) { throw "Missing packaged model: $($item.Rel)" }
  $packedHash = (Get-FileHash -Algorithm SHA256 $packed).Hash.ToLower()
  if ($packedHash -ne $item.Sha) { throw "Packaged model hash differs: $($item.Rel)" }
}
$legacy = Join-Path $folder "_internal\signprint_ai\arm_core_adapter.py"
if (Test-Path $legacy) { throw "The ARM adapter must not be frozen in independent TEST" }

@"
NIYOMSIL INDEPENDENT CORE TEST 0.1
Separate installer identity and installation folder, preserving stable NiyomSilp releases.
GUI file signprint_ai/app_v2.py is unchanged (frozen hash).
AI wrapper independent_core/engine.py + independent_core/desktop_adapter.py.
Model RealESRGAN_x4plus.pth verified by SHA256.
Face module optional, never replaces AI result on error.
ICC ZIPs are external; Adobe ICC files are NOT bundled.
No claim that NVIDIA GPU, shop ICC calibration or large-format output has been verified.
"@ | Set-Content (Join-Path $folder "NIYOMSIL_TEST_BUILD_PROOF.txt") -Encoding UTF8

$env:NIYOMSIL_INDEPENDENT_SMOKE = "1"
try {
  $proc = Start-Process -FilePath (Resolve-Path $exe).Path -Wait -PassThru
  if ($proc.ExitCode -ne 0) { throw "Packaged EXE import smoke failed: $($proc.ExitCode)" }
} finally {
  Remove-Item Env:NIYOMSIL_INDEPENDENT_SMOKE -ErrorAction SilentlyContinue
}
$env:NIYOMSIL_INDEPENDENT_INFER_SMOKE = "1"
try {
  $proc = Start-Process -FilePath (Resolve-Path $exe).Path -Wait -PassThru
  if ($proc.ExitCode -ne 0) { throw "Packaged EXE real-model inference smoke failed: $($proc.ExitCode)" }
} finally {
  Remove-Item Env:NIYOMSIL_INDEPENDENT_INFER_SMOKE -ErrorAction SilentlyContinue
}

$programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
$innoCandidates = @(
  (Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"),
  (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$iscc = $innoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 missing" }
& $iscc ".\installer_independent_test.iss"
if ($LASTEXITCODE -ne 0) { throw "Test installer build failed" }
$setup = ".\release-independent\NiyomSilp-Independent-Core-TEST-Setup-v0.1.0.exe"
if (-not (Test-Path $setup)) { throw "Independent Setup EXE missing" }
$sha = (Get-FileHash -Algorithm SHA256 $setup).Hash.ToLower()
"$sha  NiyomSilp-Independent-Core-TEST-Setup-v0.1.0.exe" | Set-Content "$setup.sha256.txt" -Encoding ascii
Write-Host "Independent installer compiled: $sha"
