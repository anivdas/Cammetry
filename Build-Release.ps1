$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$Version = '0.6.0-dev'
$Venv = Join-Path $PSScriptRoot '.build-venv'
$Python = Join-Path $Venv 'Scripts\python.exe'

Write-Host ""
Write-Host "Cammetry Release Builder v$Version" -ForegroundColor Cyan
Write-Host "This builds the Windows app, portable EXE, and Setup installer." -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $Python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & py -3.12 -m venv $Venv
        if ($LASTEXITCODE -ne 0) {
            & py -3 -m venv $Venv
            if ($LASTEXITCODE -ne 0) { throw 'Python could not create the build environment.' }
        }
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) { throw 'Python 3 was not found. Install Python 3.12 or newer and run this again.' }
        & python -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw 'Python could not create the build environment.' }
    }
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }

$IconPng = Join-Path $PSScriptRoot 'assets\app.png'
$IconIco = Join-Path $PSScriptRoot 'assets\app.ico'
if (-not (Test-Path $IconIco)) {
    & $Python -c "from PIL import Image; Image.open(r'$IconPng').convert('RGBA').save(r'$IconIco', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate the Windows icon.' }
}

$FfmpegDir = Join-Path $PSScriptRoot 'ffmpeg_bin'
$FfmpegExe = Join-Path $FfmpegDir 'ffmpeg.exe'
$FfprobeExe = Join-Path $FfmpegDir 'ffprobe.exe'
$FfmpegBuild = 'n7.1-62-gb168ed9b14'
$FfmpegRelease = 'autobuild-2024-12-31-13-02'
$FfmpegAsset = "ffmpeg-$FfmpegBuild-win64-gpl-7.1.zip"
$FfmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/$FfmpegRelease/$FfmpegAsset"

# Always stage the pinned runtime from its immutable release URL for reproducible
# official/test packages. Do not consume BtbN's moving master/latest aliases.
Write-Host "Staging pinned Windows FFmpeg runtime: $FfmpegBuild" -ForegroundColor Yellow
$FfmpegZip = Join-Path $env:TEMP 'Cammetry-ffmpeg.zip'
$FfmpegExtract = Join-Path $env:TEMP 'Cammetry-ffmpeg'
Remove-Item -Recurse -Force $FfmpegExtract -ErrorAction SilentlyContinue
Remove-Item -Force $FfmpegZip -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $FfmpegDir -ErrorAction SilentlyContinue
Invoke-WebRequest -Uri $FfmpegUrl -OutFile $FfmpegZip -UseBasicParsing
Expand-Archive -Path $FfmpegZip -DestinationPath $FfmpegExtract -Force
$DownloadedFfmpeg = Get-ChildItem -Path $FfmpegExtract -Filter ffmpeg.exe -Recurse | Select-Object -First 1
$DownloadedFfprobe = Get-ChildItem -Path $FfmpegExtract -Filter ffprobe.exe -Recurse | Select-Object -First 1
if (-not $DownloadedFfmpeg -or -not $DownloadedFfprobe) { throw 'Pinned FFmpeg archive did not contain ffmpeg.exe and ffprobe.exe.' }
New-Item -ItemType Directory -Force $FfmpegDir | Out-Null
Copy-Item $DownloadedFfmpeg.FullName $FfmpegExe -Force
Copy-Item $DownloadedFfprobe.FullName $FfprobeExe -Force

$FfmpegVersionLine = (& $FfmpegExe -hide_banner -version | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or $FfmpegVersionLine -notmatch [regex]::Escape($FfmpegBuild)) {
    throw "Unexpected FFmpeg runtime. Expected $FfmpegBuild, got: $FfmpegVersionLine"
}
$FfmpegEncoders = (& $FfmpegExe -hide_banner -encoders 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw 'Pinned FFmpeg could not enumerate encoders.' }
if ($FfmpegEncoders -notmatch 'libx264') { throw 'Pinned FFmpeg does not expose required CPU libx264 encoding.' }
if ($FfmpegEncoders -notmatch 'h264_nvenc') { Write-Warning 'Pinned FFmpeg does not expose h264_nvenc; NVIDIA users will use another validated encoder or CPU x264.' }
Write-Host "Validated FFmpeg runtime: $FfmpegVersionLine" -ForegroundColor Green

