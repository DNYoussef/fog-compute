# Wave 6 E2E Tests Execution Script (PowerShell)

param(
    [string]$TestGroup = "all"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Wave 6 E2E Tests - Authentication Flows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if axe-playwright is installed
Write-Host "Checking dependencies..." -ForegroundColor Yellow
try {
    $axeInstalled = npm list axe-playwright 2>&1 | Select-String "axe-playwright"
    if ($axeInstalled) {
        Write-Host "axe-playwright is installed" -ForegroundColor Green
    }
} catch {
    Write-Host "axe-playwright not found. Installing..." -ForegroundColor Yellow
    npm install --save-dev axe-playwright
}

# Check if backend is running
Write-Host "Checking backend..." -ForegroundColor Yellow
try {
    $backend = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction SilentlyContinue
    if ($backend.StatusCode -eq 200) {
        Write-Host "Backend is running on port 8000" -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Backend is not running on port 8000" -ForegroundColor Red
    Write-Host "Start backend with: cd backend; python -m uvicorn server.main:app --port 8000" -ForegroundColor Yellow
    exit 1
}

# Check if frontend is running
Write-Host "Checking frontend..." -ForegroundColor Yellow
try {
    $frontend = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -ErrorAction SilentlyContinue
    if ($frontend.StatusCode -eq 200) {
        Write-Host "Frontend is running on port 3000" -ForegroundColor Green
    }
} catch {
    Write-Host "WARNING: Frontend is not running on port 3000" -ForegroundColor Yellow
    Write-Host "Some tests may fail. Start frontend with: cd apps/control-panel; npm run dev" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Running Wave 6 E2E Tests" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

switch ($TestGroup) {
    "all" {
        Write-Host "Running all Wave 6 tests..." -ForegroundColor Yellow
        npx playwright test `
            tests/e2e/test_login_flow.spec.ts `
            tests/e2e/test_registration_flow.spec.ts `
            tests/e2e/test_protected_routes.spec.ts `
            --reporter=html,json,list
    }
    "login" {
        Write-Host "Running TEST-05: Login UI tests..." -ForegroundColor Yellow
        npx playwright test tests/e2e/test_login_flow.spec.ts --reporter=html,list
    }
    "register" {
        Write-Host "Running TEST-06: Registration UI tests..." -ForegroundColor Yellow
        npx playwright test tests/e2e/test_registration_flow.spec.ts --reporter=html,list
    }
    "protected" {
        Write-Host "Running TEST-07: Protected routes tests..." -ForegroundColor Yellow
        npx playwright test tests/e2e/test_protected_routes.spec.ts --reporter=html,list
    }
    "a11y" {
        Write-Host "Running accessibility tests only..." -ForegroundColor Yellow
        npx playwright test --grep "Accessibility" --reporter=html,list
    }
    "security" {
        Write-Host "Running security tests only..." -ForegroundColor Yellow
        npx playwright test --grep "Security" --reporter=html,list
    }
    "performance" {
        Write-Host "Running performance tests only..." -ForegroundColor Yellow
        npx playwright test --grep "Performance" --reporter=html,list
    }
    "debug" {
        Write-Host "Running tests in debug mode..." -ForegroundColor Yellow
        npx playwright test `
            tests/e2e/test_login_flow.spec.ts `
            tests/e2e/test_registration_flow.spec.ts `
            tests/e2e/test_protected_routes.spec.ts `
            --debug
    }
    default {
        Write-Host "Unknown option: $TestGroup" -ForegroundColor Red
        Write-Host ""
        Write-Host "Usage: .\scripts\run-wave6-tests.ps1 [-TestGroup <option>]" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Options:" -ForegroundColor Yellow
        Write-Host "  all         - Run all Wave 6 tests (default)"
        Write-Host "  login       - Run only login tests (TEST-05)"
        Write-Host "  register    - Run only registration tests (TEST-06)"
        Write-Host "  protected   - Run only protected route tests (TEST-07)"
        Write-Host "  a11y        - Run only accessibility tests"
        Write-Host "  security    - Run only security tests"
        Write-Host "  performance - Run only performance tests"
        Write-Host "  debug       - Run tests in debug mode"
        Write-Host ""
        exit 1
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Execution Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "View HTML report: npx playwright show-report" -ForegroundColor Green
Write-Host "View JSON results: Get-Content playwright-results.json" -ForegroundColor Green
Write-Host ""
