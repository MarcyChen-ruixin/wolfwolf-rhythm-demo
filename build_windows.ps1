# Build Windows onedir package for Werewolf Rhythm Demo (GitHub Releases).
# Does not upload anywhere.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Installing build dependencies"
python -m pip install -r requirements.txt

Write-Host "==> Cleaning previous build output"
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "==> Running PyInstaller (onedir)"
python -m PyInstaller --noconfirm rhythm_game.spec

$exe = Join-Path $PSScriptRoot "dist\WerewolfRhythmDemo\WerewolfRhythmDemo.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: executable not found at $exe"
}

Write-Host ""
Write-Host "Build OK:"
Write-Host "  $exe"
Write-Host "Package this onedir folder for GitHub Releases (do not upload from this script)."
