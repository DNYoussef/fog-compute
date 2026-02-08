# Phase 0: Contracts and Mock Policy

## SIN IDs Addressed
- **SIN-031**: Contract test scaffold added (`tests/contracts/`)
- **SIN-032**: Global mock guard and APP_ENV policy

## Changes

### Canonical JSON Schemas (`docs/contracts/`)
- `betanet-status.schema.json` - GET /api/betanet/status response
- `betanet-node.schema.json` - Betanet node object
- `idle-device.schema.json` - Idle compute device object
- `benchmark-data.schema.json` - GET /api/benchmarks/data response

### Environment Policy (`backend/server/config.py`)
- Added `APP_ENV` setting (development|staging|production)
- Added `ALLOW_MOCKS` setting (default true, forbidden in production)
- Startup validator rejects ALLOW_MOCKS=true when APP_ENV=production

### Mock Guard (`backend/server/mock_guard.py`)
- `allow_mock_fallback()` - check before serving mock data
- `guard_mock(context)` - raises MockNotAllowedError in production
- All mock code paths should call this before returning fake data

### Contract Test Scaffold (`tests/contracts/`)
- Schema validation helpers using jsonschema
- Tests for all 4 canonical schemas
- Mock guard unit tests

## Architectural Decision: BLOCKER-B1
**Decision: Option B** - Backend owns public API contracts and persistence.
Rust Betanet provides transport and metrics only. Backend adapts Rust data
into canonical schemas.

## Architectural Decision: BLOCKER-B2
**Decision**: ALLOW_MOCKS=false default in production. Mock code paths
raise MockNotAllowedError at runtime.

## Architectural Decision: BLOCKER-B3
**Decision**: JSON Schema snapshots in docs/contracts/ are the contract
source of truth. Contract tests in CI validate conformance.
