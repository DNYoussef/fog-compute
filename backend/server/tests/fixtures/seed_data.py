"""
Test Database Seed Data
Creates realistic data for E2E testing

Usage:
    python -m backend.server.tests.fixtures.seed_data
    OR
    from backend.server.tests.fixtures.seed_data import seed_all_data
    await seed_all_data()
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
import random

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.server.models.database import (
    Base, Job, TokenBalance, Device, Circuit,
    DAOProposal, Stake, BetanetNode
)
from backend.tests.constants import (
    ONE_DAY,
    ONE_HOUR,
    ONE_MINUTE,
    TEST_MAX_LOGIN_ATTEMPTS,
    TEST_PAGE_SIZE,
    TEST_TIMEOUT_MEDIUM,
)


# Database URL - Read from environment (set by CI) or use local default
# CI may provide postgres:// or postgresql://, normalize to postgresql+asyncpg://
db_url = os.environ.get(
    'DATABASE_URL',
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fog_compute_test"
)

# Ensure asyncpg driver is used (CI might provide postgres:// or postgresql:// without +asyncpg)
if db_url.startswith('postgresql://') and '+asyncpg' not in db_url:
    db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
elif db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)

DATABASE_URL = db_url


async def create_tables(engine):
    """Create all database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Database tables created")


async def seed_betanet_nodes(session: AsyncSession):
    """Seed 15 Betanet mixnodes with realistic data"""
    regions = ['us-east', 'us-west', 'eu-west', 'eu-central', 'ap-south', 'ap-northeast']
    statuses = ['active', 'active', 'active', 'active', 'deploying', 'stopped']

    nodes = []
    for i in range(TEST_PAGE_SIZE + TEST_MAX_LOGIN_ATTEMPTS):
        node = BetanetNode(
            node_id=uuid.uuid4(),
            node_type='mixnode',
            region=random.choice(regions),
            status=random.choice(statuses),
            ip_address=f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
            packets_processed=random.randint(10000, 1000000),
            uptime_seconds=random.randint(ONE_HOUR, ONE_DAY * 30),  # 1 hour to 30 days
            deployed_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 60)),
            last_seen=datetime.now(timezone.utc) - timedelta(minutes=random.randint(0, TEST_TIMEOUT_MEDIUM))
        )
        nodes.append(node)

    session.add_all(nodes)
    await session.commit()
    print(f"[OK] Created {len(nodes)} Betanet nodes")
    return nodes


async def seed_jobs(session: AsyncSession):
    """Seed 50 jobs with varied statuses and SLA tiers"""
    sla_tiers = ['platinum', 'gold', 'silver', 'bronze']
    statuses = {
        'pending': 10,
        'running': 10,
        'completed': 25,
        'failed': 5
    }

    jobs = []
    job_count = 0

    for status, count in statuses.items():
        for i in range(count):
            job_count += 1

            # Calculate timestamps based on status
            submitted_at = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72))
            started_at = submitted_at + timedelta(minutes=random.randint(1, TEST_TIMEOUT_MEDIUM)) if status != 'pending' else None
            completed_at = started_at + timedelta(
                minutes=random.randint(TEST_MAX_LOGIN_ATTEMPTS, TEST_TIMEOUT_MEDIUM * 4)
            ) if status in ['completed', 'failed'] else None

            job = Job(
                id=uuid.uuid4(),
                name=f"job-{job_count:03d}-{random.choice(['ml-training', 'data-processing', 'video-transcode', 'simulation'])}",
                sla_tier=random.choice(sla_tiers),
                status=status,
                cpu_required=round(random.uniform(0.5, 8.0), 2),
                memory_required=round(random.uniform(512, 16384), 2),  # MB
                gpu_required=round(random.uniform(0.0, 2.0), 2) if random.random() > 0.7 else 0.0,
                duration_estimate=round(random.uniform(ONE_MINUTE, ONE_HOUR), 2),  # seconds
                data_size_mb=round(random.uniform(100, 10000), 2),
                assigned_node=f"node-{random.randint(1, TEST_PAGE_SIZE + TEST_MAX_LOGIN_ATTEMPTS):02d}" if status != 'pending' else None,
                submitted_at=submitted_at,
                started_at=started_at,
                completed_at=completed_at,
                progress=100.0 if status == 'completed' else (random.uniform(10, 90) if status == 'running' else 0.0),
                result={'success': True, 'output_size_mb': random.randint(50, 500)} if status == 'completed' else None,
                logs=f"Job {job_count} execution logs..." if status != 'pending' else None
            )
            jobs.append(job)

    session.add_all(jobs)
    await session.commit()
    print(f"[OK] Created {len(jobs)} jobs")
    return jobs


