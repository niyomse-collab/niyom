# Reassemble the official NiyomSilp Design v1.0.1 installer from GitHub Release parts.
# Designed for 64-bit Windows PowerShell 5.1+; no Python or extra tools required.
# Verifies final SHA-256 before reporting success.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$name = "NiyomSilp-Design-v1-Setup.exe"
$sourcePrefix = "$name.part"
$checksumFile = Join-Path $dir "$name.sha256.txt"
$destination = Join-Path $dir $name
if (-not (Test-Path -LiteralPath $checksumFile -PathType Leaf)) {
    throw "Missing installer SHA-256 checksum file: $checksumFile"
}
$parts = @(Get-ChildItem -LiteralPath $dir -Filter "$sourcePrefix*" -File | Sort-Object Name)
if ($parts.Count -lt 2) {
    throw "Missing installer parts; download every .partXX file from the same v1.0.1 release."
}
for ($i = 0; $i -lt $parts.Count; $i++) {
    $expectedName = "{0}.part{1:D2}" -f $name, ($i + 1)
    if ($parts[$i].Name -cne $expectedName) {
        throw "Part order is incomplete. Expected $expectedName but found $($parts[$i].Name)"
    }
}
$expected = ((Get-Content -LiteralPath $checksumFile -TotalCount 1) -split '\s+')[0].ToLowerInvariant()
if ($expected -notmatch '^[a-f0-9]{64}$') {
    throw "Malformed installer SHA-256 checksum file."
}
$stream = [System.IO.File]::Open($destination, [System.IO.FileMode]::Create,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    foreach ($part in $parts) {
        Write-Host ("Combining {0} ({1} bytes)..." -f $part.Name, $part.Length)
        $reader = [System.IO.File]::OpenRead($part.FullName)
        try { $reader.CopyTo($stream) }
        finally { $reader.Dispose() }
    }
}
finally { $stream.Dispose() }
$actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) {
    Remove-Item -LiteralPath $destination -Force
    throw "Checksum mismatch; the reassembled installer was deleted. Download all parts again."
}
Write-Host "SHA-256 verified. Installer ready:" $destination -ForegroundColor Green
Write-Host "Install normally; the program does not require Python on the user's PC."
