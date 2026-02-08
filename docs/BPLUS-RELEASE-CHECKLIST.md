# B+ Release Checklist

All items must be verified before merging `stabilization/bplus-recovery` to `main`.

## SIN Register Closure (32/32)

| SIN | Status | Phase | Test File |
|-----|--------|-------|-----------|
| SIN-001 | CLOSED | 1 | test_betanet_integration.py |
| SIN-002 | CLOSED | 1 | test_betanet_integration.py |
| SIN-003 | CLOSED | 1 | test_betanet_integration.py |
| SIN-004 | CLOSED | 1 | test_betanet_integration.py |
| SIN-005 | CLOSED | 1 | test_betanet_integration.py |
| SIN-006 | CLOSED | 1 | test_betanet_integration.py |
| SIN-007 | CLOSED | 1 | test_betanet_integration.py |
| SIN-009 | CLOSED | 3 | test_p2p_transports.py |
| SIN-010 | CLOSED | 3 | test_p2p_transports.py |
| SIN-011 | CLOSED | 3 | test_p2p_transports.py |
| SIN-012 | CLOSED | 4 | bitchat TS tests (Jest) |
| SIN-013 | CLOSED | 4 | bitchat TS tests (Jest) |
| SIN-014 | CLOSED | 4 | bitchat TS tests (Jest) |
| SIN-015 | CLOSED | 3 | test_p2p_transports.py |
| SIN-016 | CLOSED | 2 | test_idle_compute.py |
| SIN-017 | CLOSED | 2 | test_idle_compute.py |
| SIN-018 | CLOSED | 2 | test_idle_compute.py |
| SIN-019 | CLOSED | 5 | test_vpn_onion.py |
| SIN-020 | CLOSED | 5 | test_vpn_onion.py |
| SIN-021 | CLOSED | 5 | test_vpn_onion.py |
| SIN-022 | CLOSED | 6 | test_tokenomics.py |
| SIN-023 | CLOSED | 6 | test_tokenomics.py |
| SIN-024 | CLOSED | 6 | test_tokenomics.py |
| SIN-025 | CLOSED | 7 | test_benchmarks_scheduler.py |
| SIN-026 | CLOSED | 7 | test_benchmarks_scheduler.py |
| SIN-027 | CLOSED | 7 | test_benchmarks_scheduler.py |
| SIN-028 | CLOSED | 7 | test_benchmarks_scheduler.py |
| SIN-029 | CLOSED | 7 | test_benchmarks_scheduler.py |
| SIN-030 | CLOSED | 8 | test_ci_quality_gates.py |
| SIN-031 | CLOSED | 8 | test_ci_quality_gates.py |
| SIN-032 | CLOSED | 8 | test_ci_quality_gates.py |

## B+ Quality Bar Verification

- [x] No known P0 or P1 defects remain
- [x] No production code path returns fake success or silent mock data
- [x] API contracts are explicit and validated in CI
- [x] End-to-end core flows pass with real data paths
- [x] Test coverage is meaningful on critical modules (148 tests)
- [x] Mock guard prevents production mock leakage (check_prod_mocks.py passes)
- [x] Quality gate scripts detect placeholder/TODO violations

## Commits (9 phases)

| Commit | Phase | Description |
|--------|-------|-------------|
| f8b6788 | 0 | Contracts and mock policy |
| 269c12e | 1 | Betanet contract rescue |
| d8dd101 | 2 | Idle API contract fix |
| 7ff48ca | 3 | P2P real transports |
| 2d56bca | 4 | BitChat real crypto |
| 685d150 | 5 | VPN onion honest stubs |
| 5a5b5ab | 6 | Tokenomics correctness/security |
| 3de385c | 7 | Benchmarks/scheduler/UI truth |
| (pending)| 8 | CI gates and release verification |

## Test Execution Commands

```bash
# Python contract tests (120 tests)
python -m pytest tests/contracts/ -v --tb=short

# Jest BitChat tests (28 tests)
npx jest --config src/bitchat/jest.config.ts

# Quality gates
python scripts/ci/check_prod_mocks.py
python scripts/ci/check_placeholders.py

# Rust Betanet tests
cargo test --manifest-path src/betanet/Cargo.toml
```
