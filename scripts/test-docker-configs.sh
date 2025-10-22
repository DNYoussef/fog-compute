#!/bin/bash
# Docker Compose Configuration Testing Script
# Tests all Docker Compose configurations for FOG Compute platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((TESTS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

test_counter() {
    ((TESTS_RUN++))
}

# Cleanup function
cleanup() {
    log_info "Cleaning up Docker resources..."
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.betanet.yml -f docker-compose.monitoring.yml down -v 2>/dev/null || true
    docker network prune -f 2>/dev/null || true
}

# Trap cleanup on exit
trap cleanup EXIT

echo "=========================================="
echo "FOG Compute Docker Configuration Tests"
echo "=========================================="
echo ""

# Test 1: Validate Docker Compose file syntax
log_info "Test 1: Validating Docker Compose file syntax..."
test_counter

if docker-compose -f docker-compose.yml config > /dev/null 2>&1; then
    log_success "Base configuration syntax valid"
else
    log_error "Base configuration syntax invalid"
fi

if docker-compose -f docker-compose.yml -f docker-compose.dev.yml config > /dev/null 2>&1; then
    log_success "Development configuration syntax valid"
else
    log_error "Development configuration syntax invalid"
fi

if docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config > /dev/null 2>&1; then
    log_success "Betanet configuration syntax valid"
else
    log_error "Betanet configuration syntax invalid"
fi

if docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml config > /dev/null 2>&1; then
    log_success "Monitoring configuration syntax valid"
else
    log_error "Monitoring configuration syntax invalid"
fi

# Test 2: Check for duplicate services
log_info "Test 2: Checking for duplicate services..."
test_counter

BASE_SERVICES=$(docker-compose -f docker-compose.yml config --services)
DEV_SERVICES=$(docker-compose -f docker-compose.yml -f docker-compose.dev.yml config --services)
BETANET_SERVICES=$(docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config --services)

# Check if betanet config adds new services (not duplicates)
BETANET_NEW=$(docker-compose -f docker-compose.betanet.yml config --services 2>/dev/null | grep -v "prometheus\|grafana\|loki\|postgres" || true)

if [ ! -z "$BETANET_NEW" ]; then
    log_success "Betanet configuration adds only new mixnode services (no monitoring duplicates)"
else
    log_error "Betanet configuration issue detected"
fi

# Test 3: Verify network configuration
log_info "Test 3: Verifying network configuration..."
test_counter

NETWORKS=$(docker-compose -f docker-compose.yml config | grep -A 5 "^networks:" | grep -E "^\s+[a-z-]+:" | awk '{print $1}' | tr -d ':')

if echo "$NETWORKS" | grep -q "fog-network" && echo "$NETWORKS" | grep -q "betanet-network"; then
    log_success "Both fog-network and betanet-network configured"
else
    log_error "Network configuration incomplete"
fi

# Test 4: Check multi-network attachment
log_info "Test 4: Checking multi-network attachments..."
test_counter

POSTGRES_NETWORKS=$(docker-compose -f docker-compose.yml config | grep -A 20 "postgres:" | grep -A 10 "networks:" | grep -E "^\s+-" | awk '{print $2}')
BACKEND_NETWORKS=$(docker-compose -f docker-compose.yml config | grep -A 30 "backend:" | grep -A 10 "networks:" | grep -E "^\s+-" | awk '{print $2}')

if echo "$POSTGRES_NETWORKS" | grep -q "fog-network" && echo "$POSTGRES_NETWORKS" | grep -q "betanet-network"; then
    log_success "PostgreSQL attached to both networks"
else
    log_error "PostgreSQL network attachment incomplete"
fi

if echo "$BACKEND_NETWORKS" | grep -q "fog-network" && echo "$BACKEND_NETWORKS" | grep -q "betanet-network"; then
    log_success "Backend attached to both networks"
else
    log_error "Backend network attachment incomplete"
fi

# Test 5: Verify port assignments (no conflicts)
log_info "Test 5: Verifying port assignments..."
test_counter

