# Fog Compute Benchmarking - Usage Guide

## Quick Start

### Install Dependencies
```bash
pip install asyncio psutil
```

### Run Benchmarks

#### Full Suite
```bash
cd C:/Users/17175/Desktop/fog-compute
python src/fog/benchmarks/run_benchmarks.py --mode full --verbose
```

#### Quick Validation
```bash
python src/fog/benchmarks/run_benchmarks.py --mode quick
```

#### Demo Mode
```bash
python src/fog/benchmarks/run_benchmarks.py --mode demo
```

### Custom Output Directory
```bash
python src/fog/benchmarks/run_benchmarks.py --mode full --output-dir /path/to/reports
```

## Expected Output

### Console Output
```
================================================================================
FOG COMPUTE PERFORMANCE BENCHMARK SUITE - FULL MODE
================================================================================
Starting Fog Compute Performance Benchmark Suite
Baseline established: {'memory': {...}, 'timestamp': 1234567890}
Running system benchmarks...
Running privacy benchmarks...
Running graph benchmarks...
Running integration benchmarks...

================================================================================
BENCHMARK EXECUTION SUMMARY
================================================================================
Overall Grade: A
Tests Passed: 15/16 (93.8%)
Total Execution Time: 12.3 seconds

Results by Category:
  SYSTEM: 5/5 passed, avg improvement: 68.5%
  PRIVACY: 4/4 passed, avg improvement: 42.3%
  GRAPH: 4/4 passed, avg improvement: 55.8%
  INTEGRATION: 2/3 passed, avg improvement: 12.4%

================================================================================
```

### Generated Files
- `fog-compute/reports/benchmark_results_[timestamp].json` - Detailed results
- `fog-compute/reports/benchmark_suite.log` - Execution logs
- `fog-compute/reports/benchmark_runner.log` - Runner logs

## Performance Targets

### Core Improvements (Must Meet)
- **Fog Coordinator**: ≥70% improvement (60-80% range)
- **Privacy Coordinator**: ≥40% improvement (30-50% range)
- **Graph Processing**: ≥50% improvement (40-60% range)

### System Latency (Must Not Exceed)
- **System Startup**: ≤30 seconds
- **Device Registration**: ≤2 seconds
- **Privacy Task Routing**: ≤3 seconds
- **Graph Gap Detection**: ≤30 seconds (1000 nodes)

### Quality Metrics
- **Memory Reduction**: ≥30% (20-40% range)
- **Coupling Reduction**: ≥70%
- **Overall Pass Rate**: ≥75%

## Interpreting Results

### Grade Scale
- **A**: 90-100% pass rate - Production ready
- **B**: 80-89% pass rate - Production ready with monitoring
- **C**: 70-79% pass rate - Staged deployment recommended
- **D**: 60-69% pass rate - Additional optimization needed
- **F**: <60% pass rate - Not ready for deployment

### Critical Benchmarks
These must pass for deployment approval:
1. `fog_coordinator_optimization`
2. `onion_coordinator_optimization`
3. `graph_gap_detection_optimization`

### Deployment Criteria
System is deployment-ready when:
- ✅ Overall grade is A, B, or C
- ✅ No critical regressions detected
- ✅ All core benchmarks passed
- ✅ Pass rate ≥75%

## Extending the Suite

### Add New Benchmark
```python
# In benchmark_suite.py

async def _benchmark_new_feature(self) -> BenchmarkResult:
    """Benchmark new feature performance"""
    test_name = "new_feature_test"

    async with self._performance_context(test_name) as start_time:
        # Your benchmark code here
        await some_operation()
        duration = time.perf_counter() - start_time

    target = self.targets['new_feature_target']['value']
    improvement = calculate_improvement(baseline, duration)
    passed = improvement >= target

    result = BenchmarkResult(
        test_name=test_name,
        category="system",  # or privacy, graph, integration
        before_value=baseline,
        after_value=duration,
        improvement_percent=improvement,
        target_improvement=target,
        passed=passed,
        timestamp=time.time(),
        metadata={'key': 'value'}
    )

    self.results.append(result)
    return result
```

### Add New Target
```json
// In config/targets.json

{
  "performance_targets": {
    "new_feature_target": {
      "value": 50.0,
      "range": "40-60%",
      "description": "New feature improvement target"
    }
  }
}
```

## Troubleshooting

### Import Errors
```bash
# Ensure Python path includes parent directory
export PYTHONPATH="${PYTHONPATH}:C:/Users/17175/Desktop/fog-compute/src"
```

### Permission Errors (Windows)
```bash
# Run with appropriate permissions
python -m src.fog.benchmarks.run_benchmarks --mode full
```

### Missing Dependencies
```bash
pip install asyncio psutil
```

### Benchmark Failures
Check logs in output directory:
```bash
cat fog-compute/reports/benchmark_suite.log
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: Fog Compute Benchmarks
on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install asyncio psutil
      - name: Run benchmarks
        run: |
          python src/fog/benchmarks/run_benchmarks.py --mode quick
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: fog-compute/reports/
```

## Next Steps

1. **Populate Modules**: Add real implementations to `coordinator/`, `scheduler/`, `monitoring/`
2. **Wire Benchmarks**: Replace simulated delays with actual fog operations
3. **Baseline Comparison**: Establish production baselines for accurate improvements
4. **Continuous Monitoring**: Set up automated benchmark runs in CI/CD
5. **Performance Regression Alerts**: Configure notifications for failing benchmarks