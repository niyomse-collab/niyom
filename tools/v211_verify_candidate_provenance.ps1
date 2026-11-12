$ErrorActionPreference = 'Stop'

$proofPath = '.\dist\NiyomsilAIEnhancer\BUILD_PROOF.txt'
$installer = '.\release\NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe'
$sumsPath = '.\release\SHA256SUMS.txt'

foreach ($required in @($proofPath, $installer, $sumsPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Candidate provenance input missing: $required"
    }
}

$proofLines = @(Get-Content -LiteralPath $proofPath)
$sourceLine = $proofLines |
    Where-Object { $_ -match '^Source commit:[ ]*([0-9a-f]{40})[ ]*$' } |
    Select-Object -First 1
if (-not $sourceLine) {
    throw 'BUILD_PROOF does not contain a valid source commit.'
}
$proofCommit = [regex]::Match($sourceLine, '[0-9a-f]{40}').Value.ToLowerInvariant()
$checkoutSha = (git rev-parse HEAD).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $checkoutSha -notmatch '^[0-9a-f]{40}$') {
    throw 'Could not identify the checked-out candidate source commit.'
}
if ($proofCommit -ne $checkoutSha) {
    throw 'BUILD_PROOF source commit does not match the checked-out source commit.'
}

$expectedHeadSha = $env:V211_EXPECTED_HEAD_SHA
if ([string]::IsNullOrWhiteSpace($expectedHeadSha)) {
    throw 'Expected PR head/source SHA was not supplied to candidate verification.'
}
$expectedHeadSha = $expectedHeadSha.Trim().ToLowerInvariant()
if ($expectedHeadSha -notmatch '^[0-9a-f]{40}$') {
    throw 'Expected PR head/source SHA is invalid.'
}
if ($checkoutSha -ne $expectedHeadSha -or $proofCommit -ne $expectedHeadSha) {
    throw 'BUILD_PROOF source commit does not match the expected PR head SHA.'
}

$expectedBaseSha = $env:V211_EXPECTED_BASE_SHA
if (-not [string]::IsNullOrWhiteSpace($expectedBaseSha)) {
    $expectedBaseSha = $expectedBaseSha.Trim().ToLowerInvariant()
    if ($expectedBaseSha -notmatch '^[0-9a-f]{40}$') {
        throw 'Pull request base SHA is invalid.'
    }
    git cat-file -e "${expectedBaseSha}^{commit}"
    if ($LASTEXITCODE -ne 0) {
        throw 'Pull request base commit is missing from the candidate checkout.'
    }
    git merge-base --is-ancestor $expectedBaseSha $checkoutSha
    if ($LASTEXITCODE -ne 0) {
        throw 'Pull request head must contain the current base commit before candidate packaging.'
    }
}

$headerLine = $proofLines |
    Where-Object { $_.Trim() -ceq 'NIYOMSIL DESIGN v2 - VERIFIED INSTALLER BUILD PROOF' } |
    Select-Object -First 1
if (-not $headerLine) {
    throw 'BUILD_PROOF is not a V2 channel build.'
}
$versionLine = $proofLines |
    Where-Object { $_ -match '^Version:[ ]*2[.]1[.]1-beta[.][0-9]+[ ]*$' } |
    Select-Object -First 1
if (-not $versionLine) {
    throw 'BUILD_PROOF version is not a V2.1.1 beta candidate.'
}

$verified = @()
foreach ($line in Get-Content -LiteralPath $sumsPath) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$') {
        throw 'SHA256SUMS contains a malformed entry.'
    }
    $expected = $Matches[1].ToLowerInvariant()
    $name = $Matches[2].Trim()
    if ([IO.Path]::GetFileName($name) -ne $name) {
        throw 'SHA256SUMS contains a non-local filename.'
    }
    $file = Join-Path '.\release' $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw 'Installer slice listed in SHA256SUMS is missing.'
    }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Installer slice SHA256 mismatch: $name"
    }
    $verified += [ordered]@{
        file = $name
        sha256 = $actual
        bytes = (Get-Item -LiteralPath $file).Length
    }
}
if ($verified.Count -lt 2) {
    throw 'Disk-spanning installer must include Setup.exe and at least one verified data slice.'
}
if (-not ($verified.file -contains [IO.Path]::GetFileName($installer))) {
    throw 'Setup.exe is not covered by SHA256SUMS.'
}

$installerHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$proofHash = (Get-FileHash -LiteralPath $proofPath -Algorithm SHA256).Hash.ToLowerInvariant()
$provenance = [ordered]@{
    schema_version = 1
    channel = 'v2.1.1-experimental'
    source_commit = $checkoutSha
    workflow_commit = $env:GITHUB_SHA
    workflow_run_id = $env:GITHUB_RUN_ID
    workflow_run_number = $env:GITHUB_RUN_NUMBER
    installer_file = [IO.Path]::GetFileName($installer)
    installer_sha256 = $installerHash
    installer_bytes = (Get-Item -LiteralPath $installer).Length
    build_proof_sha256 = $proofHash
    frozen_import_smoke = 'passed'
    installer_slice_sha256_verified = $true
    installer_slices = $verified
    release_published = $false
    real_four_engine_inference_verified = $false
    shop_gpu_qa_verified = $false
    quality_certified = $false
}
$provenance | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath '.\release\CANDIDATE_PROVENANCE.json' -Encoding utf8

Write-Output "Candidate provenance verified for source $checkoutSha."
