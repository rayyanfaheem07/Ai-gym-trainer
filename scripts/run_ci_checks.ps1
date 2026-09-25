<#
.SYNOPSIS
    Runs local CI/CD automated quality gates for Real-Time AI Gym Trainer on Windows.
#>
$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Real-Time AI Gym Trainer — Windows Local CI Quality Gate Pipeline   " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Secret & Sensitive File Scan
Write-Host "`n[Gate 1/4] Checking untracked sensitive environment files..." -ForegroundColor Yellow
$trackedEnv = git ls-files .env .env.local
if ($trackedEnv) {
    Write-Error "FAILED: Sensitive environment files are tracked in Git: $trackedEnv"
}
Write-Host "No sensitive files tracked." -ForegroundColor Green

# 2. Backend Ruff & Pytest
Write-Host "`n[Gate 2/4] Running backend linter (Ruff) and Pytest with coverage..." -ForegroundColor Yellow
& .venv\Scripts\ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& .venv\Scripts\pytest --cov=backend/app --cov=ai --cov-report=term --cov-fail-under=80
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Backend quality & coverage passed." -ForegroundColor Green

# 3. Frontend Quality Gates
Write-Host "`n[Gate 3/4] Running frontend tests, typecheck, lint, and build..." -ForegroundColor Yellow
Push-Location frontend
try {
    npm test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    npm run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    npm run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
Write-Host "Frontend quality & build passed." -ForegroundColor Green

# 4. Docker Compose Validation
Write-Host "`n[Gate 4/4] Validating Docker Compose configuration syntax..." -ForegroundColor Yellow
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Docker compose configuration is valid." -ForegroundColor Green

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host "  ALL LOCAL CI QUALITY GATES PASSED SUCCESSFULLY!                      " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
