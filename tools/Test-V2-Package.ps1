param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [ValidateSet("imports", "ui", "face", "processing")][string]$Mode = "processing",
    [int]$TimeoutSeconds = 600
)
$ErrorActionPreference = "Stop"
$exePath = (Resolve-Path $Exe).Path
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outputPath = (Resolve-Path $OutputDir).Path
$flags = @{
    imports = "NIYOMSIL_IMPORT_SMOKE";
    ui = "NIYOMSIL_UI_SMOKE";
    face = "NIYOMSIL_FACE_BACKEND_SMOKE";
    processing = "NIYOMSIL_PACKAGE_SMOKE"
}
$flag = $flags[$Mode]
Set-Item "Env:$flag" "1"
$env:NIYOMSIL_SMOKE_OUTPUT = $outputPath
try {
    $process = Start-Process -FilePath $exePath -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill()
        throw "Packaged $Mode test timed out"
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) {
        $errorFile = Join-Path $outputPath "package-smoke-error.txt"
        if (Test-Path $errorFile) { Get-Content $errorFile }
        throw "Packaged $Mode test failed: $($process.ExitCode)"
    }
    if ($Mode -eq "processing") {
        $reportFile = Join-Path $outputPath "package-smoke.json"
        if (-not (Test-Path $reportFile)) { throw "Missing processing report" }
        $report = Get-Content $reportFile -Raw | ConvertFrom-Json
        if (-not $report.passed -or $report.release.channel -ne "v2") { throw "Invalid processing report" }
        Get-Content $reportFile
    }
    Write-Host "Packaged $Mode test passed"
} finally {
    Remove-Item "Env:$flag" -ErrorAction SilentlyContinue
    Remove-Item Env:NIYOMSIL_SMOKE_OUTPUT -ErrorAction SilentlyContinue
}
