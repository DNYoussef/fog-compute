# Test Fixtures - Database Seed Data

This directory contains test data seeding utilities for E2E and integration testing.

## Quick Start

### Full Seed (Recommended for comprehensive testing)
```bash
# From project root
python -m backend.server.tests.fixtures.seed_data
```

**Creates:**
- 15 Betanet mixnodes (varied regions, statuses)
- 50 Jobs (10 pending, 10 running, 25 completed, 5 failed)
- 100 Devices (50 Android, 30 iOS, 20 Desktop)
- 10 Token balances
- 20 VPN/Onion circuits
- 5 DAO proposals
- 5 Staking records

**Total:** 215 database records

### Quick Seed (Fast mode for rapid testing)
```bash
python -m backend.server.tests.fixtures.seed_data --quick
```

**Creates:**
- 15 Betanet nodes
- 10 Jobs
- 20 Devices

**Total:** 45 database records (10x faster)

## Configuration

### Database URL
The seed script uses a test database by default:
```python
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/fog_compute_test"
```

To use a different database, set the `DATABASE_URL` environment variable:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:port/dbname"
python -m backend.server.tests.fixtures.seed_data
```

## Integration with Playwright

The seed script is automatically called before E2E tests run. See `playwright.config.ts`:

```typescript
webServer: [
  {
    command: 'cd backend/server && python -m uvicorn main:app --port 8000',
    url: 'http://localhost:8000/health',
  },
  {
    command: 'cd apps/control-panel && npm run dev',
    url: 'http://localhost:3000',
  },
],
```

To seed before tests:
```bash
# 1. Start database
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15

# 2. Seed data
python -m backend.server.tests.fixtures.seed_data

# 3. Run tests
npx playwright test
```

## Data Characteristics

### Betanet Nodes
- **Regions:** us-east, us-west, eu-west, eu-central, ap-south, ap-northeast
- **Statuses:** 80% active, 10% deploying, 10% stopped
- **Uptime:** 1 hour to 30 days
- **Packets:** 10k to 1M processed

### Jobs
- **SLA Tiers:** Platinum, Gold, Silver, Bronze (distributed evenly)
- **Statuses:**
  - Pending (10): Recently submitted, no node assigned
  - Running (10): Assigned to nodes, 10-90% progress
  - Completed (25): Finished successfully with results
  - Failed (5): Terminated with errors
- **Resources:** 0.5-8 CPU cores, 512-16384 MB RAM, 0-2 GPUs

### Devices
- **Android (50):** 4-8 cores, 2-8 GB RAM, 20-100% battery
- **iOS (30):** 4-6 cores, 3-6 GB RAM, 30-100% battery
- **Desktop (20):** 4-16 cores, 8-32 GB RAM, always plugged in
- **Statuses:** idle, active, harvesting, offline (distributed)
- **Temperature:** 35-70°C (realistic ranges)

### Token Balances
- **Addresses:** 10 unique Ethereum-style addresses
- **Balances:** 1,000 to 1,000,000 tokens
- **Staked:** 0 to 500,000 tokens
- **Rewards:** 0 to 50,000 tokens accrued

### Circuits
- **Hops:** 3-5 node hops (Tor-style routing)
- **Bandwidth:** 1-100 Mbps
- **Latency:** 10-150 ms
- **Health:** 0.5-1.0 (70% healthy circuits)
- **Lifecycle:** 70% active, 30% destroyed

### DAO Proposals
- **Statuses:**
  - Active (2): Currently being voted on
  - Passed (1): Approved, not yet executed
  - Rejected (1): Failed vote
  - Executed (1): Implemented
- **Votes:** 100-10,000 for, 50-5,000 against
- **Topics:** Rewards, infrastructure, governance, security, tokenomics

### Stakes
- **Amounts:** 10,000 to full staked balance
- **Rewards:** 100 to 5,000 tokens earned
- **Duration:** 30 to 180 days
- **Status:** 80% active, 20% unstaked

## Programmatic Usage

```python
from backend.server.tests.fixtures import seed_all_data, quick_seed

# Full seed
await seed_all_data()

# Quick seed
await quick_seed()
```

## Validation

After seeding, verify data integrity:
```bash
# Check counts
psql -U postgres -d fog_compute_test -c "
    SELECT 'jobs' as table, count(*) FROM jobs
    UNION ALL SELECT 'devices', count(*) FROM devices
    UNION ALL SELECT 'betanet_nodes', count(*) FROM betanet_nodes;
"
```

Expected output:
```
    table     | count
--------------+-------
 jobs         |    50
 devices      |   100
 betanet_nodes|    15
```

## Troubleshooting

### "Database does not exist"
```bash
createdb fog_compute_test
```

### "Connection refused"
Ensure PostgreSQL is running:
```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15
```

### "Module not found"
Run from project root:
```bash
cd /path/to/fog-compute
python -m backend.server.tests.fixtures.seed_data
```

## Testing Strategy

1. **Pre-test seeding:** Run seed script before E2E tests
2. **Isolation:** Each test run uses fresh seed data (tables dropped/created)
3. **Idempotency:** Safe to run multiple times (drops/recreates all tables)
4. **Determinism:** Random seeds use consistent patterns for reproducibility

## Future Enhancements

- [ ] Add command-line arguments for custom counts
- [ ] Support JSON import/export of seed data
- [ ] Add seed profiles (small, medium, large, stress)
- [ ] Implement incremental seeding (append vs replace)
- [ ] Add data validation post-seed
- [ ] Support multiple database backends

---

**Generated with Claude Code**
**Co-Authored-By:** Claude <noreply@anthropic.com>
