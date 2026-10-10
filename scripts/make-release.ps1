# Make the Windows download for a release: dist\Budget-Buddy-<version>-Windows.zip and its .sha256 file.
# The zip holds the built app (build-desktop.ps1), the installer and a plain-English READ ME FIRST.txt, so
# nobody needs Python or this repository to use it. The version comes from server\app\__init__.py.
# (docs/dev/release.md has the full checklist; .github/workflows/release.yml runs this for a v* tag.)
#
#   powershell -ExecutionPolicy Bypass -File scripts\make-release.ps1

. "$PSScriptRoot\paths.ps1"

function Read-Version($File) {
    $match = Select-String -Path $File -Pattern '__version__ = "([^"]+)"'
    if (-not $match) { throw "No __version__ in $File." }
    return $match.Matches[0].Groups[1].Value
}

$Version = Read-Version (Join-Path $ServerDir "app\__init__.py")
$DesktopVersion = Read-Version (Join-Path $DesktopDir "budget_buddy_desktop\__init__.py")
if ($Version -ne $DesktopVersion) {
    Write-Host "The Home Base is version $Version but the desktop app is $DesktopVersion. Make them match first." -ForegroundColor Yellow
    exit 1
}

$Name = "Budget-Buddy-$Version-Windows"
$Stage = Join-Path $RepoRoot "build\release\$Name"
$DistDir = Join-Path $RepoRoot "dist"
$Zip = Join-Path $DistDir "$Name.zip"
$Packaging = Join-Path $DesktopDir "packaging"

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force $Stage, $DistDir | Out-Null

& (Join-Path $PSScriptRoot "build-desktop.ps1") -Into $Stage
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Content -Path (Join-Path $Stage "Budget Buddy\version.txt") -Encoding ASCII -Value $Version
foreach ($file in "install.ps1", "Install Budget Buddy.bat", "Uninstall Budget Buddy.bat", "READ ME FIRST.txt") {
    Copy-Item (Join-Path $Packaging $file) $Stage
}

if (Test-Path $Zip) { Remove-Item -Force $Zip }
# Each file added by hand with "/" in its name: Windows PowerShell 5.1 (Compress-Archive and ZipFile alike) writes
# "\", which some unzip tools (and macOS) treat as part of the file name.
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::Open($Zip, [IO.Compression.ZipArchiveMode]::Create)
try {
    $base = Split-Path -Parent $Stage
    foreach ($file in Get-ChildItem -Recurse -File $Stage) {
        $entry = $file.FullName.Substring($base.Length + 1).Replace("\", "/")
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $entry,
            [IO.Compression.CompressionLevel]::Optimal)
    }
} finally {
    $archive.Dispose()
}
$Hash = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower()
Set-Content -Path "$Zip.sha256" -Encoding ASCII -Value "$Hash  $Name.zip"

Write-Host ""
Write-Host "Release ready: $Zip" -ForegroundColor Green
Write-Host "SHA-256: $Hash"
