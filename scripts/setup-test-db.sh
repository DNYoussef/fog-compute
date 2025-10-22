#!/bin/bash
# Setup Test Database and Seed Data
#
# Usage:
#   ./scripts/setup-test-db.sh           # Full seed
#   ./scripts/setup-test-db.sh --quick   # Quick seed
#   ./scripts/setup-test-db.sh --docker  # Start DB in Docker first

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo -e "🗄️  Test Database Setup & Seeding"
echo -e "======================================${NC}\n"

# Parse arguments
QUICK_MODE=false
DOCKER_MODE=false

for arg in "$@"; do
  case $arg in
    --quick)
      QUICK_MODE=true
      shift
      ;;
    --docker)
      DOCKER_MODE=true
      shift
      ;;
  esac
done

# Step 1: Start PostgreSQL in Docker (if requested)
if [ "$DOCKER_MODE" = true ]; then
  echo -e "${YELLOW}🐳 Starting PostgreSQL in Docker...${NC}"
  docker run -d \
    --name fog-compute-test-db \
    -p 5432:5432 \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=fog_compute_test \
    postgres:15 \
    || echo "Container already running"

  echo -e "${GREEN}✅ PostgreSQL container started${NC}"
  echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
  sleep 5
fi

# Step 2: Verify PostgreSQL is running
echo -e "${YELLOW}🔍 Checking PostgreSQL connection...${NC}"
if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
  echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
else
  echo -e "${YELLOW}⚠️  PostgreSQL not detected. Attempting to start...${NC}"
  if command -v brew &> /dev/null && brew services list | grep -q "postgresql.*started"; then
    echo -e "${GREEN}✅ PostgreSQL already running (via Homebrew)${NC}"
  elif command -v systemctl &> /dev/null; then
    sudo systemctl start postgresql
    echo -e "${GREEN}✅ PostgreSQL started (via systemctl)${NC}"
  else
    echo -e "${YELLOW}⚠️  Could not start PostgreSQL automatically.${NC}"
    echo -e "${YELLOW}   Please start PostgreSQL manually or use --docker flag${NC}"
    echo -e "${YELLOW}   Example: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15${NC}"
    exit 1
  fi
fi

# Step 3: Create test database (if not exists)
echo -e "\n${YELLOW}📦 Creating test database...${NC}"
if psql -U postgres -lqt | cut -d \| -f 1 | grep -qw fog_compute_test; then
  echo -e "${BLUE}ℹ️  Database 'fog_compute_test' already exists${NC}"
else
  createdb -U postgres fog_compute_test || true
  echo -e "${GREEN}✅ Database 'fog_compute_test' created${NC}"
fi

# Step 4: Install Python dependencies (if needed)
echo -e "\n${YELLOW}📚 Checking Python dependencies...${NC}"
if python -c "import asyncpg" 2>/dev/null; then
  echo -e "${GREEN}✅ Dependencies installed${NC}"
else
  echo -e "${YELLOW}⏳ Installing dependencies...${NC}"
  pip install -q asyncpg sqlalchemy alembic psycopg2-binary
  echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

# Step 5: Run seed script
echo -e "\n${YELLOW}🌱 Seeding test database...${NC}"
cd "$(dirname "$0")/.."

if [ "$QUICK_MODE" = true ]; then
  echo -e "${BLUE}ℹ️  Running in QUICK mode (minimal data)${NC}"
  python -m backend.server.tests.fixtures.seed_data --quick
else
  echo -e "${BLUE}ℹ️  Running FULL seed (215 records)${NC}"
  python -m backend.server.tests.fixtures.seed_data
fi

# Step 6: Verify seeding
echo -e "\n${YELLOW}🔍 Verifying seed data...${NC}"
VERIFICATION=$(psql -U postgres -d fog_compute_test -t -c "
  SELECT
    (SELECT COUNT(*) FROM jobs) as jobs,
    (SELECT COUNT(*) FROM devices) as devices,
    (SELECT COUNT(*) FROM betanet_nodes) as nodes,
    (SELECT COUNT(*) FROM token_balances) as balances,
    (SELECT COUNT(*) FROM circuits) as circuits;
")

echo -e "${GREEN}✅ Seed verification:${NC}"
echo "$VERIFICATION" | awk '{print "   Jobs: "$1", Devices: "$2", Nodes: "$3", Balances: "$4", Circuits: "$5}'

echo -e "\n${BLUE}======================================"
echo -e "✨ Setup Complete!"
echo -e "======================================${NC}"
echo -e "${GREEN}Database URL:${NC} postgresql://postgres:postgres@localhost:5432/fog_compute_test"
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Start backend: ${YELLOW}python backend/server/main.py${NC}"
echo -e "  2. Start frontend: ${YELLOW}cd apps/control-panel && npm run dev${NC}"
echo -e "  3. Run E2E tests: ${YELLOW}npx playwright test${NC}"
echo -e "${BLUE}======================================${NC}\n"
