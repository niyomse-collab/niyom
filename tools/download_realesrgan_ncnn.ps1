param(
    [string]$Destination = "$PSScriptRoot\..\tools"
)
$ErrorActionPreference = "Stop"
$repo = "xinntao/Real-ESRGAN"
Write-Host "Finding official Real-ESRGAN NCNN/Vulkan Windows release..."
$headers = @{"User-Agent"="SignPrint-AI-Builder"}
$releases = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/releases"
$asset = $null
foreach ($release in $releases) {
    foreach ($a in $release.assets) {
        if ($a.name -match "realesrgan-ncnn-vulkan.*windows.*\.zip$") {
            $asset = $a
            break
        }
    }
    if ($asset) { break }
}
if (-not $asset) {
    throw "Could not find a Windows realesrgan-ncnn-vulkan ZIP in official releases."
}
$dest = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$tmp = Join-Path $env:TEMP $asset.name
Write-Host "Downloading $($asset.name)..."
Invoke-WebRequest -Headers $headers -Uri $asset.browser_download_url -OutFile $tmp
$extract = Join-Path $env:TEMP "SignPrintAI_realesrgan_ncnn"
Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $tmp -DestinationPath $extract -Force
$exe = Get-ChildItem $extract -Recurse -Filter "realesrgan-ncnn-vulkan.exe" | Select-Object -First 1
if (-not $exe) { throw "Downloaded archive does not contain realesrgan-ncnn-vulkan.exe" }
Copy-Item $exe.FullName (Join-Path $dest "realesrgan-ncnn-vulkan.exe") -Force
$modelDir = Join-Path $exe.Directory.FullName "models"
if (Test-Path $modelDir) {
    Copy-Item $modelDir (Join-Path $dest "models") -Recurse -Force
}
# Copy runtime DLLs shipped by the official archive, if any.
Get-ChildItem $exe.Directory.FullName -File | Where-Object { $_.Extension -in ".dll" } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $dest $_.Name) -Force
}
Write-Host "Real-ESRGAN NCNN backend prepared in: $dest"
