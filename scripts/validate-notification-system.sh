#!/bin/bash

# Notification System Validation Script
# This script verifies that the notification system is properly installed

echo "======================================"
echo "Notification System Validation"
echo "======================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check core component
echo "Checking core component..."
if [ -f "apps/control-panel/components/SuccessNotification.tsx" ]; then
    echo -e "${GREEN}✓${NC} Core component exists"
else
    echo -e "${RED}✗${NC} Core component missing"
    ERRORS=$((ERRORS + 1))
fi

# Check example component
echo "Checking example component..."
if [ -f "apps/control-panel/components/examples/NotificationExample.tsx" ]; then
    echo -e "${GREEN}✓${NC} Example component exists"
else
    echo -e "${RED}✗${NC} Example component missing"
    ERRORS=$((ERRORS + 1))
fi

# Check layout integration
echo "Checking layout integration..."
if grep -q "NotificationToaster" "apps/control-panel/app/layout.tsx"; then
    echo -e "${GREEN}✓${NC} Layout integrated"
else
    echo -e "${RED}✗${NC} Layout not integrated"
    ERRORS=$((ERRORS + 1))
fi

# Check documentation files
echo "Checking documentation..."
DOC_FILES=(
    "docs/NOTIFICATION_SYSTEM_README.md"
    "docs/NOTIFICATION_CHEAT_SHEET.md"
    "docs/NOTIFICATION_QUICK_START.md"
    "docs/NOTIFICATION_INTEGRATION_GUIDE.md"
    "docs/NOTIFICATION_USAGE_EXAMPLES.md"
    "docs/NOTIFICATION_IMPLEMENTATION_SUMMARY.md"
    "docs/NOTIFICATION_FILE_STRUCTURE.md"
)

for file in "${DOC_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $(basename $file)"
    else
        echo -e "${RED}✗${NC} $(basename $file) missing"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check dependency
echo ""
echo "Checking dependencies..."
if npm list react-hot-toast &>/dev/null; then
    echo -e "${GREEN}✓${NC} react-hot-toast installed"
else
    echo -e "${RED}✗${NC} react-hot-toast not installed"
    ERRORS=$((ERRORS + 1))
fi

# Check test IDs in component
echo ""
echo "Checking test IDs..."
if grep -q 'data-testid="success-notification"' "apps/control-panel/components/SuccessNotification.tsx"; then
    echo -e "${GREEN}✓${NC} success-notification test ID present"
else
    echo -e "${YELLOW}⚠${NC} success-notification test ID not found"
fi

if grep -q 'data-testid="error-notification"' "apps/control-panel/components/SuccessNotification.tsx"; then
    echo -e "${GREEN}✓${NC} error-notification test ID present"
else
    echo -e "${YELLOW}⚠${NC} error-notification test ID not found"
fi

# Summary
echo ""
echo "======================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "Notification system is properly installed."
else
    echo -e "${RED}✗ $ERRORS error(s) found${NC}"
    echo "Please review the issues above."
fi
echo "======================================"

exit $ERRORS
