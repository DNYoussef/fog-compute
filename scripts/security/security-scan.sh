#!/bin/bash

##############################################################################
# Fog Compute Security Scanner
# Automated security vulnerability scanning across all components
##############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCAN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
REPORT_DIR="$SCAN_DIR/security-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/security-scan-$TIMESTAMP.txt"

# Create report directory
mkdir -p "$REPORT_DIR"

# Initialize report
echo "====================================================================" > "$REPORT_FILE"
echo "SECURITY SCAN REPORT" >> "$REPORT_FILE"
echo "Scan Date: $(date)" >> "$REPORT_FILE"
echo "====================================================================" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

##############################################################################
# Helper Functions
##############################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    echo "[INFO] $1" >> "$REPORT_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "[SUCCESS] $1" >> "$REPORT_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "[WARNING] $1" >> "$REPORT_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "[ERROR] $1" >> "$REPORT_FILE"
}

##############################################################################
# 1. Dependency Vulnerability Scanning
##############################################################################

scan_dependencies() {
    log_info "Scanning dependencies for vulnerabilities..."
    echo "" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"
    echo "DEPENDENCY VULNERABILITY SCAN" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"

    # Python dependencies (pip-audit)
    log_info "Scanning Python dependencies..."
    cd "$SCAN_DIR/backend"
    if command -v pip-audit &> /dev/null; then
        pip-audit --format json > "$REPORT_DIR/pip-audit-$TIMESTAMP.json" 2>&1 || true
        pip-audit >> "$REPORT_FILE" 2>&1 || log_warning "pip-audit found vulnerabilities"
        log_success "Python dependency scan complete"
    else
        log_warning "pip-audit not installed. Install with: pip install pip-audit"
    fi

    # Node.js dependencies (npm audit)
    log_info "Scanning Node.js dependencies..."
    cd "$SCAN_DIR"
    if command -v npm &> /dev/null; then
        npm audit --json > "$REPORT_DIR/npm-audit-$TIMESTAMP.json" 2>&1 || true
        npm audit >> "$REPORT_FILE" 2>&1 || log_warning "npm audit found vulnerabilities"
        log_success "Node.js dependency scan complete"
    else
        log_warning "npm not installed"
    fi

    # Rust dependencies (cargo audit)
    log_info "Scanning Rust dependencies..."
    cd "$SCAN_DIR/src/betanet"
    if command -v cargo &> /dev/null; then
        if command -v cargo-audit &> /dev/null; then
            cargo audit --json > "$REPORT_DIR/cargo-audit-$TIMESTAMP.json" 2>&1 || true
            cargo audit >> "$REPORT_FILE" 2>&1 || log_warning "cargo audit found vulnerabilities"
            log_success "Rust dependency scan complete"
        else
            log_warning "cargo-audit not installed. Install with: cargo install cargo-audit"
        fi
    else
        log_warning "cargo not installed"
    fi
}

##############################################################################
# 2. Static Code Analysis
##############################################################################

