#!/bin/bash

echo "==================================================================="
echo "Fog Compute Benchmarking - Structure Verification"
echo "==================================================================="

echo -e "\n1. Directory Structure:"
find . -type d | sort | sed 's/^/  /'

echo -e "\n2. Python Files:"
find . -name "*.py" | sort | sed 's/^/  /'

echo -e "\n3. Configuration Files:"
find . -name "*.json" -o -name "*.md" | sort | sed 's/^/  /'

echo -e "\n4. Line Counts:"
wc -l **/*.py config/*.json 2>/dev/null | tail -1

echo -e "\n5. Module Verification:"
python3 << 'PYTHON'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils import SystemMetrics, setup_logging, collect_system_metrics
    print("  ✓ utils module imports successfully")
except ImportError as e:
    print(f"  ✗ utils module import failed: {e}")

try:
    from benchmarks import FogBenchmarkSuite, BenchmarkRunner
    print("  ✓ benchmarks module imports successfully")
except ImportError as e:
    print(f"  ✗ benchmarks module import failed: {e}")

try:
    import json
    with open('config/targets.json') as f:
        config = json.load(f)
    print(f"  ✓ config loaded: {len(config['performance_targets'])} targets")
except Exception as e:
    print(f"  ✗ config load failed: {e}")
PYTHON

echo -e "\n6. Performance Targets:"
python3 -c "import json; data=json.load(open('config/targets.json')); print('\n'.join(f'  • {k}: {v[\"value\"]}% ({v.get(\"range\", \"N/A\")})' for k,v in data['performance_targets'].items()))"

echo -e "\n==================================================================="
echo "Verification Complete!"
echo "Run benchmarks: python benchmarks/run_benchmarks.py --mode demo"
echo "==================================================================="
