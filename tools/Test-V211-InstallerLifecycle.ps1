$ErrorActionPreference = 'Stop'
$repoRoot = (Get-Location).Path
$tempRoot = Join-Path $env:RUNNER_TEMP ("v211-installer-lifecycle-" + [Guid]::NewGuid().ToString('N'))
$fixtureDir = Join-Path $tempRoot 'fixture'
$compiledDir = Join-Path $tempRoot 'compiled'
$originalLocalAppData = $env:LOCALAPPDATA
$profileRoot = Join-Path $tempRoot 'profile\AppData\Local'
$env:LOCALAPPDATA = $profileRoot
$cacheRoot = Join-Path $profileRoot 'NiyomSilp\V211-FourAI-QA'
$testGuid = [Guid]::NewGuid().ToString('D').ToUpperInvariant()
$testRegistryKey = 'Software\NiyomSilp\V211ExperimentalLifecycle-' + $testGuid.Replace('-', '')
$testRegistryPath = 'HKCU:\' + $testRegistryKey
$testUninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{' + $testGuid + '}_is1'
$startMenuRoot = Join-Path $tempRoot 'StartMenu'
$desktopRoot = Join-Path $tempRoot 'Desktop'
$completeMarker = Join-Path $cacheRoot 'setup-complete.flag'
$pendingMarker = Join-Path $cacheRoot 'setup-pending.flag'

New-Item -ItemType Directory -Force -Path $fixtureDir, $compiledDir, $profileRoot, $startMenuRoot, $desktopRoot | Out-Null

function Reset-FixtureCache {
    if (Test-Path -LiteralPath $cacheRoot) {
        Remove-Item -LiteralPath $cacheRoot -Recurse -Force
    }
    Remove-Item Env:V211_FIXTURE_FAIL -ErrorAction SilentlyContinue
}

function Invoke-FixtureSetup([string]$InstallDir, [string]$Tasks, [string]$LogName) {
    $arguments = @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        "/DIR=$InstallDir",
        "/LOG=$(Join-Path $tempRoot $LogName)"
    )
    if ($Tasks) {
        $arguments += "/TASKS=$Tasks"
    }
    $process = Start-Process -FilePath $setupExe -ArgumentList $arguments -Wait -PassThru
    if ($null -eq $process) {
        throw "Inno Setup did not return a process for $LogName"
    }
    return [int]$process.ExitCode
}

function Invoke-FixtureUninstall([string]$InstallDir) {
    $uninstaller = Join-Path $InstallDir 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
        $process = Start-Process -FilePath $uninstaller -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
        ) -Wait -PassThru
        if ($null -eq $process -or $process.ExitCode -ne 0) {
            throw "Synthetic silent uninstall failed for $InstallDir"
        }
    }
}