static_code_analysis() {
    log_info "Running static code analysis..."
    echo "" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"
    echo "STATIC CODE ANALYSIS" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"

    # Python - Bandit
    log_info "Running Bandit (Python security linter)..."
    cd "$SCAN_DIR"
    if command -v bandit &> /dev/null; then
        bandit -r backend/server -f json -o "$REPORT_DIR/bandit-$TIMESTAMP.json" 2>&1 || true
        bandit -r backend/server >> "$REPORT_FILE" 2>&1 || log_warning "Bandit found security issues"
        log_success "Bandit scan complete"
    else
        log_warning "Bandit not installed. Install with: pip install bandit"
    fi

    # Python - Safety
    log_info "Running Safety (Python dependency checker)..."
    if command -v safety &> /dev/null; then
        cd "$SCAN_DIR/backend"
        safety check --json > "$REPORT_DIR/safety-$TIMESTAMP.json" 2>&1 || true
        safety check >> "$REPORT_FILE" 2>&1 || log_warning "Safety found vulnerabilities"
        log_success "Safety check complete"
    else
        log_warning "Safety not installed. Install with: pip install safety"
    fi

    # JavaScript/TypeScript - ESLint
    log_info "Running ESLint (JavaScript/TypeScript linter)..."
    cd "$SCAN_DIR"
    if command -v eslint &> /dev/null; then
        eslint apps/control-panel --ext .ts,.tsx,.js,.jsx -f json -o "$REPORT_DIR/eslint-$TIMESTAMP.json" 2>&1 || true
        eslint apps/control-panel --ext .ts,.tsx,.js,.jsx >> "$REPORT_FILE" 2>&1 || log_warning "ESLint found issues"
        log_success "ESLint scan complete"
    else
        log_warning "ESLint not installed"
    fi

    # Rust - Clippy
    log_info "Running Clippy (Rust linter)..."
    cd "$SCAN_DIR/src/betanet"
    if command -v cargo &> /dev/null; then
        cargo clippy -- -D warnings >> "$REPORT_FILE" 2>&1 || log_warning "Clippy found issues"
        log_success "Clippy scan complete"
    fi
}

##############################################################################
# 3. Secret Scanning
##############################################################################

scan_secrets() {
    log_info "Scanning for exposed secrets..."
    echo "" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"
    echo "SECRET SCANNING" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"

    # TruffleHog
    if command -v trufflehog &> /dev/null; then
        cd "$SCAN_DIR"
        trufflehog filesystem . --json > "$REPORT_DIR/trufflehog-$TIMESTAMP.json" 2>&1 || true
        log_success "TruffleHog scan complete"
    else
        log_warning "TruffleHog not installed. Install from: https://github.com/trufflesecurity/trufflehog"
    fi

    # Manual pattern checking for common secrets
    log_info "Checking for hardcoded secrets..."
    cd "$SCAN_DIR"

    # Check for hardcoded SECRET_KEY
    if grep -r "SECRET_KEY.*=.*['\"].*['\"]" --include="*.py" --include="*.js" --include="*.ts" . 2>/dev/null; then
        log_error "Found hardcoded SECRET_KEY!" >> "$REPORT_FILE"
    fi

    # Check for hardcoded passwords
    if grep -r "password.*=.*['\"].*['\"]" --include="*.py" --include="*.js" --include="*.ts" --include="*.yml" . 2>/dev/null | grep -v "example" | grep -v "test"; then
        log_error "Found hardcoded passwords!" >> "$REPORT_FILE"
    fi

    # Check for API keys
    if grep -r -E "(api_key|apikey|api-key).*=.*['\"][^'\"]{20,}['\"]" --include="*.py" --include="*.js" --include="*.ts" . 2>/dev/null; then
        log_error "Found potential API keys!" >> "$REPORT_FILE"
    fi

    log_success "Secret scanning complete"
}

##############################################################################
# 4. Docker Security Scanning
##############################################################################

scan_docker_images() {
    log_info "Scanning Docker images..."
    echo "" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"
    echo "DOCKER IMAGE SCANNING" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"

    # Trivy
    if command -v trivy &> /dev/null; then
        log_info "Running Trivy on Docker images..."

        # Scan backend image
        if docker images | grep -q "fog-backend"; then
            trivy image --format json --output "$REPORT_DIR/trivy-backend-$TIMESTAMP.json" fog-backend:latest 2>&1 || true
            trivy image fog-backend:latest >> "$REPORT_FILE" 2>&1 || log_warning "Trivy found vulnerabilities in backend"
        fi

        # Scan frontend image
        if docker images | grep -q "fog-frontend"; then
            trivy image --format json --output "$REPORT_DIR/trivy-frontend-$TIMESTAMP.json" fog-frontend:latest 2>&1 || true
            trivy image fog-frontend:latest >> "$REPORT_FILE" 2>&1 || log_warning "Trivy found vulnerabilities in frontend"
        fi

        log_success "Trivy scan complete"
    else
        log_warning "Trivy not installed. Install from: https://github.com/aquasecurity/trivy"
    fi
}

