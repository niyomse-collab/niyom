$ErrorActionPreference = "Stop"

# Execute the production Ensure-VerifiedDownload function in an isolated
# temporary directory. Invoke-WebRequest and Start-Sleep are replaced locally;
# this test performs no network access and never touches model/customer files.
$sourcePath = Join-Path (Split-Path -Parent $PSScriptRoot) "build_windows.ps1"
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $sourcePath, [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {
    throw "build_windows.ps1 has PowerShell parse errors."
}
$functionAst = $ast.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq "Ensure-VerifiedDownload"
}, $true)
if ($null -eq $functionAst) {
    throw "Could not locate production Ensure-VerifiedDownload function."
}

$script:experimentalV211 = $true
$script:downloadMode = ""
$script:requestCount = 0
$script:sleepCalls = @()
$script:payload = [System.Text.Encoding]::UTF8.GetBytes("verified synthetic payload")
$script:destinationToCreate = ""

function Invoke-WebRequest {
    param(
        [string]$Uri,
        [string]$OutFile,
        [int]$TimeoutSec
    )
    $script:requestCount++
    if ($script:downloadMode -eq "io-drop-once" -and $script:requestCount -eq 1) {
        throw [System.IO.IOException]::new(
            "Unable to read data from the transport connection: An existing connection was forcibly closed by the remote host."
        )
    }
    if ($script:downloadMode -eq "http-reset-once" -and $script:requestCount -eq 1) {
        throw [System.Net.Http.HttpRequestException]::new("connection reset by peer")
    }
    if ($script:downloadMode -eq "nontransient-io") {
        throw [System.IO.IOException]::new("disk full while writing response")
    }
    if ($script:downloadMode -eq "hash-mismatch") {
        [System.IO.File]::WriteAllBytes(
            $OutFile, [System.Text.Encoding]::UTF8.GetBytes("wrong synthetic payload")
        )
        return
    }
    [System.IO.File]::WriteAllBytes($OutFile, $script:payload)
    if ($script:downloadMode -eq "destination-race") {
        [System.IO.File]::WriteAllText($script:destinationToCreate, "preserve existing destination")
    }
}

function Start-Sleep {
    param([int]$Seconds)
    $script:sleepCalls += $Seconds
}

. ([scriptblock]::Create($functionAst.Extent.Text))

$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $expectedHash = [Convert]::ToHexString($sha.ComputeHash($script:payload)).ToLowerInvariant()
} finally {
    $sha.Dispose()
}

