param(
  [Parameter(Mandatory=$true)][string]$InputImage,
  [Parameter(Mandatory=$true)][string]$WaifuExe,
  [string]$OutputDir = "waifu2x-v2-evidence"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$inputFull = (Resolve-Path $InputImage).Path
$exeFull = (Resolve-Path $WaifuExe).Path
if (-not (Test-Path $inputFull -PathType Leaf)) { throw "Input image missing" }
if (-not (Test-Path $exeFull -PathType Leaf)) { throw "Waifu2x executable missing" }
$env:SIGNPRINT_WAIFU2X_EXE = $exeFull
$env:PYTHONPATH = $repo
New-Item -ItemType Directory -Force $OutputDir | Out-Null
$outFull = (Resolve-Path $OutputDir).Path
python -m pip install pillow numpy opencv-python
if ($LASTEXITCODE -ne 0) { throw "Python dependency install failed" }
$env:NIYOMSIL_INPUT = $inputFull
$env:NIYOMSIL_OUTPUT = Join-Path $outFull "waifu2x-v2-output.png"
@'
import json, os, traceback
from pathlib import Path
from PIL import Image
from signprint_ai.pipeline import PrintEnhancementPipeline
from signprint_ai.processing import EnhanceSettings
out=Path(os.environ["NIYOMSIL_OUTPUT"])
try:
    pipeline=PrintEnhancementPipeline()
    if not pipeline.waifu2x.available:
        raise RuntimeError("V2 did not detect Waifu2x executable")
    result=pipeline.process(
        os.environ["NIYOMSIL_INPUT"], str(out),
        EnhanceSettings(ai_scale=2, dpi=300, v1_baseline=True),
        ai_engine="waifu2x"
    )
    with Image.open(out) as image:
        assert image.size == (result["original_size"][0]*2, result["original_size"][1]*2)
        assert image.mode in ("RGB","RGBA")
    assert result["ai_engine"] == "waifu2x" and result["ai_available"]
    print(json.dumps({"status":"PASS",**result},ensure_ascii=False,default=str))
except Exception:
    traceback.print_exc()
    raise
'@ | Set-Content -Encoding utf8 (Join-Path $outFull "run_v2_waifu2x.py")
python (Join-Path $outFull "run_v2_waifu2x.py") *> (Join-Path $outFull "integration.log")
$exit = $LASTEXITCODE
Get-Content (Join-Path $outFull "integration.log")
if ($exit -ne 0) { throw "V2 + Waifu2x failed. See $outFull\integration.log" }
Write-Host "PASS: V2 + Waifu2x output: $env:NIYOMSIL_OUTPUT"
