# Local-only Windows checks. Does not upload customer files or touch installed program.
param(
  [Parameter(Mandatory=$true)][string]$SampleImage,
  [Parameter(Mandatory=$true)][string]$ICCProfile,
  [string]$ModelFile = ".\models\RealESRGAN_x4plus.pth",
  [ValidateSet(2,4)][int]$Scale = 2,
  [ValidateRange(72,1200)][int]$DPI = 150,
  [string]$PythonExe = "python"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
  $image = (Resolve-Path -LiteralPath $SampleImage -ErrorAction Stop).Path
  $icc = (Resolve-Path -LiteralPath $ICCProfile -ErrorAction Stop).Path
  $model = (Resolve-Path -LiteralPath $ModelFile -ErrorAction Stop).Path
  $out = Join-Path $root "local-qa-results"
  New-Item -ItemType Directory -Path $out -Force | Out-Null
  Write-Host "Checking private shop ICC locally (no external upload)..."
  & $PythonExe "tools\run_shop_icc.py" --source $image --icc $icc --dpi $DPI --out (Join-Path $out "icc")
  $iccResult = $LASTEXITCODE
  if ($iccResult -ne 0) {
    Write-Warning "ICC check failed or incomplete (code $iccResult). The stable app is unchanged."
  }
  Write-Host "Checking NVIDIA CUDA GPU without any CPU fallback..."
  & $PythonExe "tools\run_gpu_parity.py" --source $image --model $model --scale $Scale --out (Join-Path $out "gpu")
  $gpuResult = $LASTEXITCODE
  if ($gpuResult -ne 0) {
    Write-Warning "GPU check failed or incomplete (code $gpuResult). The stable app is unchanged."
  }
  Write-Host "Local evidence: $out"
  if ($iccResult -ne 0 -or $gpuResult -ne 0) {
    throw "Checks incomplete: ICC=$iccResult GPU=$gpuResult. Do not switch production core."
  }
  Write-Host "Comparison checks PASS. Physical print and real-user GUI still need review."
} finally {
  Pop-Location
}
