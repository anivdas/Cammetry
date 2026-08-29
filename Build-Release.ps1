$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$Version = '0.5.0'
$Venv = Join-Path $PSScriptRoot '.build-venv'
$Python = Join-Path $Venv 'Scripts\python.exe'

Write-Host ""
Write-Host "Cammetry Release Builder v$Version" -ForegroundColor Cyan
Write-Host "This builds the Windows app, portable EXE, and Setup installer." -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $Python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        try { & py -3.12 -m venv $Venv }
        catch { & py -3 -m venv $Venv }
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) { throw 'Python 3 was not found. Install Python 3.12 or newer and run this again.' }
        & python -m venv $Venv
    }
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-build.txt

# Generate the Windows .ico from the project-owned PNG so the repository only
# needs one source icon asset. Pillow is installed by requirements-build.txt.
$IconPng = Join-Path $PSScriptRoot 'assets\app.png'
$IconIco = Join-Path $PSScriptRoot 'assets\app.ico'
if (-not (Test-Path $IconIco)) {
    & $Python -c "from PIL import Image; Image.open(r'$IconPng').convert('RGBA').save(r'$IconIco', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
}

# Bundle a full Windows FFmpeg build so fresh installations can use NVENC,
# Intel QSV, AMD AMF, and CPU x264 without requiring users to install FFmpeg.
$FfmpegDir = Join-Path $PSScriptRoot 'ffmpeg_bin'
$FfmpegExe = Join-Path $FfmpegDir 'ffmpeg.exe'
$FfprobeExe = Join-Path $FfmpegDir 'ffprobe.exe'
if (-not (Test-Path $FfmpegExe) -or -not (Test-Path $FfprobeExe)) {
    Write-Host "Downloading full Windows FFmpeg runtime..." -ForegroundColor Yellow
    $FfmpegUrl = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
    $FfmpegZip = Join-Path $env:TEMP 'Cammetry-ffmpeg.zip'
    $FfmpegExtract = Join-Path $env:TEMP 'Cammetry-ffmpeg'
    Remove-Item -Recurse -Force $FfmpegExtract -ErrorAction SilentlyContinue
    Remove-Item -Force $FfmpegZip -ErrorAction SilentlyContinue
    Invoke-WebRequest -Uri $FfmpegUrl -OutFile $FfmpegZip -UseBasicParsing
    Expand-Archive -Path $FfmpegZip -DestinationPath $FfmpegExtract -Force
    $DownloadedFfmpeg = Get-ChildItem -Path $FfmpegExtract -Filter ffmpeg.exe -Recurse | Select-Object -First 1
    $DownloadedFfprobe = Get-ChildItem -Path $FfmpegExtract -Filter ffprobe.exe -Recurse | Select-Object -First 1
    if (-not $DownloadedFfmpeg -or -not $DownloadedFfprobe) { throw 'Downloaded FFmpeg archive did not contain ffmpeg.exe and ffprobe.exe.' }
    New-Item -ItemType Directory -Force $FfmpegDir | Out-Null
    Copy-Item $DownloadedFfmpeg.FullName $FfmpegExe -Force
    Copy-Item $DownloadedFfprobe.FullName $FfprobeExe -Force
    Set-Content -Path (Join-Path $FfmpegDir 'SOURCE.txt') -Encoding UTF8 -Value @(
        'FFmpeg Windows binaries from BtbN/FFmpeg-Builds',
        $FfmpegUrl,
        'FFmpeg is distributed under its own license. See THIRD_PARTY_NOTICES.md.'
    )
    Remove-Item -Recurse -Force $FfmpegExtract -ErrorAction SilentlyContinue
    Remove-Item -Force $FfmpegZip -ErrorAction SilentlyContinue
}

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
  --distpath dist-installer `
  cammetry.py

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
  --distpath dist-portable `
  cammetry.py

Copy-Item "dist-portable\Cammetry-Portable.exe" "release\Cammetry-Portable-v$Version.exe"

$PortableFolder = "release\Cammetry-Portable-v$Version"
New-Item -ItemType Directory -Force $PortableFolder | Out-Null
Copy-Item "dist-portable\Cammetry-Portable.exe" "$PortableFolder\Cammetry.exe"
Copy-Item README.md, LICENSE, PRIVACY.md, CHANGELOG.md, FEATURE_PARITY.md, THIRD_PARTY_NOTICES.md "$PortableFolder\"
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
        $MakeNsis = @(
            "$env:ProgramFiles\NSIS\makensis.exe",
            "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
        ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    }
}

if (-not $MakeNsis) {
    throw 'NSIS could not be located. Install NSIS (winget install -e --id NSIS.NSIS) and run Build-Release.ps1 again.'
}

Write-Host "Building Windows Setup installer..." -ForegroundColor Yellow
Push-Location "installer"
try { & $MakeNsis "Cammetry.nsi" } finally { Pop-Location }

Write-Host ""
Write-Host "Release build complete." -ForegroundColor Green
Get-ChildItem release | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host ""
Write-Host "Recommended public download: Cammetry-Setup-v$Version.exe" -ForegroundColor Cyan
