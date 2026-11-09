param(
    [switch]$SkipInstaller,
    [ValidateSet("v1", "v2")]
    [string]$Channel = "v1",
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:-beta\.[0-9]+)?$')]
    [string]$Version = "1.0.1"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Normalize the legacy V2 default before validating the workspace.
if ($Channel -eq "v2" -and $Version -eq "1.0.1") { $Version = "2.0.0-beta.1" }

# Never clean or replace files from a previously built/approved V1 checkout.
# V2 should be built in an independent clean workspace. Check BEFORE venv,
# metadata, model downloads or any build/release folder deletion.
if ($Channel -eq "v2") {
    $v1ReleaseFiles = @(Get-ChildItem ".\\release\\NiyomSilp-Design-v1-*" -File -ErrorAction SilentlyContinue)
    $v1Proof = ".\\dist\\NiyomsilAIEnhancer\\ARM_CORE_BUILD_PROOF.txt"
    $v1Metadata = ".\\build_info.json"
    $v1MetadataPresent = $false
    if (Test-Path $v1Metadata) {
        try {
            $priorBuildInfo = Get-Content $v1Metadata -Raw | ConvertFrom-Json
            $v1MetadataPresent = ($priorBuildInfo.channel -eq "v1")
        } catch {
            # Unknown metadata must not be deleted by an unrelated V2 build.
            throw "V2 build refused: pre-existing build_info.json cannot be verified. Use a clean V2 checkout."
        }
    }
    if ($v1ReleaseFiles.Count -gt 0 -or (Test-Path $v1Proof) -or $v1MetadataPresent) {
        throw "V2 build refused: V1 build files found in this workspace. Build V2 in a separate clean checkout so V1 remains untouched."
    }
}

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

# The shared script removes build/, dist/ and release/. Never let a V2 build
# erase an accepted V2 installer or an unknown workspace. Only a previous
# V2.1.1 candidate with matching build_info + BUILD_PROOF may be replaced.
if ($Channel -eq "v2") {
    & $python ".\\tools\\v211_build_workspace_guard.py" --root $PSScriptRoot --requested-version $Version
    if ($LASTEXITCODE -ne 0) {
        throw "V2 build refused: existing build outputs are not verified V2.1.1 candidate artifacts. Use a clean isolated checkout; accepted V1/V2 files were preserved."
    }
}

if (Test-Path ".venv-build") {
    Remove-Item ".venv-build" -Recurse -Force
}

& $python -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw "Could not create build venv" }

$py = ".\.venv-build\Scripts\python.exe"

$sourceCommit = (& git rev-parse HEAD).Trim()
@{ channel = $Channel; version = $Version; source_commit = $sourceCommit } |
    ConvertTo-Json | Set-Content ".\build_info.json" -Encoding utf8
$proofName = if ($Channel -eq "v2") { "BUILD_PROOF.txt" } else { "ARM_CORE_BUILD_PROOF.txt" }
$experimentalV211 = ($Channel -eq "v2" -and $Version -like "2.1.1*")
$installerScript = if ($experimentalV211) { ".\installer_v211_experimental.iss" } elseif ($Channel -eq "v2") { ".\installer_v2.iss" } else { ".\installer.iss" }
$installerName = if ($experimentalV211) { "NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe" } elseif ($Channel -eq "v2") { "NiyomSilp-Design-v2-Setup.exe" } else { "NiyomSilp-Design-v1-Setup.exe" }
$installerPrefix = [System.IO.Path]::GetFileNameWithoutExtension($installerName)

function Ensure-VerifiedDownload {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$ExpectedHash,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

    # A shared V2 workspace may already contain the accepted model files.
    # Reuse only exact known hashes; never overwrite a different stable model.
    if (Test-Path -LiteralPath $Path) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "Existing $Label path is not a regular file; refusing to replace it."
        }
        $existing = Get-Item -LiteralPath $Path
        if (($existing.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Existing $Label is a link; refusing to follow or replace it."
        }
        $existingHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingHash -ne $ExpectedHash.ToLowerInvariant()) {
            throw "Existing $Label SHA256 differs from the pinned model; refusing to overwrite the existing file."
        }
        Write-Host "Reusing existing verified ${Label}: $existingHash"
        return $existingHash
    }

    try {
        Invoke-WebRequest -Uri $Url -OutFile $Path
        $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $ExpectedHash.ToLowerInvariant()) {
            Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
            throw "Downloaded $Label SHA256 mismatch: $actualHash"
        }
        Write-Host "Downloaded and verified ${Label}: $actualHash"
        return $actualHash
    } catch {
        # Only a newly-created partial download can be removed here. Existing
        # files are checked and rejected before entering this block.
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

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

Write-Host "Verifying the exact RealESRGAN_x4plus model used by the V2 core..."
$modelUrl = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
$modelPath = ".\\models\\RealESRGAN_x4plus.pth"
$expectedModelHash = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"
$actualModelHash = Ensure-VerifiedDownload -Path $modelPath -Url $modelUrl -ExpectedHash $expectedModelHash -Label "RealESRGAN_x4plus"
Write-Host "MODEL SHA256 OK: $actualModelHash"

Write-Host "Verifying optional Face Protect models without replacing existing files..."
$faceModelDir = ".\\models\\face"

$gfpganUrl = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
$gfpganPath = Join-Path $faceModelDir "GFPGANv1.4.pth"
$expectedGfpganHash = "e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad"
$actualGfpganHash = Ensure-VerifiedDownload -Path $gfpganPath -Url $gfpganUrl -ExpectedHash $expectedGfpganHash -Label "GFPGANv1.4"

$retinaUrl = "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth"
$retinaPath = Join-Path $faceModelDir "detection_Resnet50_Final.pth"
$expectedRetinaHash = "6d1de9c2944f2ccddca5f5e010ea5ae64a39845a86311af6fdf30841b0a5a16d"
$actualRetinaHash = Ensure-VerifiedDownload -Path $retinaPath -Url $retinaUrl -ExpectedHash $expectedRetinaHash -Label "RetinaFace detector"
Write-Host "FACE MODELS VERIFIED: $actualGfpganHash / $actualRetinaHash"

Write-Host "Validating ARM core + optional face module imports..."
& $py -m py_compile run.py signprint_ai\app_v2.py signprint_ai\arm_core_adapter.py signprint_ai\face_module\__init__.py signprint_ai\face_module\face_protection.py signprint_ai\independent_core.py tools\generate_brand_assets.py
if ($LASTEXITCODE -ne 0) { throw "Python source validation failed" }

& $py -c "exec(open('pyi_rth_basicsr_compat.py', encoding='utf-8').read()); from signprint_ai.independent_core import RealESRGANEngine; from gfpgan.archs.gfpganv1_clean_arch import GFPGANv1Clean; from facexlib.utils.face_restoration_helper import FaceRestoreHelper; print('ARM + Face Protect imports OK')"
if ($LASTEXITCODE -ne 0) { throw "ARM/Face module import validation failed" }

Remove-Item build, dist, release -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Building V2 UI + ARM V2.2.8 PyTorch Core..."
& $py -m PyInstaller --noconfirm --clean ".\NiyomsilV2ArmCore.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ARM Core build failed" }

