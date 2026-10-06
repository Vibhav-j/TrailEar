<#
.SYNOPSIS
    TrailEar Offline Demo Script (Airplane Mode recording demo)
.DESCRIPTION
    Runs a sample audio WAV through the entire local offline pipeline:
    1. Reads 3s audio windows with 1s hop (FileSource).
    2. Runs open-weight bird classifier (BirdNET or deterministic mock).
    3. Debounces and deduplicates through DetectionManager (cooldown, min_consecutive hits).
    4. Voices detections through offline Piper TTS (or NullTTS fallback).
    5. Saves walk and individual sightings into SQLite (data/walks.sqlite).
    6. Generates a grounded, reflective field journal using local LLM / deterministic fallback.
    No network connection is used.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    # Determine python executable
    $py = "python"
    if (Test-Path ".\.venv\Scripts\python.exe") {
        $py = ".\.venv\Scripts\python.exe"
    }

    Write-Host "`n" -NoNewline
    Write-Host "=================================================================" -ForegroundColor DarkGreen
    Write-Host "      TrailEar Offline Demo -- Airplane Mode End-to-End Walk      " -ForegroundColor Green
    Write-Host "=================================================================" -ForegroundColor DarkGreen
    Write-Host "  Timestamp:    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    Write-Host "  Network:      OFFLINE (Local compute only)" -ForegroundColor Yellow
    Write-Host "  Sample audio: data/samples/sample.wav" -ForegroundColor Gray
    Write-Host "=================================================================`n" -ForegroundColor DarkGreen

    # Ensure species database exists
    if (-not (Test-Path "data/species.sqlite")) {
        Write-Host "Seeding local species database..." -ForegroundColor Cyan
        & $py scripts/seed_species_db.py
    }

    # Ensure sample WAV exists
    if (-not (Test-Path "data/samples/sample.wav")) {
        Write-Host "Generating synthetic sample audio..." -ForegroundColor Cyan
        & $py scripts/generate_test_wav.py
        Copy-Item "data/samples/test_tone.wav" "data/samples/sample.wav"
    }

    # Run the pocket walk pipeline on the sample WAV
    Write-Host "Running walk pipeline through audio sample in pocket mode...`n" -ForegroundColor Cyan
    & $py -m trailear walk --file data/samples/sample.wav --pocket

    Write-Host "`n=================================================================" -ForegroundColor DarkGreen
    Write-Host "  Demo complete! Full walk session persisted to data/walks.sqlite" -ForegroundColor Green
    Write-Host "=================================================================`n" -ForegroundColor DarkGreen
} finally {
    Pop-Location
}