async def seed_devices(session: AsyncSession):
    """Seed 100 idle compute devices"""
    device_types = {
        'android': 50,
        'ios': 30,
        'desktop': 20
    }
    statuses = ['idle', 'active', 'harvesting', 'offline']

    devices = []
    device_count = 0

    for device_type, count in device_types.items():
        for i in range(count):
            device_count += 1

            # Realistic specs per device type
            if device_type == 'android':
                cpu_cores = random.choice([4, 6, 8])
                memory_mb = random.choice([2048, 4096, 6144, 8192])
                battery = random.uniform(20, 100)
            elif device_type == 'ios':
                cpu_cores = random.choice([4, 6])
                memory_mb = random.choice([3072, 4096, 6144])
                battery = random.uniform(30, 100)
            else:  # desktop
                cpu_cores = random.choice([4, 8, 12, 16])
                memory_mb = random.choice([8192, 16384, 32768])
                battery = 100.0  # Always plugged in

            device = Device(
                device_id=f"{device_type}-{uuid.uuid4().hex[:8]}",
                device_type=device_type,
                status=random.choice(statuses),
                battery_percent=round(battery, 1),
                is_charging=random.random() > 0.6 if device_type != 'desktop' else True,
                cpu_cores=cpu_cores,
                memory_mb=memory_mb,
                cpu_temp_celsius=round(random.uniform(35, 70), 1),
                tasks_completed=random.randint(0, 500),
                compute_hours=round(random.uniform(0, 1000), 2),
                registered_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 90)),
                last_heartbeat=datetime.now(timezone.utc) - timedelta(minutes=random.randint(0, 60))
            )
            devices.append(device)

    session.add_all(devices)
    await session.commit()
    print(f"[OK] Created {len(devices)} devices")
    return devices


async def seed_token_balances(session: AsyncSession):
    """Seed 10 wallet addresses with token balances"""
    balances = []

    for i in range(TEST_PAGE_SIZE):
        balance = TokenBalance(
            address=f"0x{uuid.uuid4().hex[:40]}",  # 42 chars total (0x + 40 hex)
            balance=round(random.uniform(1000, 1000000), 2),
            staked=round(random.uniform(0, 500000), 2),
            rewards=round(random.uniform(0, 50000), 2),
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(30, 365)),
            updated_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
        )
        balances.append(balance)

    session.add_all(balances)
    await session.commit()
    print(f"[OK] Created {len(balances)} token balances")
    return balances


async def seed_circuits(session: AsyncSession):
    """Seed 20 VPN/Onion circuits"""
    circuits = []

    for i in range(TEST_PAGE_SIZE * 2):
        num_hops = random.choice([3, 4, 5])  # Typical onion routing uses 3 hops
        hops = [f"node-{uuid.uuid4().hex[:8]}" for _ in range(num_hops)]

        circuit = Circuit(
            circuit_id=uuid.uuid4(),
            hops=hops,
            bandwidth=round(random.uniform(1.0, 100.0), 2),  # Mbps
            latency_ms=round(random.uniform(10, 150), 2),
            health=round(random.uniform(0.5, 1.0), 2),
            created_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48)),
            destroyed_at=None if random.random() > 0.3 else datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 24))
        )
        circuits.append(circuit)

    session.add_all(circuits)
    await session.commit()
    print(f"[OK] Created {len(circuits)} circuits")
    return circuits


async def seed_dao_proposals(session: AsyncSession, balances):
    """Seed 5 DAO governance proposals"""
    proposals = []

    proposal_titles = [
        "Increase staking rewards by 5%",
        "Deploy mixnodes in Asia-Pacific region",
        "Update network consensus parameters",
        "Allocate funds for security audit",
        "Implement new tokenomics model"
    ]

    statuses = ['active', 'active', 'passed', 'rejected', 'executed']

    for i, title in enumerate(proposal_titles):
        votes_for = random.randint(100, 10000)
        votes_against = random.randint(50, 5000)

        proposal = DAOProposal(
            proposal_id=uuid.uuid4(),
            title=title,
            description=f"Detailed description for proposal: {title}. This proposal aims to improve the fog-compute network by implementing changes that benefit all stakeholders.",
            proposer=balances[i % len(balances)].address,
            status=statuses[i],
            votes_for=votes_for,
            votes_against=votes_against,
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(TEST_MAX_LOGIN_ATTEMPTS, TEST_TIMEOUT_MEDIUM)),
            voting_ends_at=datetime.now(timezone.utc) + timedelta(days=random.randint(1, 14)) if statuses[i] == 'active' else datetime.now(timezone.utc) - timedelta(days=random.randint(1, 7)),
            executed_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, TEST_MAX_LOGIN_ATTEMPTS)) if statuses[i] == 'executed' else None
        )
        proposals.append(proposal)

    session.add_all(proposals)
    await session.commit()
    print(f"[OK] Created {len(proposals)} DAO proposals")
    return proposals