$exe = ".\dist\NiyomsilAIEnhancer\NiyomsilAIEnhancer.exe"
$packedModel = ".\dist\NiyomsilAIEnhancer\_internal\models\RealESRGAN_x4plus.pth"
$packedGfpgan = ".\dist\NiyomsilAIEnhancer\_internal\models\face\GFPGANv1.4.pth"
$packedRetina = ".\dist\NiyomsilAIEnhancer\_internal\models\face\detection_Resnet50_Final.pth"

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

@"
NIYOMSIL DESIGN $Channel - VERIFIED INSTALLER BUILD PROOF
Version: $Version
Source commit: $sourceCommit

UI:
- signprint_ai/app_v2.py
- Black/Red NiyomSilp Design $Channel interface

AI processing core:
- signprint_ai/independent_core.py
- signprint_ai/arm_core_adapter.py

ARM model:
- RealESRGAN_x4plus.pth
- SHA256: $expectedModelHash

Optional Face Protect models:
- GFPGANv1.4.pth
- SHA256: $expectedGfpganHash
- detection_Resnet50_Final.pth
- SHA256: $expectedRetinaHash

Runtime:
- PyTorch 2.11.0 + CUDA 12.8 wheels
- TorchVision 0.26.0
- CUDA preferred automatically on supported NVIDIA GPU
- FP32 on the tested ARM path

Important:
- NCNN backend is NOT used by this build.
- No fallback to Lanczos replaces the ARM AI engine.
- No extra denoise / contrast / sharpen filter is applied after ARM AI processing.
- Face Protection is OPTIONAL and defaults OFF.
- Model settings and pass order preserve the legacy compatibility contract.
- Shop-approved V1.0.7 quality is the baseline; GPU pixel parity is not independently certified.
- Third-party model names and credits are preserved in the bundled notices.
- AUTO / CPU / detected GPU selection is stored in each queued job.
- Preview zoom, 1:1, Fit and synchronized mouse pan are enabled.
- When enabled, GFPGAN/RetinaFace runs only as a post-ARM face layer.
- If Face Protect fails, the ARM result is preserved.
- CMYK/ICC conversion is export-only.
"@ | Set-Content ".\dist\NiyomsilAIEnhancer\$proofName" -Encoding utf8

Get-Item $exe | Format-List FullName,Length
Get-Item $packedModel | Format-List FullName,Length
Get-Item $packedGfpgan | Format-List FullName,Length
Get-Item $packedRetina | Format-List FullName,Length
Write-Host "ARM CORE MODEL VERIFIED: $packedHash"
Write-Host "FACE MODELS VERIFIED: $packedGfpganHash / $packedRetinaHash"

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
    if ($Channel -eq "v2") {
        & $iscc "/DMyAppVersion=$Version" $installerScript
    } else {
        & $iscc $installerScript
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
    }

    $installer = ".\release\$installerName"
    if (-not (Test-Path $installer)) {
        throw "Installer compile reported success but the expected EXE is missing."
    }

    $installerHash = (Get-FileHash -Algorithm SHA256 $installer).Hash.ToLower()
    "$installerHash  $installerName" |
        Set-Content ".\release\$installerName.sha256.txt" -Encoding ascii

    if ($Channel -eq "v2") {
        Get-ChildItem ".\release\$installerPrefix*" -File |
            Where-Object { $_.Extension -in ".exe", ".bin" } |
            ForEach-Object { "$((Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower())  $($_.Name)" } |
            Set-Content ".\release\SHA256SUMS.txt" -Encoding ascii
    }

    Get-Item $installer | Format-List FullName,Length
    Write-Host "Installer SHA256: $installerHash"
}

Write-Host "NIYOMSIL DESIGN $Channel BUILD COMPLETE"
