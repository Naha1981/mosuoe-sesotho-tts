$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.venv')) {
    uv venv
}

. .\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env from .env.example. Add GEMINI_API_KEY, then run this script again.'
    exit 0
}

uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
