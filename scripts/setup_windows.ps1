<#
.SYNOPSIS
    TrailEar Windows setup script
.DESCRIPTION
    Sets up the development environment on Windows 10/11.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    # 1. Check Python
    Write-Step "Checking Python 3.11+"
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Error "Python not found on PATH. Install Python 3.11+ and try again."
        exit 1
    }
    $ver = python --version 2>&1
    Write-Ok $ver

    # 2. Create venv
    Write-Step "Creating virtual environment"
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
        Write-Ok "Created .venv"
    } else {
        Write-Ok ".venv already exists"
    }

    # Activate venv
    . .\.venv\Scripts\Activate.ps1
    Write-Ok "Activated .venv"

    # 3. Install package
    Write-Step "Installing trailear[dev]"
    pip install -e ".[dev]" --quiet
    Write-Ok "Installed"

    # 4. Check Ollama
    Write-Step "Checking Ollama"
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Write-Ok "Ollama found, pulling qwen2.5:3b"
        ollama pull qwen2.5:3b
    } else {
        Write-Warn "Ollama not found. Install from https://ollama.ai and pull qwen2.5:3b"
        Write-Warn "The mock LLM will be used in the meantime."
    }

    # 5. Fetch models
    Write-Step "Fetching models (BirdNET + Piper voice)"
    python scripts/fetch_models.py

    # 6. Seed species DB
    Write-Step "Seeding species database"
    python scripts/seed_species_db.py

    # 7. Run tests
    Write-Step "Running tests"
    pytest -q

    # 8. Print next steps
    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "  Setup complete! Try these commands:" -ForegroundColor Green
    Write-Host "    python -m trailear file data/samples/sample.wav" -ForegroundColor White
    Write-Host "    python -m trailear serve" -ForegroundColor White
    Write-Host "=" * 60 -ForegroundColor Green
} finally {
    Pop-Location
}