async def seed_stakes(session: AsyncSession, balances):
    """Seed 5 staking records"""
    stakes = []

    for i in range(min(TEST_MAX_LOGIN_ATTEMPTS, len(balances))):
        balance = balances[i]

        stake = Stake(
            stake_id=uuid.uuid4(),
            address=balance.address,
            amount=round(random.uniform(10000, balance.staked), 2) if balance.staked > 10000 else balance.staked,
            rewards_earned=round(random.uniform(100, 5000), 2),
            staked_at=datetime.now(timezone.utc) - timedelta(days=random.randint(30, 180)),
            unstaked_at=None if random.random() > 0.2 else datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
        )
        stakes.append(stake)

    session.add_all(stakes)
    await session.commit()
    print(f"[OK] Created {len(stakes)} stakes")
    return stakes


async def seed_all_data():
    """Main function to seed all test data"""
    print("\n" + "="*60)
    print("[SEED] SEEDING TEST DATABASE")
    print("="*60 + "\n")

    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create tables
    await create_tables(engine)

    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Seed all entities
        print("\n[DATA] Seeding entities...\n")

        nodes = await seed_betanet_nodes(session)
        jobs = await seed_jobs(session)
        devices = await seed_devices(session)
        balances = await seed_token_balances(session)
        circuits = await seed_circuits(session)
        proposals = await seed_dao_proposals(session, balances)
        stakes = await seed_stakes(session, balances)

        print("\n" + "="*60)
        print("*** SEED COMPLETE - Summary:")
        print("="*60)
        print(f"  * Betanet Nodes:  {len(nodes)}")
        print(f"  * Jobs:           {len(jobs)}")
        print(f"  * Devices:        {len(devices)}")
        print(f"  * Token Balances: {len(balances)}")
        print(f"  * Circuits:       {len(circuits)}")
        print(f"  * DAO Proposals:  {len(proposals)}")
        print(f"  * Stakes:         {len(stakes)}")
        print("="*60)
        print(f"  TOTAL RECORDS:    {len(nodes) + len(jobs) + len(devices) + len(balances) + len(circuits) + len(proposals) + len(stakes)}")
        print("="*60 + "\n")

    await engine.dispose()
    return True


async def quick_seed():
    """Quick seed with minimal data for rapid testing"""
    print("\n>>> QUICK SEED MODE (Minimal data for rapid testing)\n")

    engine = create_async_engine(DATABASE_URL, echo=False)
    await create_tables(engine)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Quick seed with reduced counts
        nodes = await seed_betanet_nodes(session)  # Still 15 (reasonable)

        # Seed 10 jobs instead of 50
        jobs = []
        for i in range(TEST_PAGE_SIZE):
            job = Job(
                id=uuid.uuid4(),
                name=f"test-job-{i}",
                sla_tier=random.choice(['platinum', 'gold']),
                status=random.choice(['pending', 'running', 'completed']),
                cpu_required=2.0,
                memory_required=2048.0,
                submitted_at=datetime.now(timezone.utc)
            )
            jobs.append(job)
        session.add_all(jobs)
        await session.commit()

        # Seed 20 devices instead of 100
        devices = []
        for i in range(TEST_PAGE_SIZE * 2):
            device = Device(
                device_id=f"test-device-{i}",
                device_type=random.choice(['android', 'ios', 'desktop']),
                status='active',
                battery_percent=75.0,
                cpu_cores=4,
                memory_mb=4096
            )
            devices.append(device)
        session.add_all(devices)
        await session.commit()

        print(f"[OK] Quick seed complete: {len(nodes)} nodes, {len(jobs)} jobs, {len(devices)} devices\n")

    await engine.dispose()
    return True


if __name__ == "__main__":
    import sys

    # Check for quick mode flag
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(quick_seed())
    else:
        asyncio.run(seed_all_data())
