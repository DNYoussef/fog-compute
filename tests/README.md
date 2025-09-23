# Fog-Compute Test Suite

Comprehensive cross-language testing for the Fog-Compute platform with >80% coverage target.

## Test Structure

```
tests/
├── rust/                    # Rust tests for Betanet
│   ├── betanet_unit_tests.rs
│   ├── betanet_integration_tests.rs
│   └── Cargo.toml
├── typescript/              # TypeScript tests for BitChat
│   ├── components.test.tsx
│   ├── hooks.test.ts
│   └── protocol.test.ts
├── python/                  # Python tests for benchmarks
│   ├── test_benchmarks.py
│   ├── test_fog_api.py
│   └── test_performance_metrics.py
├── e2e/                    # End-to-end tests
│   ├── control-panel.spec.ts
│   ├── mobile.spec.ts
│   └── cross-browser.spec.ts
└── performance/            # Performance tests
    ├── system_test.py
    └── network_test.rs
```

## Running Tests

### Rust Tests (Betanet)

```bash
# Run all Rust tests
cd tests/rust
cargo test

# Run specific test
cargo test betanet_unit_tests

# Run with output
cargo test -- --nocapture

# Run benchmarks
cargo test --release
```

### TypeScript Tests (BitChat UI)

```bash
# Run all TypeScript tests
npm test

# Run specific test file
npm test components.test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

### Python Tests (Benchmarks & API)

```bash
# Run all Python tests
pytest tests/python/

# Run specific test file
pytest tests/python/test_benchmarks.py

# Run with coverage
pytest --cov=src/fog --cov-report=html

# Run integration tests only
pytest -m integration
```

### E2E Tests (Playwright)

```bash
# Install Playwright browsers (first time only)
npx playwright install

# Run all E2E tests
npx playwright test

# Run specific browser
npx playwright test --project=chromium

# Run mobile tests
npx playwright test mobile.spec.ts

# Debug mode
npx playwright test --debug

# Show report
npx playwright show-report tests/output/playwright-report
```

### Performance Tests

```bash
# Python system test
python tests/performance/system_test.py

# Rust network test
cd tests/performance
cargo run --bin network_test --release
```

## Test Coverage Goals

| Component | Target | Current |
|-----------|--------|---------|
| Rust (Betanet) | 80% | - |
| TypeScript (UI) | 80% | - |
| Python (Benchmarks) | 80% | - |
| E2E Coverage | Key Flows | - |

## Key Test Categories

### 1. Unit Tests
- **Rust**: Mixnode, crypto, VRF modules
- **TypeScript**: Components, hooks, utilities
- **Python**: Benchmark suite, metrics

### 2. Integration Tests
- **Rust**: Pipeline performance, batch processing
- **TypeScript**: P2P protocols, WebSocket
- **Python**: API endpoints, full workflow

### 3. E2E Tests
- Control panel functionality
- Mobile responsiveness
- Cross-browser compatibility
- Real-time updates

### 4. Performance Tests
- System throughput (25,000 pps target)
- Latency (<1ms target)
- Memory pool efficiency (>85% hit rate)
- Network scalability

## Test Data

Mock data and fixtures are located in:
- `tests/fixtures/` - Shared test data
- `tests/mocks/` - Mock implementations

## Continuous Integration

Tests run automatically on:
- Pull requests
- Main branch commits
- Nightly builds

### CI Commands

```bash
# Run all tests
npm run test:all

# Run CI suite
npm run test:ci

# Generate coverage report
npm run coverage
```

## Performance Targets

### Betanet (Rust)
- ✅ Throughput: ≥25,000 pps
- ✅ Latency: ≤1ms average
- ✅ Memory pool hit rate: ≥85%
- ✅ Packet drop rate: ≤0.1%

### BitChat (TypeScript)
- ✅ Component render: <100ms
- ✅ P2P connection: <500ms
- ✅ Message latency: <50ms

### Benchmarks (Python)
- ✅ Suite completion: <5min
- ✅ All targets met: 100%
- ✅ Grade: A

## Troubleshooting

### Common Issues

**Rust tests failing:**
```bash
# Update dependencies
cargo update
cargo clean && cargo test
```

**TypeScript tests failing:**
```bash
# Clear Jest cache
npm run test -- --clearCache
npm test
```

**Python tests failing:**
```bash
# Reinstall dependencies
pip install -r requirements.txt
pytest --cache-clear
```

**E2E tests failing:**
```bash
# Reinstall Playwright
npx playwright install --force
npx playwright test --debug
```

## Adding New Tests

### Rust Test Template
```rust
#[tokio::test]
async fn test_name() {
    // Arrange
    let config = create_test_config();

    // Act
    let result = perform_action(config).await;

    // Assert
    assert!(result.is_ok());
}
```

### TypeScript Test Template
```typescript
describe('Component', () => {
  it('should render correctly', () => {
    const { getByText } = render(<Component />);
    expect(getByText('text')).toBeInTheDocument();
  });
});
```

### Python Test Template
```python
@pytest.mark.asyncio
async def test_function():
    # Arrange
    suite = FogBenchmarkSuite()

    # Act
    result = await suite.run_test()

    # Assert
    assert result.passed
```

## Test Reports

Reports are generated in:
- `tests/output/coverage/` - Coverage reports
- `tests/output/playwright-report/` - E2E test reports
- `tests/output/benchmark-results/` - Performance results

## Resources

- [Jest Documentation](https://jestjs.io/)
- [Playwright Documentation](https://playwright.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Cargo Test Documentation](https://doc.rust-lang.org/cargo/commands/cargo-test.html)