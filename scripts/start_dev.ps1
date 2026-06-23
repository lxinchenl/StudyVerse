$ErrorActionPreference = "Stop"

Write-Host "Starting Personalized Learning Multi-Agent System..."
Write-Host "Backend:  http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; if (-not (Test-Path .venv)) { python -m venv .venv }; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm install; npm run dev"

