[CmdletBinding()]
param(
    [ValidateRange(30, 900)]
    [int]$EngineTimeoutSeconds = 180,

    [ValidateRange(300, 7200)]
    [int]$ProcessTimeoutSeconds = 3600,

    [string]$OutputDirectory,

    [string]$ExpectedCandidateSha
)

$ErrorActionPreference = 'Stop'

function Stop-Preflight([int]$Code, [string]$Message) {
    Write-Host ('ERROR: ' + $Message) -ForegroundColor Red
    exit $Code
}

# Require an explicit, exact candidate identity on every invocation. This
# avoids a stale hard-coded SHA when a newer experimental candidate is built.
if ([string]::IsNullOrWhiteSpace($ExpectedCandidateSha) -or
    $ExpectedCandidateSha -notmatch '^[0-9a-fA-F]{40}$') {
    Stop-Preflight 3 'Pass -ExpectedCandidateSha with the exact 40-character Source commit from the installed candidate BUILD_PROOF.txt.'
}
$ExpectedCandidateSha = $ExpectedCandidateSha.ToLowerInvariant()

if ($env:OS -ne 'Windows_NT') {
    Stop-Preflight 2 'This diagnostic is supported only on Windows.'
}
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    Stop-Preflight 2 'LOCALAPPDATA is unavailable for the current Windows account.'
}

$uninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{4B6A2C18-0F95-47EE-A6B8-0F2DD7B0CE11}_is1'
try {
    $uninstall = Get-ItemProperty -LiteralPath ('HKCU:\' + $uninstallSubkey) -ErrorAction Stop
} catch {
    Stop-Preflight 3 'NiyomSilp V2.1.1 is not registered for the current Windows account.'
}

$installPath = [string]$uninstall.'Inno Setup: App Path'
if ([string]::IsNullOrWhiteSpace($installPath)) {
    Stop-Preflight 3 'The installed application path is missing from the current user registry.'
}
try {
    $installPath = [System.IO.Path]::GetFullPath($installPath)
} catch {
    Stop-Preflight 3 'The installed application path is invalid.'
}

$exe = Join-Path $installPath 'NiyomsilAIEnhancer.exe'
$proofPath = Join-Path $installPath 'BUILD_PROOF.txt'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or
    -not (Test-Path -LiteralPath $proofPath -PathType Leaf)) {
    Stop-Preflight 3 'The installed Candidate executable or BUILD_PROOF.txt is missing.'
}

$proofText = Get-Content -LiteralPath $proofPath -Raw
$proofMatch = [regex]::Match(
    $proofText,
    '(?im)^Source commit:\s*([0-9a-f]{40})\s*$'
)
if (-not $proofMatch.Success) {
    Stop-Preflight 3 'BUILD_PROOF.txt does not contain a valid Source commit.'
}
$installedSourceSha = $proofMatch.Groups[1].Value.ToLowerInvariant()
if ($installedSourceSha -ne $ExpectedCandidateSha) {
    Stop-Preflight 3 (
        'Candidate mismatch. This authorization is only for source ' +
        $ExpectedCandidateSha + '; installed source is ' + $installedSourceSha + '.'
    )
}

$manifestRoot = Join-Path $env:LOCALAPPDATA 'NiyomSilp\V211-FourAI-QA'
$manifestPath = Join-Path $manifestRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Stop-Preflight 4 'The verified four-engine manifest is missing in the current Windows profile.'
}
try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $actualNames = @($manifest.PSObject.Properties.Name | Sort-Object)
} catch {
    Stop-Preflight 4 'The four-engine manifest is not valid JSON.'
}
$expectedNames = @('anime4k', 'real_cugan', 'real_esrgan', 'waifu2x')
if ($actualNames.Count -ne 4 -or
    ($actualNames -join '|') -cne ($expectedNames -join '|')) {
    Stop-Preflight 4 'The manifest does not contain exactly the four expected engine entries.'
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        $desktop = $env:USERPROFILE
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $OutputDirectory = Join-Path $desktop ('NiyomSilp-V211-GPU-QA-' + $stamp)
}
try {
    $OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
} catch {
    Stop-Preflight 5 'The requested diagnostic output directory is invalid.'
}

# A caller-supplied folder may contain an earlier QA image or unrelated file.
# Never let the packaged diagnostic overwrite evidence in an existing folder.
if (Test-Path -LiteralPath $OutputDirectory -PathType Container) {
    try {
        $existingOutputEntry = Get-ChildItem -LiteralPath $OutputDirectory -Force -ErrorAction Stop |
            Select-Object -First 1
    } catch {
        Stop-Preflight 5 'The existing diagnostic output directory cannot be inspected safely.'
    }
    if ($null -ne $existingOutputEntry) {
        Stop-Preflight 5 'The diagnostic output directory must be new or empty; refusing to overwrite existing files.'
    }
}