##############################################################################
# 5. Configuration Security Check
##############################################################################

check_configuration() {
    log_info "Checking configuration security..."
    echo "" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"
    echo "CONFIGURATION SECURITY CHECK" >> "$REPORT_FILE"
    echo "--------------------------------------------------------------------" >> "$REPORT_FILE"

    # Check for exposed .env files
    if [ -f "$SCAN_DIR/.env" ]; then
        log_error ".env file found in repository!" >> "$REPORT_FILE"
    fi

    # Check Docker Compose security
    cd "$SCAN_DIR"
    if [ -f "docker-compose.yml" ]; then
        # Check for hardcoded passwords
        if grep -q "POSTGRES_PASSWORD:" docker-compose.yml; then
            if grep "POSTGRES_PASSWORD:" docker-compose.yml | grep -q "fog_password"; then
                log_error "Hardcoded database password in docker-compose.yml!" >> "$REPORT_FILE"
            fi
        fi

        # Check for privileged mode
        if grep -q "privileged: true" docker-compose.yml; then
            log_warning "Privileged mode enabled in docker-compose.yml" >> "$REPORT_FILE"
        fi
    fi

    # Check SSL/TLS configuration
    if [ -d "$SCAN_DIR/config/production/nginx" ]; then
        log_info "Checking Nginx SSL configuration..."
        if grep -q "ssl_protocols" "$SCAN_DIR/config/production/nginx/nginx.conf"; then
            if grep "ssl_protocols" "$SCAN_DIR/config/production/nginx/nginx.conf" | grep -q "TLSv1 "; then
                log_error "Insecure TLS version enabled!" >> "$REPORT_FILE"
            else
                log_success "TLS configuration looks good"
            fi
        fi
    fi

    log_success "Configuration check complete"
}

##############################################################################
# 6. Generate Summary
##############################################################################

generate_summary() {
    log_info "Generating summary..."
    echo "" >> "$REPORT_FILE"
    echo "====================================================================" >> "$REPORT_FILE"
    echo "SCAN SUMMARY" >> "$REPORT_FILE"
    echo "====================================================================" >> "$REPORT_FILE"

    # Count issues by severity
    CRITICAL_COUNT=$(grep -c "\[ERROR\]" "$REPORT_FILE" || echo "0")
    WARNING_COUNT=$(grep -c "\[WARNING\]" "$REPORT_FILE" || echo "0")
    INFO_COUNT=$(grep -c "\[INFO\]" "$REPORT_FILE" || echo "0")

    echo "Critical Issues: $CRITICAL_COUNT" >> "$REPORT_FILE"
    echo "Warnings: $WARNING_COUNT" >> "$REPORT_FILE"
    echo "Info: $INFO_COUNT" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    if [ "$CRITICAL_COUNT" -gt 0 ]; then
        echo "Status: FAILED - Critical issues found" >> "$REPORT_FILE"
        log_error "Security scan FAILED - $CRITICAL_COUNT critical issues found"
        exit 1
    elif [ "$WARNING_COUNT" -gt 10 ]; then
        echo "Status: WARNING - Multiple warnings found" >> "$REPORT_FILE"
        log_warning "Security scan completed with $WARNING_COUNT warnings"
        exit 0
    else
        echo "Status: PASSED" >> "$REPORT_FILE"
        log_success "Security scan PASSED"
        exit 0
    fi
}

##############################################################################
# Main Execution
##############################################################################

main() {
    log_info "Starting comprehensive security scan..."
    log_info "Scan directory: $SCAN_DIR"
    log_info "Report file: $REPORT_FILE"
    echo ""

    scan_dependencies
    static_code_analysis
    scan_secrets
    scan_docker_images
    check_configuration
    generate_summary

    log_info "Full report saved to: $REPORT_FILE"
}

# Run main function
main
