# Phase 7: Benchmarks, Scheduler, and UI Truthfulness

## SIN IDs Closed
- **SIN-025**: Benchmark API `/api/benchmarks/data` now returns real psutil metrics (CPU%, memory%, network I/O) instead of static zeros. Reports `source: "psutil"` field. Stop endpoint validates benchmark ID (404 for unknown).
- **SIN-026**: Frontend dashboard stats and benchmark data API routes gate mock fallbacks on `NODE_ENV`. Production returns 503 error instead of silent mock data. Dev fallback includes `_mock: true` flag.
- **SIN-027**: FogMap component fetches from `/api/fog/topology` instead of hardcoded node array. Shows stale-data/unavailable indicator when backend is down. Auto-refreshes every 30 seconds.
- **SIN-028**: Scheduler `_execute_task` delegates to pluggable `ExecutionAdapter` protocol. No inline `random.uniform`/`random.random` in execution path. `SimulatedExecutionAdapter` raises `RuntimeError` in production. `StubExecutionAdapter` provides deterministic test double.
- **SIN-029**: Demo benchmark mode clearly labeled with `[SIMULATED]` tags, `is_demo: true` flag in output, and warning text. Blocked in production (`APP_ENV=production` returns error).

## Changes
- `backend/server/routes/benchmarks.py` - Real psutil metrics, benchmark tracking, ID validation
- `apps/control-panel/app/api/dashboard/stats/route.ts` - Production 503, dev `_mock` flag
- `apps/control-panel/app/api/benchmarks/data/route.ts` - Production 503, dev `_mock` flag
- `apps/control-panel/components/FogMap.tsx` - Topology API fetch, stale indicator, no hardcoded nodes
- `src/scheduler/intelligent_scheduler.py` - ExecutionAdapter protocol, 3 adapter implementations
- `src/fog/benchmarks/run_benchmarks.py` - Demo labeling, production block
- `tests/contracts/test_benchmarks_scheduler.py` - 21 tests

## Key Fixes
- `get_benchmark_data()` uses `psutil.cpu_percent()`, `psutil.virtual_memory()`, `psutil.net_io_counters()`
- `stop_benchmark()` raises `HTTPException(404)` for unknown benchmark IDs
- Dashboard stats route returns `{ status: 503, error: "Backend unavailable" }` in production
- Benchmarks data route returns `{ status: 503, error: "Backend unavailable" }` in production
- FogMap `useEffect` calls `fetch('/api/fog/topology')` with 5s timeout and 30s refresh interval
- `ExecutionAdapter` ABC with abstract `execute(task, worker) -> (time, success)`
- `StubExecutionAdapter` - deterministic: fixed time, fixed success (for tests)
- `SimulatedExecutionAdapter` - random execution (legacy), blocked in production
- `IntelligentScheduler.__init__` accepts optional `execution_adapter` parameter
- `run_demo_mode()` checks `APP_ENV`, returns `success: False` in production
- Demo output tagged with `[SIMULATED]`, `is_demo: true`, warning text
