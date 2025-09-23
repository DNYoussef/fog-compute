#!/bin/bash
# Automated Benchmark Runner for Fog-Compute
# Executes all benchmarks and generates consolidated report

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$SCRIPT_DIR"
TIMESTAMP=$(date +%s)

echo "========================================================================"
echo "Fog-Compute Benchmark Suite"
echo "========================================================================"
echo ""

# Track results
declare -A RESULTS
ALL_PASS=true

# Function to run benchmark and capture result
run_benchmark() {
    local name=$1
    local command=$2
    local report_file=$3

    echo "========================================================================"
    echo "Running: $name"
    echo "========================================================================"

    if eval "$command"; then
        RESULTS[$name]="SUCCESS"
        echo "✓ $name completed successfully"
    else
        RESULTS[$name]="FAILED"
        ALL_PASS=false
        echo "✗ $name failed"
    fi

    echo ""
}

# Run benchmarks
run_benchmark "Betanet Throughput" \
    "cargo run --release --bin betanet_throughput" \
    "betanet_throughput_report.json"

run_benchmark "BitChat Latency" \
    "ts-node $SCRIPT_DIR/bitchat_latency.ts" \
    "bitchat_latency_report.json"

run_benchmark "Control Panel Rendering" \
    "ts-node $SCRIPT_DIR/control_panel_render.ts" \
    "control_panel_render_report.json"

run_benchmark "System Integration" \
    "python3 $SCRIPT_DIR/system_integration.py" \
    "system_integration_report.json"

# Generate consolidated report
echo "========================================================================"
echo "Generating Consolidated Report"
echo "========================================================================"

cat > "$REPORT_DIR/consolidated_benchmark_report.json" << EOF
{
  "benchmark_suite": "fog_compute_complete",
  "timestamp": $TIMESTAMP,
  "benchmarks": {
EOF

first=true
for bench in "${!RESULTS[@]}"; do
    if [ "$first" = false ]; then
        echo "," >> "$REPORT_DIR/consolidated_benchmark_report.json"
    fi
    first=false

    cat >> "$REPORT_DIR/consolidated_benchmark_report.json" << EOF
    "$bench": {
      "status": "${RESULTS[$bench]}"
    }
EOF
done

cat >> "$REPORT_DIR/consolidated_benchmark_report.json" << EOF

  },
  "summary": {
    "total_benchmarks": ${#RESULTS[@]},
    "passed": $(echo "${RESULTS[@]}" | tr ' ' '\n' | grep -c "SUCCESS" || true),
    "failed": $(echo "${RESULTS[@]}" | tr ' ' '\n' | grep -c "FAILED" || true)
  },
  "overall_status": "$(if [ "$ALL_PASS" = true ]; then echo "PASS"; else echo "FAIL"; fi)"
}
EOF

# Print summary
echo ""
echo "========================================================================"
echo "BENCHMARK SUMMARY"
echo "========================================================================"
echo ""
echo "Total Benchmarks: ${#RESULTS[@]}"
echo ""

for bench in "${!RESULTS[@]}"; do
    status="${RESULTS[$bench]}"
    if [ "$status" = "SUCCESS" ]; then
        echo "  ✓ $bench: PASS"
    else
        echo "  ✗ $bench: FAIL"
    fi
done

echo ""
if [ "$ALL_PASS" = true ]; then
    echo "Overall Status: ✓ PASS"
    exit 0
else
    echo "Overall Status: ✗ FAIL"
    exit 1
fi