$installPrefix = $installPath.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
$manifestRootFull = [System.IO.Path]::GetFullPath($manifestRoot)
$manifestPrefix = $manifestRootFull.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if ($OutputDirectory.Equals($installPath, [StringComparison]::OrdinalIgnoreCase) -or
    $OutputDirectory.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    $OutputDirectory.Equals($manifestRootFull, [StringComparison]::OrdinalIgnoreCase) -or
    $OutputDirectory.StartsWith($manifestPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    Stop-Preflight 5 'The output directory must be outside the application and installed model folders.'
}

try {
    [System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
} catch {
    Stop-Preflight 5 'The diagnostic output directory could not be created.'
}
$reportPath = Join-Path $OutputDirectory 'shop_gpu_diagnostic.json'
if (Test-Path -LiteralPath $reportPath) {
    Stop-Preflight 5 'The report already exists; choose a new output directory to avoid overwriting evidence.'
}

# Do not retain intermediate candidate images even if the interactive account
# has an optional private evidence-retention override set. Restore the caller's
# process environment immediately after the diagnostic child exits.
$evidenceVariable = 'NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR'
$oldEvidenceDirectory = [Environment]::GetEnvironmentVariable($evidenceVariable, 'Process')
$diagnosticProcess = $null
$diagnosticExitCode = $null
$processFailure = $null

try {
    [Environment]::SetEnvironmentVariable($evidenceVariable, $null, 'Process')

    $quotedManifest = '"' + $manifestPath.Replace('"', '\"') + '"'
    $quotedOutput = '"' + $OutputDirectory.Replace('"', '\"') + '"'
    $arguments = (
        '--diagnose-v211-four-ai --manifest ' + $quotedManifest +
        ' --output-dir ' + $quotedOutput +
        ' --timeout-seconds ' + $EngineTimeoutSeconds
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $exe
    $startInfo.WorkingDirectory = $installPath
    $startInfo.Arguments = $arguments
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    $diagnosticProcess = [System.Diagnostics.Process]::Start($startInfo)
    if ($null -eq $diagnosticProcess) {
        throw 'The packaged diagnostic process could not be started.'
    }

    $waitMilliseconds = [int]($ProcessTimeoutSeconds * 1000)
    if (-not $diagnosticProcess.WaitForExit($waitMilliseconds)) {
        $taskkill = Join-Path $env:WINDIR 'System32\taskkill.exe'
        if (Test-Path -LiteralPath $taskkill -PathType Leaf) {
            & $taskkill /PID $diagnosticProcess.Id /T /F 2>$null | Out-Null
        }
        throw ('The packaged diagnostic exceeded the overall timeout of ' +
            $ProcessTimeoutSeconds + ' seconds; the process tree was stopped.')
    }
    $diagnosticProcess.WaitForExit()
    $diagnosticExitCode = $diagnosticProcess.ExitCode
} catch {
    $processFailure = $_.Exception.Message
} finally {
    [Environment]::SetEnvironmentVariable(
        $evidenceVariable, $oldEvidenceDirectory, 'Process'
    )
    if ($null -ne $diagnosticProcess) {
        $diagnosticProcess.Dispose()
    }
}

if (-not [string]::IsNullOrWhiteSpace($processFailure)) {
    Write-Host ('ERROR: Local GPU diagnostic could not complete: ' + $processFailure) -ForegroundColor Red
    exit 5
}
if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
    Stop-Preflight 5 'The diagnostic did not produce shop_gpu_diagnostic.json. No acceptance is recorded.'
}
try {
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json -ErrorAction Stop
} catch {
    Stop-Preflight 5 'The generated shop_gpu_diagnostic.json is not valid JSON.'
}

$summary = [ordered]@{
    candidate_source_sha = $ExpectedCandidateSha
    diagnostic_exit_code = $diagnosticExitCode
    shop_gpu_acceptance_passed = ($report.shop_gpu_acceptance_passed -eq $true)
    all_four_native_cli_outputs_validated = (
        $report.all_four_native_cli_outputs_validated_on_both_synthetic_cases -eq $true
    )
    gtx_1660_ti_and_vulkan_detected = (
        $report.gtx_1660_ti_and_vulkan_environment_detected -eq $true
    )
    runtime_device_use_verified = ($report.runtime_device_use_verified -eq $true)
    runtime_vram_budget_passed = ($report.runtime_vram_budget_passed -eq $true)
    per_engine_runtime_device_use_verified = $report.per_engine_runtime_device_use_verified
    per_engine_native_cli_vram_budget_passed = $report.per_engine_native_cli_runtime_vram_budget_passed
    customer_artwork_used = ($report.customer_artwork_used -eq $true)
    network_accessed = ($report.network_accessed -eq $true)
    uploads_performed = ($report.uploads_performed -eq $true)
    report_path = $reportPath
}
$summary | ConvertTo-Json -Depth 6

if ($diagnosticExitCode -eq 0 -and $report.shop_gpu_acceptance_passed -eq $true) {
    Write-Host 'Shop GPU synthetic diagnostic passed its runtime gates. Visual and print quality remain unverified.'
    exit 0
}

Write-Warning 'Shop GPU acceptance did not pass. Keep V2 as the accepted output; attach shop_gpu_diagnostic.json for diagnosis.'
exit 1
