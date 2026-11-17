[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCandidateSha
)

$ErrorActionPreference = 'Stop'

function Normalize-AccountName([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    $value = $Value.Trim()
    if ($value -ieq 'LocalSystem') { return 'nt authority\system' }
    if ($value -match '^(?i)\.\\(.+)$') {
        return (($env:COMPUTERNAME + '\' + $Matches[1]).ToLowerInvariant())
    }
    return $value.ToLowerInvariant()
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$currentAccount = Normalize-AccountName $currentIdentity

$runnerServices = @()
try {
    $runnerServices = @(
        Get-CimInstance -ClassName Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -like 'actions.runner.*' }
    )
} catch {
    $runnerServices = @()
}

$serviceRecords = @()
foreach ($service in $runnerServices) {
    $serviceAccount = Normalize-AccountName ([string]$service.StartName)
    $servicePath = [Environment]::ExpandEnvironmentVariables([string]$service.PathName)
    $exeMatch = [regex]::Match($servicePath, '^\s*"(?<exe>[^"]+\.exe)"', 'IgnoreCase')
    if (-not $exeMatch.Success) {
        $exeMatch = [regex]::Match($servicePath, '^\s*(?<exe>.+?\.exe)(?:\s|$)', 'IgnoreCase')
    }

    $runnerRoot = ''
    $runnerMetadataPresent = $false
    if ($exeMatch.Success) {
        $serviceExe = $exeMatch.Groups['exe'].Value
        $binDirectory = Split-Path -Parent $serviceExe
        $runnerRoot = Split-Path -Parent $binDirectory
        $runnerMetadata = Join-Path $runnerRoot '.runner'
        if (Test-Path -LiteralPath $runnerMetadata -PathType Leaf) {
            try {
                $null = Get-Content -LiteralPath $runnerMetadata -Raw | ConvertFrom-Json -ErrorAction Stop
                $runnerMetadataPresent = $true
            } catch {
                $runnerMetadataPresent = $false
            }
        }
    }

    $serviceRecords += [ordered]@{
        running = ([string]$service.State -ieq 'Running')
        start_mode = [string]$service.StartMode
        account_matches_interactive_user = (
            $serviceAccount -ne '' -and $serviceAccount -eq $currentAccount
        )
        runner_metadata_present = $runnerMetadataPresent
    }
}

$runnerProcesses = @()
try {
    $runnerProcesses = @(
        Get-CimInstance -ClassName Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction Stop
    )
} catch {
    $runnerProcesses = @()
}

$uninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{4B6A2C18-0F95-47EE-A6B8-0F2DD7B0CE11}_is1'
$installPath = ''
$installedExePresent = $false
$buildProofPresent = $false
$installedSourceSha = $null
try {
    $uninstall = Get-ItemProperty -LiteralPath ('HKCU:\' + $uninstallSubkey) -ErrorAction Stop
    $installPath = [string]$uninstall.'Inno Setup: App Path'
    if (-not [string]::IsNullOrWhiteSpace($installPath)) {
        $installedExePresent = Test-Path -LiteralPath (Join-Path $installPath 'NiyomsilAIEnhancer.exe') -PathType Leaf
        $proofPath = Join-Path $installPath 'BUILD_PROOF.txt'
        $buildProofPresent = Test-Path -LiteralPath $proofPath -PathType Leaf
        if ($buildProofPresent) {
            $proofText = Get-Content -LiteralPath $proofPath -Raw
            $proofMatch = [regex]::Match($proofText, '(?im)^Source commit:\s*([0-9a-f]{40})\s*$')
            if ($proofMatch.Success) {
                $installedSourceSha = $proofMatch.Groups[1].Value.ToLowerInvariant()
            }
        }
    }
} catch {
    $installPath = ''
}

$manifestPresent = $false
$manifestShapeValid = $false
$manifestPath = ''
$localAppData = [Environment]::GetFolderPath('LocalApplicationData')
if (-not [string]::IsNullOrWhiteSpace($localAppData)) {
    $manifestPath = Join-Path $localAppData 'NiyomSilp\V211-FourAI-QA\manifest.json'
    $manifestPresent = Test-Path -LiteralPath $manifestPath -PathType Leaf
    if ($manifestPresent) {
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
            $actualNames = @($manifest.PSObject.Properties.Name | Sort-Object)
            $expectedNames = @('anime4k', 'real_cugan', 'real_esrgan', 'waifu2x' | Sort-Object)
            $manifestShapeValid = (
                $actualNames.Count -eq 4 -and
                ($actualNames -join '|') -ceq ($expectedNames -join '|')
            )
        } catch {
            $manifestShapeValid = $false
        }
    }
}

$nvidiaSmiPath = $null
$command = Get-Command 'nvidia-smi.exe' -ErrorAction SilentlyContinue
if ($null -eq $command) {
    $command = Get-Command 'nvidia-smi' -ErrorAction SilentlyContinue
}
if ($null -ne $command) {
    $nvidiaSmiPath = $command.Source
}
if ([string]::IsNullOrWhiteSpace($nvidiaSmiPath)) {
    $candidate = Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $nvidiaSmiPath = $candidate
    }
}

$targetGpu = $null
if (-not [string]::IsNullOrWhiteSpace($nvidiaSmiPath)) {
    try {
        $gpuLines = @(& $nvidiaSmiPath '--query-gpu=name,driver_version,memory.total,memory.free' '--format=csv,noheader,nounits' 2>$null)
        if ($LASTEXITCODE -eq 0) {
            foreach ($line in $gpuLines) {
                $parts = ([string]$line -split ',') | ForEach-Object { $_.Trim() }
                if ($parts.Count -ge 4 -and $parts[0] -match '(?i)GTX\s*1660\s*Ti') {
                    $total = 0
                    $free = 0
                    if ([int]::TryParse($parts[2], [ref]$total) -and [int]::TryParse($parts[3], [ref]$free)) {
                        $targetGpu = [ordered]@{
                            name_match = $true
                            driver_version = $parts[1]
                            memory_total_mib = $total
                            memory_free_mib = $free
                        }
                        break
                    }
                }
            }
        }
    } catch {
        $targetGpu = $null
    }
}

$vulkanLoaderPath = Join-Path $env:WINDIR 'System32\vulkan-1.dll'
$vulkanLoaderPresent = Test-Path -LiteralPath $vulkanLoaderPath -PathType Leaf

$expectedShaMatches = $null
if (-not [string]::IsNullOrWhiteSpace($ExpectedCandidateSha)) {
    $expectedShaMatches = (
        -not [string]::IsNullOrWhiteSpace($installedSourceSha) -and
        $installedSourceSha -eq $ExpectedCandidateSha.ToLowerInvariant()
    )
}

$runningService = @($serviceRecords | Where-Object { $_.running })
$serviceAccountMatch = @($runningService | Where-Object { $_.account_matches_interactive_user }).Count -gt 0
$runnerProcessPresent = $runnerProcesses.Count -gt 0
$blockers = @()
if ($runningService.Count -eq 0 -and -not $runnerProcessPresent) { $blockers += 'runner_service_or_listener_not_running' }
if ($runningService.Count -gt 0 -and -not $serviceAccountMatch) { $blockers += 'runner_service_account_differs_from_interactive_user' }
if (-not $installedExePresent -or -not $buildProofPresent) { $blockers += 'candidate_installation_not_found_in_current_user_hkcu' }
if ($null -eq $expectedShaMatches -and [string]::IsNullOrWhiteSpace($ExpectedCandidateSha)) {
    # An omitted expected SHA is diagnostic-only; the installed proof is still reported.
} elseif ($expectedShaMatches -ne $true) {
    $blockers += 'installed_candidate_source_sha_mismatch'
}
if (-not $manifestPresent -or -not $manifestShapeValid) { $blockers += 'four_engine_manifest_missing_or_invalid_shape_in_current_user_localappdata' }
if ($null -eq $targetGpu) { $blockers += 'gtx_1660_ti_not_found_by_nvidia_smi' }
if (-not $vulkanLoaderPresent) { $blockers += 'vulkan_loader_dll_not_found_in_system32' }

$status = if ($blockers.Count -eq 0) {
    'local_preflight_ready_github_labels_still_require_confirmation'
} else {
    'blocked_or_incomplete'
}

$report = [ordered]@{
    schema_version = 1
    status = $status
    blockers = $blockers
    read_only = $true
    network_accessed = $false
    model_downloaded = $false
    customer_artwork_accessed = $false
    files_written = $false
    services_changed = $false
    current_user_profile_checked = $true
    runner_services = $serviceRecords
    runner_listener_process_present = $runnerProcessPresent
    required_github_runner_labels = @('self-hosted', 'Windows', 'X64', 'niyom-shop-gpu')
    github_runner_labels_verified_locally = $false
    candidate_installed_for_current_user = ($installedExePresent -and $buildProofPresent)
    installed_candidate_source_sha = $installedSourceSha
    expected_candidate_sha_matches = $expectedShaMatches
    four_engine_manifest_present = $manifestPresent
    four_engine_manifest_shape_valid = $manifestShapeValid
    manifest_hashes_verified = $false
    target_gpu = $targetGpu
    vulkan_loader_file_present = $vulkanLoaderPresent
    note = 'This script does not verify GitHub labels, model/executable SHA256, native inference, adapter use or image quality. It only identifies local runner/profile prerequisites.'
}

$report | ConvertTo-Json -Depth 8
if ($blockers.Count -eq 0) { exit 0 } else { exit 1 }