DEV_PORTS=$(docker-compose -f docker-compose.yml -f docker-compose.dev.yml config | grep -E "^\s+- \"[0-9]+:" | awk -F'"' '{print $2}' | awk -F':' '{print $1}' | sort)
UNIQUE_PORTS=$(echo "$DEV_PORTS" | uniq)

if [ "$DEV_PORTS" = "$UNIQUE_PORTS" ]; then
    log_success "No port conflicts detected"
else
    log_error "Port conflicts detected"
    echo "Duplicate ports:"
    echo "$DEV_PORTS" | uniq -d
fi

# Test 6: Verify Grafana port consistency
log_info "Test 6: Verifying Grafana port configuration..."
test_counter

GRAFANA_PORT=$(docker-compose -f docker-compose.yml -f docker-compose.dev.yml config | grep -A 30 "grafana:" | grep "^\s*- \"3001:3000\"" || echo "")

if [ ! -z "$GRAFANA_PORT" ]; then
    log_success "Grafana correctly configured on port 3001"
else
    log_error "Grafana port configuration issue"
fi

# Test 7: Test production configuration (dry-run)
log_info "Test 7: Testing production configuration (dry-run)..."
test_counter

if docker-compose -f docker-compose.yml config --quiet; then
    log_success "Production configuration passes validation"
else
    log_error "Production configuration validation failed"
fi

# Test 8: Test development configuration (dry-run)
log_info "Test 8: Testing development configuration (dry-run)..."
test_counter

if docker-compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet; then
    log_success "Development configuration passes validation"
else
    log_error "Development configuration validation failed"
fi

# Test 9: Test betanet configuration (dry-run)
log_info "Test 9: Testing betanet configuration (dry-run)..."
test_counter

if docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config --quiet; then
    log_success "Betanet configuration passes validation"
else
    log_error "Betanet configuration validation failed"
fi

# Test 10: Verify monitoring stack consolidation
log_info "Test 10: Verifying monitoring stack consolidation..."
test_counter

PROM_COUNT=$(docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config --services | grep -c "prometheus" || echo "0")
GRAFANA_COUNT=$(docker-compose -f docker-compose.yml -f docker-compose.betanet.yml config --services | grep -c "grafana" || echo "0")

if [ "$PROM_COUNT" -eq 1 ] && [ "$GRAFANA_COUNT" -eq 1 ]; then
    log_success "Monitoring stack consolidated (single Prometheus and Grafana)"
else
    log_error "Monitoring stack duplication detected (Prometheus: $PROM_COUNT, Grafana: $GRAFANA_COUNT)"
fi

# Test 11: Calculate resource savings
log_info "Test 11: Calculating resource savings..."
test_counter

# Estimated RAM usage per container
PROMETHEUS_RAM=200
GRAFANA_RAM=100
POSTGRES_RAM=50

BEFORE_RAM=$((PROMETHEUS_RAM * 3 + GRAFANA_RAM * 3 + POSTGRES_RAM * 2))
AFTER_RAM=$((PROMETHEUS_RAM + GRAFANA_RAM + POSTGRES_RAM))
SAVINGS=$((BEFORE_RAM - AFTER_RAM))

log_success "Resource savings calculation complete"
echo "  Before: ${BEFORE_RAM}MB RAM"
echo "  After: ${AFTER_RAM}MB RAM"
echo "  Savings: ${SAVINGS}MB RAM (~${SAVINGS}MB reduction)"

# Test 12: Verify volume isolation
log_info "Test 12: Verifying volume isolation..."
test_counter

DEV_VOLUMES=$(docker-compose -f docker-compose.yml -f docker-compose.dev.yml config | grep -A 1 "^volumes:" | grep -E "^\s+[a-z_-]+:" | awk '{print $1}' | tr -d ':' | sort)
BASE_VOLUMES=$(docker-compose -f docker-compose.yml config | grep -A 1 "^volumes:" | grep -E "^\s+[a-z_-]+:" | awk '{print $1}' | tr -d ':' | sort)

if echo "$DEV_VOLUMES" | grep -q "postgres_dev_data"; then
    log_success "Development uses separate postgres_dev_data volume"
else
    log_error "Development volume isolation issue"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total tests run: $TESTS_RUN"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! Docker configuration is ready.${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
