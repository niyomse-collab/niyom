[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCandidateSha
)

$ErrorActionPreference = 'Stop'

function Normalize-AccountName([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    $account = $Value.Trim()
    if ($account -ieq 'LocalSystem') { return 'nt authority\system' }
    if ($account -match '^\.\\(.+)$') {
        return (($env:COMPUTERNAME + '\' + $Matches[1]).ToLowerInvariant())
    }
    return $account.ToLowerInvariant()
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
    $exeMatch = [regex]::Match(
        $servicePath,
        '^\s*"(?<exe>[^"]+\.exe)"',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if (-not $exeMatch.Success) {
        $exeMatch = [regex]::Match(
            $servicePath,
            '^\s*(?<exe>.+?\.exe)(?:\s|$)',
            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
    }

    $runnerMetadataPresent = $false
    if ($exeMatch.Success) {
        $serviceExe = $exeMatch.Groups['exe'].Value
        $runnerRoot = Split-Path -Parent (Split-Path -Parent $serviceExe)
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
$runnerProcessOwnerVerifiedCount = 0
$runnerProcessAccountMatchCount = 0
try {
    $runnerProcesses = @(
        Get-CimInstance -ClassName Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction Stop
    )
    foreach ($process in $runnerProcesses) {
        try {
            $owner = Invoke-CimMethod -InputObject $process -MethodName GetOwner -ErrorAction Stop
            if ($owner.ReturnValue -eq 0 -and -not [string]::IsNullOrWhiteSpace([string]$owner.User)) {
                $runnerProcessOwnerVerifiedCount++
                $ownerDomain = [string]$owner.Domain
                if ([string]::IsNullOrWhiteSpace($ownerDomain)) { $ownerDomain = $env:COMPUTERNAME }
                $processAccount = Normalize-AccountName ($ownerDomain + '\' + [string]$owner.User)
                if ($processAccount -eq $currentAccount) { $runnerProcessAccountMatchCount++ }
            }
        } catch {
            # Access denied or unknown ownership is not treated as a match.
        }
    }
} catch {
    $runnerProcesses = @()
}
$runnerProcessPresent = $runnerProcesses.Count -gt 0
$runnerProcessAccountsAllMatch = (
    $runnerProcessPresent -and
    $runnerProcessOwnerVerifiedCount -eq $runnerProcesses.Count -and
    $runnerProcessAccountMatchCount -eq $runnerProcesses.Count
)

$uninstallSubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{4B6A2C18-0F95-47EE-A6B8-0F2DD7B0CE11}_is1'
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
    # A missing HKCU uninstall record is reported as a failed preflight.
}

$manifestPresent = $false
$manifestShapeValid = $false
$localAppData = [Environment]::GetFolderPath('LocalApplicationData')
if (-not [string]::IsNullOrWhiteSpace($localAppData)) {
    $manifestPath = Join-Path $localAppData 'NiyomSilp\V211-FourAI-QA\manifest.json'
    $manifestPresent = Test-Path -LiteralPath $manifestPath -PathType Leaf
    if ($manifestPresent) {
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
            $actualNames = @($manifest.PSObject.Properties.Name | Sort-Object)
            $expectedNames = @('anime4k', 'real_cugan', 'real_esrgan', 'waifu2x')
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
$nvidiaCommand = Get-Command 'nvidia-smi.exe' -ErrorAction SilentlyContinue
if ($null -eq $nvidiaCommand) {
    $nvidiaCommand = Get-Command 'nvidia-smi' -ErrorAction SilentlyContinue
}
if ($null -ne $nvidiaCommand) {
    $nvidiaSmiPath = $nvidiaCommand.Source
}
if ([string]::IsNullOrWhiteSpace($nvidiaSmiPath)) {
    $nvidiaCandidate = Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'
    if (Test-Path -LiteralPath $nvidiaCandidate -PathType Leaf) {
        $nvidiaSmiPath = $nvidiaCandidate
    }
}

$targetGpuMatches = @()
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
                        $targetGpuMatches += [ordered]@{
                            name_match = $true
                            driver_version = $parts[1]
                            memory_total_mib = $total
                            memory_free_mib = $free
                            memory_reading_valid = ($total -gt 0 -and $free -ge 0 -and $free -le $total)
                            six_gib_capacity_verified = ($total -ge 5500)
                        }
                    }
                }
            }
        }
    } catch {
        $targetGpuMatches = @()
    }
}
$targetGpuMatchCount = $targetGpuMatches.Count
$targetGpu = if ($targetGpuMatchCount -eq 1) { $targetGpuMatches[0] } else { $null }
$targetGpuCapacityVerified = (
    $null -ne $targetGpu -and
    $targetGpu.memory_reading_valid -eq $true -and
    $targetGpu.six_gib_capacity_verified -eq $true
)

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
$serviceAccountsAllMatch = (
    $runningService.Count -gt 0 -and
    @($runningService | Where-Object { -not $_.account_matches_interactive_user }).Count -eq 0
)
$runningServiceMetadataAllPresent = (
    $runningService.Count -gt 0 -and
    @($runningService | Where-Object { -not $_.runner_metadata_present }).Count -eq 0
)
$blockers = @()
if ($runningService.Count -gt 0) {
    if (-not $serviceAccountsAllMatch) {
        $blockers += 'runner_service_account_differs_from_interactive_user'
    }
    if (-not $runningServiceMetadataAllPresent) {
        $blockers += 'running_runner_service_metadata_missing_or_invalid'
    }
    if (-not $runnerProcessPresent) {
        $blockers += 'runner_listener_not_running_for_active_service'
    }
}
elseif (-not $runnerProcessPresent) {
    $blockers += 'runner_service_or_listener_not_running'
}
if ($runnerProcessPresent -and -not $runnerProcessAccountsAllMatch) {
    $blockers += 'runner_listener_account_differs_or_cannot_be_verified'
}
if (-not $installedExePresent -or -not $buildProofPresent) {
    $blockers += 'candidate_installation_not_found_in_current_user_hkcu'
}
if ($null -ne $expectedShaMatches -and $expectedShaMatches -ne $true) {
    $blockers += 'installed_candidate_source_sha_mismatch'
}
if (-not $manifestPresent -or -not $manifestShapeValid) {
    $blockers += 'four_engine_manifest_missing_or_invalid_shape_in_current_user_localappdata'
}
if ($targetGpuMatchCount -eq 0) {
    $blockers += 'gtx_1660_ti_not_found_by_nvidia_smi'
} elseif ($targetGpuMatchCount -ne 1) {
    $blockers += 'gtx_1660_ti_adapter_count_not_exactly_one_by_nvidia_smi'
} elseif (-not $targetGpuCapacityVerified) {
    $blockers += 'gtx_1660_ti_vram_capacity_or_memory_reading_invalid'
}
if (-not $vulkanLoaderPresent) {
    $blockers += 'vulkan_loader_dll_not_found_in_system32'
}

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
    runner_service_count = $runnerServices.Count
    running_runner_service_count = $runningService.Count
    running_runner_service_accounts_all_match_interactive_user = $serviceAccountsAllMatch
    running_runner_service_metadata_all_present = $runningServiceMetadataAllPresent
    runner_listener_process_present = $runnerProcessPresent
    runner_listener_process_count = $runnerProcesses.Count
    runner_listener_owner_verified_count = $runnerProcessOwnerVerifiedCount
    runner_listener_account_match_count = $runnerProcessAccountMatchCount
    runner_listener_accounts_all_match_interactive_user = $runnerProcessAccountsAllMatch
    runner_listener_account_matches_interactive_user = $runnerProcessAccountsAllMatch
    required_github_runner_labels = @('self-hosted', 'Windows', 'X64', 'niyom-shop-gpu')
    github_runner_labels_verified_locally = $false
    candidate_installed_for_current_user = ($installedExePresent -and $buildProofPresent)
    installed_candidate_source_sha = $installedSourceSha
    expected_candidate_sha_matches = $expectedShaMatches
    four_engine_manifest_present = $manifestPresent
    four_engine_manifest_shape_valid = $manifestShapeValid
    manifest_hashes_verified = $false
    target_gpu_match_count = $targetGpuMatchCount
    target_gpu_capacity_verified = $targetGpuCapacityVerified
    target_gpu = $targetGpu
    vulkan_loader_file_present = $vulkanLoaderPresent
    note = 'This script does not verify GitHub labels, model/executable SHA256, native inference, adapter use or image quality. It only identifies local runner/profile prerequisites.'
}

$report | ConvertTo-Json -Depth 8
if ($blockers.Count -eq 0) { exit 0 } else { exit 1 }
