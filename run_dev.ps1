param(
  [int]$Port=31101,
  [string]$Host='0.0.0.0'
)
Write-Host 'Activating venv...'
if (-not (Test-Path .venv/Scripts/Activate.ps1)) { Write-Error 'Virtual environment not found. Run python -m venv .venv first.'; exit 1 }
. .\.venv\Scripts\Activate.ps1

Write-Host 'Loading environment variables from .env (python-dotenv auto when code runs if implemented)'

$env:PYTHONPATH = (Resolve-Path .).Path
Write-Host "Starting Uvicorn on $Host:$Port"
python -m uvicorn main:app --host $Host --port $Port --reload