$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("niyom-v211-retry-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

function Reset-TestState([string]$Mode) {
    $script:downloadMode = $Mode
    $script:requestCount = 0
    $script:sleepCalls = @()
    $script:destinationToCreate = ""
}

function Assert-NoPartialFiles([string]$Directory) {
    $parts = @(Get-ChildItem -LiteralPath $Directory -Filter "*.part" -File -ErrorAction SilentlyContinue)
    if ($parts.Count -ne 0) {
        throw "Temporary .part file leaked from retry test: $($parts[0].FullName)"
    }
}

try {
    # The exact transport IOException from Candidate #744 must retry once,
    # then publish only the fully hash-verified bytes.
    $ioDir = Join-Path $testRoot "io-retry"
    New-Item -ItemType Directory -Path $ioDir -Force | Out-Null
    Reset-TestState "io-drop-once"
    $ioPath = Join-Path $ioDir "model.bin"
    $ioResult = Ensure-VerifiedDownload -Path $ioPath -Url "https://invalid.test/no-network" -ExpectedHash $expectedHash -Label "synthetic-io-model"
    if ($script:requestCount -ne 2 -or $script:sleepCalls.Count -ne 1 -or $script:sleepCalls[0] -ne 2) {
        throw "Transport IOException did not follow the expected one-retry/backoff path."
    }
    if ($ioResult -ne $expectedHash -or (Get-FileHash -LiteralPath $ioPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
        throw "Transport retry did not publish the expected verified payload."
    }
    Assert-NoPartialFiles $ioDir

    # HttpRequestException in the exception chain is also transient.
    $httpDir = Join-Path $testRoot "http-retry"
    New-Item -ItemType Directory -Path $httpDir -Force | Out-Null
    Reset-TestState "http-reset-once"
    $httpPath = Join-Path $httpDir "model.bin"
    $httpResult = Ensure-VerifiedDownload -Path $httpPath -Url "https://invalid.test/no-network" -ExpectedHash $expectedHash -Label "synthetic-http-model"
    if ($script:requestCount -ne 2 -or $script:sleepCalls.Count -ne 1) {
        throw "HttpRequestException did not retry exactly once."
    }
    if ($httpResult -ne $expectedHash) {
        throw "HttpRequestException retry returned an unexpected hash."
    }
    Assert-NoPartialFiles $httpDir

    # An unrelated IOException must fail immediately, without a retry.
    $diskDir = Join-Path $testRoot "nontransient"
    New-Item -ItemType Directory -Path $diskDir -Force | Out-Null
    Reset-TestState "nontransient-io"
    $diskPath = Join-Path $diskDir "model.bin"
    $diskFailed = $false
    try {
        Ensure-VerifiedDownload -Path $diskPath -Url "https://invalid.test/no-network" -ExpectedHash $expectedHash -Label "synthetic-disk-model" | Out-Null
    } catch {
        $diskFailed = $true
        if ($_.Exception.Message -notmatch "disk full") { throw }
    }
    if (-not $diskFailed -or $script:requestCount -ne 1 -or (Test-Path -LiteralPath $diskPath)) {
        throw "Non-transient IOException was retried or unexpectedly published."
    }
    Assert-NoPartialFiles $diskDir

    # A received body with a bad digest must never be retried.
    $hashDir = Join-Path $testRoot "hash-mismatch"
    New-Item -ItemType Directory -Path $hashDir -Force | Out-Null
    Reset-TestState "hash-mismatch"
    $hashPath = Join-Path $hashDir "model.bin"
    $hashFailed = $false
    try {
        Ensure-VerifiedDownload -Path $hashPath -Url "https://invalid.test/no-network" -ExpectedHash $expectedHash -Label "synthetic-hash-model" | Out-Null
    } catch {
        $hashFailed = $true
        if ($_.Exception.Message -notmatch "SHA256 mismatch") { throw }
    }
    if (-not $hashFailed -or $script:requestCount -ne 1 -or (Test-Path -LiteralPath $hashPath)) {
        throw "SHA256 mismatch was retried or published."
    }
    Assert-NoPartialFiles $hashDir

    # A destination created while the request is in flight must be preserved;
    # this is a publish/race failure, not a network retry.
    $raceDir = Join-Path $testRoot "destination-race"
    New-Item -ItemType Directory -Path $raceDir -Force | Out-Null
    Reset-TestState "destination-race"
    $racePath = Join-Path $raceDir "model.bin"
    $script:destinationToCreate = $racePath
    $raceFailed = $false
    try {
        Ensure-VerifiedDownload -Path $racePath -Url "https://invalid.test/no-network" -ExpectedHash $expectedHash -Label "synthetic-race-model" | Out-Null
    } catch {
        $raceFailed = $true
        if ($_.Exception.Message -notmatch "Destination appeared") { throw }
    }
    if (-not $raceFailed -or $script:requestCount -ne 1) {
        throw "Destination race was retried or unexpectedly accepted."
    }
    if ([System.IO.File]::ReadAllText($racePath) -ne "preserve existing destination") {
        throw "Destination race overwrote the pre-existing file."
    }
    Assert-NoPartialFiles $raceDir

    # A previously verified cache entry must be reused without a request.
    $cacheDir = Join-Path $testRoot "verified-cache"
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
    Reset-TestState "must-not-run"
    $cachePath = Join-Path $cacheDir "model.bin"
    [System.IO.File]::WriteAllBytes($cachePath, $script:payload)
    $cacheResult = Ensure-VerifiedDownload -Path $cachePath -Url "https://invalid.test/no-network" -ExpectedHash $expectedHash -Label "synthetic-cache-model"
    if ($script:requestCount -ne 0 -or $cacheResult -ne $expectedHash) {
        throw "Verified cache entry was not reused offline."
    }

    Write-Output "V2.1.1 download retry fault injection passed: transport retry, HTTP retry, non-transient IOException, SHA256 fail-closed, destination race preservation, verified offline cache reuse, and .part cleanup."
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}