try {
    $csharp = @'
using System;
using System.IO;

internal static class Program {
    private static int Main(string[] args) {
        string local = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        if (String.IsNullOrEmpty(local)) return 41;

        string cache = Path.Combine(local, "NiyomSilp", "V211-FourAI-QA");
        string pending = Path.Combine(cache, "setup-pending.flag");
        string complete = Path.Combine(cache, "setup-complete.flag");
        string appDir = AppDomain.CurrentDomain.BaseDirectory;
        bool provision = Array.IndexOf(args, "--provision-v211-four-ai") >= 0;

        if (provision) {
            Directory.CreateDirectory(cache);
            File.WriteAllText(Path.Combine(appDir, "provision-invoked.flag"), "synthetic");
            if (!File.Exists(pending)) return 42;
            if (Environment.GetEnvironmentVariable("V211_FIXTURE_FAIL") == "1") return 23;
            File.Delete(pending);
            File.WriteAllText(complete, "synthetic installer lifecycle only");
            return 0;
        }

        File.WriteAllText(Path.Combine(appDir, "editor-launched.flag"), "unexpected");
        return 0;
    }
}
'@
    $sourcePath = Join-Path $tempRoot 'Fixture.cs'
    [System.IO.File]::WriteAllText($sourcePath, $csharp, [System.Text.UTF8Encoding]::new($false))

    $compilerCandidates = @(
        (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
        (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
    )
    $csc = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $csc) {
        $command = Get-Command csc.exe -ErrorAction SilentlyContinue
        if ($command) { $csc = $command.Source }
    }
    if (-not $csc) {
        throw 'A .NET Framework C# compiler is required for the local synthetic installer fixture.'
    }

    $fixtureExe = Join-Path $fixtureDir 'NiyomsilAIEnhancer.exe'
    & $csc /nologo /target:exe "/out:$fixtureExe" $sourcePath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $fixtureExe -PathType Leaf)) {
        throw 'Could not compile the synthetic NiyomSilp installer fixture executable.'
    }

    $isccCommand = Get-Command ISCC.exe -ErrorAction Stop
    $iscc = $isccCommand.Source
    $installerSource = Join-Path $repoRoot 'installer_v211_experimental.iss'
    $iss = Get-Content -LiteralPath $installerSource -Raw
    $oldFilesLine = 'Source: "dist\NiyomsilAIEnhancer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs'
    $newFilesLine = 'Source: "' + $fixtureDir + '\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs'
    if (-not $iss.Contains($oldFilesLine)) {
        throw 'Could not identify the production installer [Files] source for a fixture-only substitution.'
    }
    $iss = $iss.Replace($oldFilesLine, $newFilesLine)

    # Keep every installer side effect inside this synthetic profile. Inno's
    # {localappdata} constant is resolved by Setup itself, so replacing only
    # the PowerShell environment variable would NOT isolate these paths.
    $oldDataRoot = '{localappdata}\NiyomSilp\V211-FourAI-QA'
    if (-not $iss.Contains($oldDataRoot)) {
        throw 'Could not identify the production per-user model-cache root.'
    }
    $escapedCacheRoot = $cacheRoot.Replace("'", "''")
    $iss = $iss.Replace($oldDataRoot, $escapedCacheRoot)

    $oldRegistryKey = 'Software\NiyomSilp\V211Experimental'
    if (-not $iss.Contains($oldRegistryKey)) {
        throw 'Could not identify the production experimental registry key.'
    }
    $iss = $iss.Replace($oldRegistryKey, $testRegistryKey)

    $oldAppIdLine = 'AppId={{4B6A2C18-0F95-47EE-A6B8-0F2DD7B0CE11}'
    if (-not $iss.Contains($oldAppIdLine)) {
        throw 'Could not identify the production experimental AppId.'
    }
    $iss = $iss.Replace($oldAppIdLine, ('AppId={{' + $testGuid + '}'))

    $oldAppNameLine = '#define MyAppName "NiyomSilp Design V2.1.1 EXPERIMENTAL"'
    if (-not $iss.Contains($oldAppNameLine)) {
        throw 'Could not identify the production experimental app name.'
    }
    $iss = $iss.Replace(
        $oldAppNameLine,
        ('#define MyAppName "NiyomSilp V211 Lifecycle Test ' + $testGuid + '"')
    )
    $iss = $iss.Replace('{autoprograms}', $startMenuRoot)
    $iss = $iss.Replace('{autodesktop}', $desktopRoot)

    $oldIconLine = 'SetupIconFile=assets\app_icon.ico'
    $newIconLine = 'SetupIconFile=' + (Join-Path $repoRoot 'assets\app_icon.ico')
    if (-not $iss.Contains($oldIconLine)) {
        throw 'Could not identify the production installer icon path.'
    }
    $iss = $iss.Replace($oldIconLine, $newIconLine)
    $testIss = Join-Path $tempRoot 'installer_v211_lifecycle_test.iss'
    [System.IO.File]::WriteAllText($testIss, $iss, [System.Text.UTF8Encoding]::new($false))

    & $iscc "/O$compiledDir" $testIss
    if ($LASTEXITCODE -ne 0) {
        throw 'Inno Setup could not compile the production installer script with the synthetic app fixture.'
    }
    $outputLine = [regex]::Split($iss, '\r?\n') | Where-Object { $_.StartsWith('OutputBaseFilename=') } | Select-Object -First 1
    if (-not $outputLine) {
        throw 'The production installer output filename could not be read.'
    }
    $setupBaseName = $outputLine.Substring('OutputBaseFilename='.Length).Trim()
    $setupExe = Join-Path $compiledDir ($setupBaseName + '.exe')
    if (-not (Test-Path -LiteralPath $setupExe -PathType Leaf)) {
        throw 'Synthetic lifecycle installer executable was not produced.'
    }

    # Case 1: no task selected. Setup must not provision, create markers, or launch
    # the GUI in silent mode. Silent uninstall must preserve the dedicated cache.
    Reset-FixtureCache
    $noConsentDir = Join-Path $tempRoot 'install-no-consent'
    $exitCode = Invoke-FixtureSetup $noConsentDir '' 'no-consent-setup.log'
    if ($exitCode -ne 0) { throw "No-consent installer returned $exitCode instead of 0." }
    if ((Test-Path $pendingMarker) -or (Test-Path $completeMarker) -or
        (Test-Path (Join-Path $noConsentDir 'provision-invoked.flag'))) {
        throw 'No-consent install unexpectedly started four-engine provisioning.'
    }
    New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
    $noConsentSentinel = Join-Path $cacheRoot 'keep-after-silent-uninstall.txt'
    Set-Content -LiteralPath $noConsentSentinel -Value 'synthetic user data'
    Invoke-FixtureUninstall $noConsentDir
    if (-not (Test-Path -LiteralPath $noConsentSentinel -PathType Leaf)) {
        throw 'Silent uninstall removed the dedicated model cache without consent.'
    }

    # Case 2: explicit installer task selected. The fixture must see the fresh
    # pending marker, then replace it with a completion marker before Setup exits.
    Reset-FixtureCache
    $successDir = Join-Path $tempRoot 'install-consented'
    $exitCode = Invoke-FixtureSetup $successDir 'installfourai' 'consented-setup.log'
    if ($exitCode -ne 0) { throw "Consented fixture install returned $exitCode instead of 0." }
    if (-not (Test-Path -LiteralPath $completeMarker -PathType Leaf) -or
        (Test-Path -LiteralPath $pendingMarker)) {
        throw 'Consented install did not publish the completion marker after clearing pending.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $successDir 'provision-invoked.flag'))) {
        throw 'The selected installer task did not execute the provisioning command.'
    }
    if (Test-Path -LiteralPath (Join-Path $successDir 'editor-launched.flag')) {
        throw 'Silent installer unexpectedly launched the editor.'
    }
    $successSentinel = Join-Path $cacheRoot 'keep-after-silent-uninstall.txt'
    Set-Content -LiteralPath $successSentinel -Value 'synthetic user data'
    Invoke-FixtureUninstall $successDir
    if (-not (Test-Path -LiteralPath $successSentinel -PathType Leaf)) {
        throw 'Silent uninstall removed consented models without a separate cleanup choice.'
    }

    # Case 3: the selected task fails. Setup must return non-zero, keep the
    # pending gate, publish no success marker and never launch the editor.
    Reset-FixtureCache
    $env:V211_FIXTURE_FAIL = '1'
    $failureDir = Join-Path $tempRoot 'install-failed'
    $exitCode = Invoke-FixtureSetup $failureDir 'installfourai' 'failed-setup.log'
    Remove-Item Env:V211_FIXTURE_FAIL -ErrorAction SilentlyContinue
    if ($exitCode -eq 0) {
        throw 'A failed four-engine setup returned success from the installer.'
    }
    if (-not (Test-Path -LiteralPath $pendingMarker -PathType Leaf) -or
        (Test-Path -LiteralPath $completeMarker)) {
        throw 'Failed setup did not retain pending state and suppress the success marker.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $failureDir 'provision-invoked.flag'))) {
        throw 'Failure fixture did not reach the selected provisioning command.'
    }
    if (Test-Path -LiteralPath (Join-Path $failureDir 'editor-launched.flag')) {
        throw 'Failed setup unexpectedly launched the editor.'
    }
    Invoke-FixtureUninstall $failureDir

    Write-Output 'Inno Setup lifecycle passed: no-consent, explicit-consent success, fail-closed setup failure, and silent-uninstall cache preservation. Synthetic fixture only; no model downloads or customer files.'
}
finally {
    Remove-Item Env:V211_FIXTURE_FAIL -ErrorAction SilentlyContinue
    Reset-FixtureCache
    if (Test-Path -LiteralPath $testRegistryPath) {
        Remove-Item -LiteralPath $testRegistryPath -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $testUninstallKey) {
        Remove-Item -LiteralPath $testUninstallKey -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($originalLocalAppData) {
        $env:LOCALAPPDATA = $originalLocalAppData
    } else {
        Remove-Item Env:LOCALAPPDATA -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
