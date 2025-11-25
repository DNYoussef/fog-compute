#!/bin/bash
# Test script for Betanet Metrics Exporter

echo "=== Betanet Metrics Exporter Test Suite ==="
echo ""

# Test 1: Build the exporter
echo "[TEST 1] Building exporter..."
cargo build --release
if [ $? -eq 0 ]; then
    echo "PASS: Exporter builds successfully"
else
    echo "FAIL: Build failed"
    exit 1
fi
echo ""

# Test 2: Run unit tests
echo "[TEST 2] Running unit tests..."
cargo test
if [ $? -eq 0 ]; then
    echo "PASS: All unit tests passed"
else
    echo "FAIL: Unit tests failed"
    exit 1
fi
echo ""

# Test 3: Start exporter (will run in background)
echo "[TEST 3] Starting exporter (with Betanet unavailable)..."
RUST_LOG=info cargo run --release &
EXPORTER_PID=$!
sleep 5

# Test 4: Check health endpoint
echo "[TEST 4] Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:9200/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "PASS: Health endpoint responding"
else
    echo "FAIL: Health endpoint not responding"
    kill $EXPORTER_PID
    exit 1
fi
echo ""

# Test 5: Check metrics endpoint
echo "[TEST 5] Testing metrics endpoint..."
METRICS_RESPONSE=$(curl -s http://localhost:9200/metrics)
if echo "$METRICS_RESPONSE" | grep -q "betanet_"; then
    echo "PASS: Metrics endpoint responding with Betanet metrics"
else
    echo "FAIL: Metrics endpoint not returning expected metrics"
    kill $EXPORTER_PID
    exit 1
fi
echo ""

# Test 6: Verify graceful degradation (Betanet not running)
echo "[TEST 6] Testing graceful degradation..."
sleep 20  # Wait for cache expiration and retries
LOGS=$(ps aux | grep betanet_exporter | grep -v grep)
if [ -n "$LOGS" ]; then
    echo "PASS: Exporter still running despite Betanet unavailability"
else
    echo "FAIL: Exporter crashed when Betanet unavailable"
    exit 1
fi
echo ""

# Cleanup
echo "Cleaning up..."
kill $EXPORTER_PID
echo ""

echo "=== All Tests Passed ==="
echo ""
echo "To test with Betanet running:"
echo "1. Start Betanet service: cargo run --bin betanet (in separate terminal)"
echo "2. Start exporter: RUST_LOG=info cargo run --release"
echo "3. Check metrics: curl http://localhost:9200/metrics"
echo "4. Stop Betanet and observe circuit breaker behavior in logs"