Set-Content -Path (Join-Path $FfmpegDir 'SOURCE.txt') -Encoding UTF8 -Value @(
    'FFmpeg Windows binaries from BtbN/FFmpeg-Builds',
    "Pinned build: $FfmpegBuild",
    "Release: $FfmpegRelease",
    $FfmpegUrl,
    'Cammetry runtime-tests hardware encoders and automatically falls back to CPU x264 when needed.',
    'FFmpeg is distributed under its own license. See THIRD_PARTY_NOTICES.md.'
)
Remove-Item -Recurse -Force $FfmpegExtract -ErrorAction SilentlyContinue
Remove-Item -Force $FfmpegZip -ErrorAction SilentlyContinue

Remove-Item -Recurse -Force build, dist-installer, dist-portable, release -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force release | Out-Null

Write-Host "Building installer application folder..." -ForegroundColor Yellow
& $Python -m PyInstaller `
  --noconfirm --clean --windowed --onedir `
  --name Cammetry `
  --icon assets\app.ico `
  --version-file version_info.txt `
  --collect-all imageio_ffmpeg `
  --collect-all cv2 `
  --collect-all PIL `
  --add-data "ffmpeg_bin;ffmpeg_bin" `
  --add-data "assets;assets" `
  --distpath dist-installer `
  cammetry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installer-folder build failed.' }

Write-Host "Building portable single-file EXE..." -ForegroundColor Yellow
& $Python -m PyInstaller `
  --noconfirm --clean --windowed --onefile `
  --name Cammetry-Portable `
  --icon assets\app.ico `
  --version-file version_info.txt `
  --collect-all imageio_ffmpeg `
  --collect-all cv2 `
  --collect-all PIL `
  --add-data "ffmpeg_bin;ffmpeg_bin" `
  --add-data "assets;assets" `
  --distpath dist-portable `
  cammetry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller portable build failed.' }

Copy-Item "dist-portable\Cammetry-Portable.exe" "release\Cammetry-Portable-v$Version.exe"

$PortableFolder = "release\Cammetry-Portable-v$Version"
New-Item -ItemType Directory -Force $PortableFolder | Out-Null
Copy-Item "dist-portable\Cammetry-Portable.exe" "$PortableFolder\Cammetry.exe"
Copy-Item README.md, LICENSE, PRIVACY.md, CHANGELOG.md, THIRD_PARTY_NOTICES.md, TRADEMARKS.md "$PortableFolder\"
Compress-Archive -Path "$PortableFolder\*" -DestinationPath "release\Cammetry-Portable-v$Version.zip" -Force
Remove-Item -Recurse -Force $PortableFolder

$MakeNsis = @(
    "$env:ProgramFiles\NSIS\makensis.exe",
    "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $MakeNsis) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "NSIS not found. Installing the open-source NSIS compiler with winget..." -ForegroundColor Yellow
        & winget install --id NSIS.NSIS -e --source winget --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'winget could not install NSIS.' }
        $MakeNsis = @(
            "$env:ProgramFiles\NSIS\makensis.exe",
            "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
        ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    }
}

if (-not $MakeNsis) {
    throw 'NSIS could not be located. Install NSIS and run Build-Release.ps1 again.'
}

Write-Host "Building Windows Setup installer..." -ForegroundColor Yellow
Push-Location "installer"
try {
    & $MakeNsis /WX "Cammetry.nsi"
    if ($LASTEXITCODE -ne 0) { throw 'NSIS installer build failed or produced a warning treated as an error.' }
} finally { Pop-Location }

Write-Host ""
Write-Host "Release build complete." -ForegroundColor Green
Get-ChildItem release | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host ""
Write-Host "Recommended public download: Cammetry-Setup-v$Version.exe" -ForegroundColor Cyan
