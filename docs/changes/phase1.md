# Phase 1: Betanet Vertical Rescue

## SIN IDs Closed
- **SIN-001**: Fixed httpx.Timeout to explicitly set all 4 fields (connect, read, write, pool)
- **SIN-002**: Unified deploy_node signature - client now accepts keyword args matching route caller
- **SIN-003**: Backend owns node CRUD (Option B). Routes no longer proxy to Rust /nodes endpoints
- **SIN-004**: Canonical BetanetNode schema with adapter for Rust MixnodeInfoResponse
- **SIN-005**: get_metrics() now parses Prometheus text format instead of expecting JSON
- **SIN-006**: Frontend status route adapts backend response to include mixnodes array and health score
- **SIN-007**: Frontend /api/betanet/nodes and /api/betanet/nodes/[nodeId] routes implemented

## Architecture (Option B)
- BetanetService maintains in-memory node registry
- BetanetClient communicates with Rust server for deploy, status, metrics, mixnodes
- sync_from_rust() merges Rust mixnode data into canonical node schema
- Node CRUD lives entirely in backend (Rust has no /nodes endpoints)
- Mock fallback gated by mock_guard (SIN-032)

## Files Changed
- `backend/server/services/betanet_client.py` - Timeout fix, deploy signature, Prometheus parser
- `backend/server/services/betanet.py` - New BetanetService with CRUD + Rust sync
- `backend/server/routes/betanet.py` - Rewritten to use BetanetService
- `apps/control-panel/app/api/betanet/status/route.ts` - Status adapter with mixnodes+health
- `apps/control-panel/app/api/betanet/nodes/route.ts` - NEW: Node list/create proxy
- `apps/control-panel/app/api/betanet/nodes/[nodeId]/route.ts` - NEW: Node detail/update/delete proxy

## Tests
- 18 integration tests covering all 7 SINs
- Schema conformance validated against betanet-node.schema.json
