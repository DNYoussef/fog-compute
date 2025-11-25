#!/bin/bash

# Quality Panel Test Verification Script
# Verifies all test files are present and provides quick test commands

set -e

echo "======================================"
echo "Quality Panel Test Verification"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo -e "${RED}Error: Must run from project root${NC}"
    exit 1
fi

echo "1. Checking test files..."
echo ""

# Check E2E files
if [ -f "tests/e2e/page-objects/QualityPanelPage.ts" ]; then
    echo -e "${GREEN}✓${NC} QualityPanelPage.ts (Page Object Model)"
    wc -l tests/e2e/page-objects/QualityPanelPage.ts
else
    echo -e "${RED}✗${NC} QualityPanelPage.ts missing"
fi

if [ -f "tests/e2e/test_quality_panel_flow.spec.ts" ]; then
    echo -e "${GREEN}✓${NC} test_quality_panel_flow.spec.ts (E2E Tests)"
    wc -l tests/e2e/test_quality_panel_flow.spec.ts
else
    echo -e "${RED}✗${NC} test_quality_panel_flow.spec.ts missing"
fi

# Check Integration files
if [ -f "tests/integration/test_quality_panel.py" ]; then
    echo -e "${GREEN}✓${NC} test_quality_panel.py (Integration Tests)"
    wc -l tests/integration/test_quality_panel.py
else
    echo -e "${RED}✗${NC} test_quality_panel.py missing"
fi

# Check documentation
if [ -f "tests/QUALITY-PANEL-TEST-SUMMARY.md" ]; then
    echo -e "${GREEN}✓${NC} QUALITY-PANEL-TEST-SUMMARY.md"
else
    echo -e "${RED}✗${NC} QUALITY-PANEL-TEST-SUMMARY.md missing"
fi

if [ -f "tests/QUALITY-PANEL-QUICK-START.md" ]; then
    echo -e "${GREEN}✓${NC} QUALITY-PANEL-QUICK-START.md"
else
    echo -e "${RED}✗${NC} QUALITY-PANEL-QUICK-START.md missing"
fi

echo ""
echo "2. Checking dependencies..."
echo ""

# Check Node.js dependencies
if command -v npm &> /dev/null; then
    echo -e "${GREEN}✓${NC} npm installed"

    if [ -d "node_modules/@playwright/test" ]; then
        echo -e "${GREEN}✓${NC} Playwright installed"
    else
        echo -e "${YELLOW}⚠${NC} Playwright not installed. Run: npm install"
    fi
else
    echo -e "${RED}✗${NC} npm not found"
fi

# Check Python dependencies
if command -v python &> /dev/null || command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python installed"

    if python -c "import pytest" 2>/dev/null || python3 -c "import pytest" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} pytest installed"
    else
        echo -e "${YELLOW}⚠${NC} pytest not installed. Run: pip install pytest pytest-asyncio pytest-cov"
    fi
else
    echo -e "${RED}✗${NC} Python not found"
fi

echo ""
echo "3. Test Commands"
echo ""

echo "Run E2E tests:"
echo "  npx playwright test test_quality_panel_flow"
echo ""

echo "Run Integration tests:"
echo "  pytest tests/integration/test_quality_panel.py -v"
echo ""

echo "Run with UI (interactive):"
echo "  npx playwright test test_quality_panel_flow --ui"
echo ""

echo "Run specific test suite:"
echo "  npx playwright test test_quality_panel_flow -g 'QP-01'"
echo "  pytest tests/integration/test_quality_panel.py::TestQualityPanelAPI -v"
echo ""

echo "4. Quick Test Statistics"
echo ""

# Count tests in E2E file
if [ -f "tests/e2e/test_quality_panel_flow.spec.ts" ]; then
    e2e_tests=$(grep -c "test(" tests/e2e/test_quality_panel_flow.spec.ts || echo "0")
    e2e_suites=$(grep -c "test.describe(" tests/e2e/test_quality_panel_flow.spec.ts || echo "0")
    echo "E2E Tests:"
    echo "  Test Suites: ${e2e_suites}"
    echo "  Test Cases: ${e2e_tests}"
fi

# Count tests in Integration file
if [ -f "tests/integration/test_quality_panel.py" ]; then
    integration_tests=$(grep -c "def test_" tests/integration/test_quality_panel.py || echo "0")
    integration_classes=$(grep -c "^class Test" tests/integration/test_quality_panel.py || echo "0")
    echo ""
    echo "Integration Tests:"
    echo "  Test Classes: ${integration_classes}"
    echo "  Test Cases: ${integration_tests}"
fi

echo ""
echo "5. Test Coverage Areas"
echo ""

echo "✓ Component initialization and rendering"
echo "✓ Test suite selection"
echo "✓ Test execution workflows"
echo "✓ Console output and state management"
echo "✓ Error handling and recovery"
echo "✓ Performance and loading states"
echo "✓ Accessibility compliance (WCAG 2.1 AA)"
echo "✓ Complete user flows"
echo "✓ Edge cases and boundary conditions"
echo "✓ API integration"
echo "✓ Data persistence"
echo ""

echo "======================================"
echo "Verification Complete"
echo "======================================"
echo ""

echo "Next Steps:"
echo "1. Install dependencies: npm install && pip install pytest pytest-asyncio"
echo "2. Install browsers: npx playwright install"
echo "3. Run tests: See commands above"
echo "4. View reports: npx playwright show-report tests/output/playwright-report"
echo ""

echo "Documentation:"
echo "- Detailed: tests/QUALITY-PANEL-TEST-SUMMARY.md"
echo "- Quick Start: tests/QUALITY-PANEL-QUICK-START.md"
echo ""
