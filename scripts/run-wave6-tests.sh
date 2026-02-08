#!/bin/bash
# Wave 6 E2E Tests Execution Script

set -e

echo "=========================================="
echo "Wave 6 E2E Tests - Authentication Flows"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if axe-playwright is installed
echo "Checking dependencies..."
if npm list axe-playwright &> /dev/null; then
    echo -e "${GREEN}axe-playwright is installed${NC}"
else
    echo -e "${YELLOW}axe-playwright not found. Installing...${NC}"
    npm install --save-dev axe-playwright
fi

# Check if backend is running
echo "Checking backend..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}Backend is running on port 8000${NC}"
else
    echo -e "${RED}ERROR: Backend is not running on port 8000${NC}"
    echo "Start backend with: cd backend && python -m uvicorn server.main:app --port 8000"
    exit 1
fi

# Check if frontend is running
echo "Checking frontend..."
if curl -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}Frontend is running on port 3000${NC}"
else
    echo -e "${YELLOW}WARNING: Frontend is not running on port 3000${NC}"
    echo "Some tests may fail. Start frontend with: cd apps/control-panel && npm run dev"
fi

echo ""
echo "=========================================="
echo "Running Wave 6 E2E Tests"
echo "=========================================="
echo ""

# Default: Run all Wave 6 tests
if [ "$1" == "" ]; then
    echo "Running all Wave 6 tests..."
    npx playwright test \
        tests/e2e/test_login_flow.spec.ts \
        tests/e2e/test_registration_flow.spec.ts \
        tests/e2e/test_protected_routes.spec.ts \
        --reporter=html,json,list

elif [ "$1" == "login" ]; then
    echo "Running TEST-05: Login UI tests..."
    npx playwright test tests/e2e/test_login_flow.spec.ts --reporter=html,list

elif [ "$1" == "register" ]; then
    echo "Running TEST-06: Registration UI tests..."
    npx playwright test tests/e2e/test_registration_flow.spec.ts --reporter=html,list

elif [ "$1" == "protected" ]; then
    echo "Running TEST-07: Protected routes tests..."
    npx playwright test tests/e2e/test_protected_routes.spec.ts --reporter=html,list

elif [ "$1" == "a11y" ]; then
    echo "Running accessibility tests only..."
    npx playwright test --grep "Accessibility" --reporter=html,list

elif [ "$1" == "security" ]; then
    echo "Running security tests only..."
    npx playwright test --grep "Security" --reporter=html,list

elif [ "$1" == "performance" ]; then
    echo "Running performance tests only..."
    npx playwright test --grep "Performance" --reporter=html,list

elif [ "$1" == "debug" ]; then
    echo "Running tests in debug mode..."
    npx playwright test \
        tests/e2e/test_login_flow.spec.ts \
        tests/e2e/test_registration_flow.spec.ts \
        tests/e2e/test_protected_routes.spec.ts \
        --debug

else
    echo "Unknown option: $1"
    echo ""
    echo "Usage: ./scripts/run-wave6-tests.sh [option]"
    echo ""
    echo "Options:"
    echo "  (none)      - Run all Wave 6 tests"
    echo "  login       - Run only login tests (TEST-05)"
    echo "  register    - Run only registration tests (TEST-06)"
    echo "  protected   - Run only protected route tests (TEST-07)"
    echo "  a11y        - Run only accessibility tests"
    echo "  security    - Run only security tests"
    echo "  performance - Run only performance tests"
    echo "  debug       - Run tests in debug mode"
    echo ""
    exit 1
fi

echo ""
echo "=========================================="
echo "Test Execution Complete"
echo "=========================================="
echo ""
echo "View HTML report: npx playwright show-report"
echo "View JSON results: cat playwright-results.json"
echo ""
