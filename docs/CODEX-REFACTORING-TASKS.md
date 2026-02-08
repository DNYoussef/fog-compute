# Codex Refactoring Tasks - Prompt Architect Edition

**Purpose**: Four precisely-crafted tasks for Codex to systematically eliminate connascence violations.
**Repository**: DNYoussef/fog-compute
**Branch Strategy**: Each task creates its own branch, PR when complete.

---

## TASK 1: Create Constants Module (Foundation)

### Context
The codebase has 23 critical magic literals representing file sizes and time durations scattered across production files. These must be centralized into a constants module before other refactoring can proceed.

### Objective
Create `backend/server/constants.py` with named constants, then update all files that use these magic numbers.

### Step-by-Step Instructions

**Step 1: Create the constants module**

Create file `backend/server/constants.py` with this exact content:

```python
"""
Centralized constants for the fog-compute backend.

This module contains all magic numbers extracted from the codebase
to improve maintainability and reduce Connascence of Meaning (CoM).
"""

# =============================================================================
# FILE SIZE CONSTANTS (in bytes)
# =============================================================================
ONE_KB: int = 1024
FOUR_KB: int = 4096
SIXTEEN_KB: int = 16384
SIXTY_FOUR_KB: int = 65536

ONE_MB: int = 1048576
TWO_MB: int = 2097152
THREE_MB: int = 3145728
FIVE_MB: int = 5242880
TEN_MB: int = 10485760
FIFTY_MB: int = 52428800
ONE_HUNDRED_MB: int = 104857600

ONE_GB: int = 1073741824

# =============================================================================
# TIME CONSTANTS (in seconds)
# =============================================================================
ONE_SECOND: int = 1
FIVE_SECONDS: int = 5
TEN_SECONDS: int = 10
FIFTEEN_SECONDS: int = 15
THIRTY_SECONDS: int = 30

ONE_MINUTE: int = 60
FIVE_MINUTES: int = 300
TEN_MINUTES: int = 600
FIFTEEN_MINUTES: int = 900
THIRTY_MINUTES: int = 1800

ONE_HOUR: int = 3600
TWO_HOURS: int = 7200
SIX_HOURS: int = 21600
TWELVE_HOURS: int = 43200

ONE_DAY: int = 86400
TWO_DAYS: int = 172800
ONE_WEEK: int = 604800
TWO_WEEKS: int = 1209600
THIRTY_DAYS: int = 2592000
NINETY_DAYS: int = 7776000
ONE_YEAR: int = 31536000

# =============================================================================
# NETWORK CONSTANTS
# =============================================================================
DEFAULT_PORT: int = 8000
DEFAULT_TIMEOUT: int = 30
MAX_RETRIES: int = 3
BACKOFF_FACTOR: float = 1.5

# =============================================================================
# PAGINATION CONSTANTS
# =============================================================================
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# =============================================================================
# SECURITY CONSTANTS
# =============================================================================
HSTS_MAX_AGE: int = ONE_YEAR  # 31536000 seconds
SESSION_EXPIRY: int = THIRTY_DAYS
TOKEN_EXPIRY: int = ONE_HOUR
REFRESH_TOKEN_EXPIRY: int = ONE_WEEK

# =============================================================================
# BITCHAT CONSTANTS
# =============================================================================
MAX_MESSAGE_SIZE: int = ONE_MB
MAX_FILE_UPLOAD_SIZE: int = FIVE_MB
MAX_GROUP_FILE_SIZE: int = TEN_MB
MAX_ATTACHMENT_SIZE: int = ONE_GB

# =============================================================================
# RESOURCE MONITORING CONSTANTS
# =============================================================================
MEMORY_CHECK_INTERVAL: int = THIRTY_SECONDS
CPU_CHECK_INTERVAL: int = TEN_SECONDS
DISK_CHECK_INTERVAL: int = ONE_MINUTE
METRICS_AGGREGATION_INTERVAL: int = FIVE_MINUTES
```

**Step 2: Update these specific files**

For each file below, find the magic number and replace with the appropriate constant:

| File | Line | Magic Number | Replace With |
|------|------|--------------|--------------|
| `backend/server/middleware/security_headers.py` | 34 | `31536000` | `HSTS_MAX_AGE` |
| `backend/server/models/database.py` | 587 | `1048576` | `ONE_MB` |
| `backend/server/routes/bitchat.py` | 142 | `1073741824` | `MAX_ATTACHMENT_SIZE` |
| `backend/server/services/file_transfer.py` | 69 | `1048576` | `ONE_MB` |
| `backend/alembic/versions/002_add_bitchat_advanced_features.py` | 57 | `1048576` | `ONE_MB` |

**Step 3: Add import to each updated file**

At the top of each file, add:
```python
from backend.server.constants import <CONSTANT_NAME>
```

Or if relative imports are used:
```python
from ..constants import <CONSTANT_NAME>
```

**Step 4: Verify changes**

Run these commands to verify:
```bash
# Check syntax
python -m py_compile backend/server/constants.py

# Run existing tests to ensure no regressions
python -m pytest backend/tests/ -x -q --tb=short

# Verify imports work
python -c "from backend.server.constants import ONE_MB, HSTS_MAX_AGE; print('Constants OK')"
```

### Success Criteria
- [ ] `backend/server/constants.py` exists with all constants
- [ ] All 5 files updated with imports and constant references
- [ ] `python -m py_compile` passes for all modified files
- [ ] Existing tests pass (no regressions)

### Git Instructions
```bash
git checkout -b refactor/constants-module
git add backend/server/constants.py
git add backend/server/middleware/security_headers.py
git add backend/server/models/database.py
git add backend/server/routes/bitchat.py
git add backend/server/services/file_transfer.py
git add backend/alembic/versions/002_add_bitchat_advanced_features.py
git commit -m "refactor: Extract magic literals to constants module

- Create backend/server/constants.py with file size and time constants
- Update security_headers.py to use HSTS_MAX_AGE
- Update database.py to use ONE_MB
- Update bitchat.py to use MAX_ATTACHMENT_SIZE
- Update file_transfer.py to use ONE_MB
- Update migration file to use ONE_MB

Addresses 23 critical CoM (Connascence of Meaning) violations."
```

---

## TASK 2: Type Annotations for Database Models

### Context
61 production functions are missing type annotations. This task focuses on the database models layer which has the highest concentration of missing types.

### Objective
Add comprehensive Python 3.10+ type annotations to all functions in the database model files.

### Step-by-Step Instructions

**Step 1: Read and understand current state**

Read these files first to understand the existing code:
- `backend/server/models/database.py`
- `backend/server/models/deployment.py`
- `backend/server/models/rewards.py`
- `backend/server/models/usage.py`
- `backend/server/models/audit_log.py`

**Step 2: Apply type annotation rules**

For EVERY function in these files:

1. **Parameters**: Add type hints to ALL parameters
   ```python
   # Before
   def get_user(user_id, include_deleted=False):

   # After
   def get_user(user_id: int, include_deleted: bool = False) -> User | None:
   ```

2. **Return types**: Add return type to ALL functions
   ```python
   # Before
   def create_deployment(data):

   # After
   def create_deployment(data: DeploymentCreate) -> Deployment:
   ```

3. **Use modern syntax** (Python 3.10+):
   - Use `X | None` instead of `Optional[X]`
   - Use `list[X]` instead of `List[X]`
   - Use `dict[K, V]` instead of `Dict[K, V]`

4. **SQLAlchemy models**: For model classes, type class attributes:
   ```python
   class User(Base):
       __tablename__: str = "users"
       id: Mapped[int] = mapped_column(primary_key=True)
       email: Mapped[str] = mapped_column(String(255), unique=True)
       created_at: Mapped[datetime] = mapped_column(default=func.now())
   ```

5. **Async functions**: Include Coroutine return types or use async-specific patterns:
   ```python
   async def get_user_async(user_id: int) -> User | None:
   ```

**Step 3: Add necessary imports**

Ensure these imports are present:
```python
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
```

**Step 4: Verify with mypy**

Run type checking:
```bash
# Install mypy if needed
pip install mypy

# Run mypy on the models directory
python -m mypy backend/server/models/ --ignore-missing-imports --no-error-summary

# If mypy finds errors, fix them before committing
```

**Step 5: Run tests**

```bash
python -m pytest backend/tests/ -x -q --tb=short
```

### Success Criteria
- [ ] ALL functions in models/ have parameter type hints
- [ ] ALL functions in models/ have return type hints
- [ ] mypy passes with no errors on models/
- [ ] Existing tests pass

### Git Instructions
```bash
git checkout -b refactor/type-annotations-models
git add backend/server/models/
git commit -m "refactor: Add comprehensive type annotations to database models

- Add parameter and return type hints to all functions
- Use Python 3.10+ syntax (X | None, list[X])
- Update SQLAlchemy model type annotations
- Addresses 61 CoT (Connascence of Type) violations in models layer"
```

---

## TASK 3: Service Layer Magic Literal Extraction

### Context
The service layer contains 200+ magic literals for timeouts, buffer sizes, thresholds, and intervals. These need to be extracted to the constants module created in Task 1.

### Prerequisites
Task 1 must be completed first (constants module must exist).

### Objective
Refactor all magic literals in service files to use named constants.

### Step-by-Step Instructions

**Step 1: Analyze each service file**

Read these files and identify ALL numeric literals:
- `backend/server/services/betanet.py` (58 violations)
- `backend/server/services/resource_monitor.py` (45 violations)
- `backend/server/services/memory_profiler.py` (36 violations)
- `backend/server/services/scheduler.py` (30 violations)
- `backend/server/services/metrics_aggregator.py` (17 violations)
- `backend/server/services/enhanced_service_manager.py` (15 violations)

**Step 2: Categorize literals**

Group magic numbers by semantic meaning:

| Category | Examples | Constant Pattern |
|----------|----------|------------------|
| Timeouts | 30, 60, 300 | `*_TIMEOUT` |
| Intervals | 10, 30, 60 | `*_INTERVAL` |
| Buffer sizes | 1024, 4096 | `*_BUFFER_SIZE` |
| Thresholds | 80, 90, 95 | `*_THRESHOLD` |
| Limits | 100, 1000 | `MAX_*` or `*_LIMIT` |
| Retry counts | 3, 5 | `*_RETRIES` |

**Step 3: Add service-specific constants to constants.py**

Append to `backend/server/constants.py`:

```python
# =============================================================================
# BETANET SERVICE CONSTANTS
# =============================================================================
BETANET_CONNECTION_TIMEOUT: int = THIRTY_SECONDS
BETANET_READ_TIMEOUT: int = ONE_MINUTE
BETANET_MAX_RETRIES: int = 3
BETANET_BUFFER_SIZE: int = SIXTY_FOUR_KB

# =============================================================================
# RESOURCE MONITOR CONSTANTS
# =============================================================================
CPU_THRESHOLD_WARNING: int = 80
CPU_THRESHOLD_CRITICAL: int = 95
MEMORY_THRESHOLD_WARNING: int = 80
MEMORY_THRESHOLD_CRITICAL: int = 90
DISK_THRESHOLD_WARNING: int = 85
DISK_THRESHOLD_CRITICAL: int = 95

# =============================================================================
# SCHEDULER CONSTANTS
# =============================================================================
SCHEDULER_CHECK_INTERVAL: int = TEN_SECONDS
SCHEDULER_CLEANUP_INTERVAL: int = ONE_HOUR
SCHEDULER_MAX_CONCURRENT_JOBS: int = 10

# =============================================================================
# METRICS AGGREGATOR CONSTANTS
# =============================================================================
METRICS_BATCH_SIZE: int = 100
METRICS_FLUSH_INTERVAL: int = THIRTY_SECONDS
METRICS_RETENTION_PERIOD: int = THIRTY_DAYS
```

**Step 4: Update each service file**

For each file:
1. Add import: `from backend.server.constants import <constants>`
2. Replace each magic number with its named constant
3. Add comments explaining non-obvious values

Example transformation:
```python
# Before
async def check_health(self):
    timeout = 30
    if cpu_usage > 80:
        logger.warning("High CPU")
    if cpu_usage > 95:
        raise ResourceExhausted()

# After
from backend.server.constants import (
    BETANET_CONNECTION_TIMEOUT,
    CPU_THRESHOLD_WARNING,
    CPU_THRESHOLD_CRITICAL,
)

async def check_health(self):
    timeout = BETANET_CONNECTION_TIMEOUT
    if cpu_usage > CPU_THRESHOLD_WARNING:
        logger.warning("High CPU")
    if cpu_usage > CPU_THRESHOLD_CRITICAL:
        raise ResourceExhausted()
```

**Step 5: Verify no hardcoded numbers remain**

Run this grep to find remaining magic numbers:
```bash
grep -rn "[^a-zA-Z_][0-9]\{2,\}[^a-zA-Z_0-9]" backend/server/services/*.py | grep -v "^#" | grep -v "import"
```

**Step 6: Run tests**

```bash
python -m pytest backend/tests/ -x -q --tb=short
```

### Success Criteria
- [ ] All 6 service files updated
- [ ] constants.py extended with service-specific constants
- [ ] grep finds no remaining magic numbers (except in strings/comments)
- [ ] All tests pass

### Git Instructions
```bash
git checkout -b refactor/service-layer-constants
git add backend/server/constants.py
git add backend/server/services/
git commit -m "refactor: Extract magic literals from service layer

- Add service-specific constants to constants.py
- Update betanet.py (58 literals)
- Update resource_monitor.py (45 literals)
- Update memory_profiler.py (36 literals)
- Update scheduler.py (30 literals)
- Update metrics_aggregator.py (17 literals)
- Update enhanced_service_manager.py (15 literals)

Addresses 201 CoM violations in service layer"
```

---

## TASK 4: Test File Constants (Optional Hygiene)

### Context
Test files contain 755 magic literals. While lower priority than production code, cleaning these improves test maintainability.

### Objective
Create a test constants module and update the top 5 most-violated test files.

### Step-by-Step Instructions

**Step 1: Create test constants file**

Create `backend/tests/constants.py`:

```python
"""
Test-specific constants for fog-compute backend tests.

Separating test constants from production constants to:
1. Keep test values isolated from production
2. Make test data obvious and intentional
3. Allow test-specific overrides
"""

from backend.server.constants import (
    ONE_MB,
    FIVE_MB,
    TEN_MB,
    ONE_GB,
    ONE_MINUTE,
    ONE_HOUR,
    ONE_DAY,
)

# =============================================================================
# TEST FILE SIZES
# =============================================================================
TEST_SMALL_FILE_SIZE: int = ONE_MB
TEST_MEDIUM_FILE_SIZE: int = FIVE_MB
TEST_LARGE_FILE_SIZE: int = TEN_MB
TEST_MAX_FILE_SIZE: int = ONE_GB

# Sample file content for tests
TEST_FILE_CONTENT: bytes = b"x" * 1024  # 1KB of data

# =============================================================================
# TEST TIMEOUTS
# =============================================================================
TEST_TIMEOUT_SHORT: int = 5
TEST_TIMEOUT_MEDIUM: int = 30
TEST_TIMEOUT_LONG: int = 120

# =============================================================================
# TEST USER DATA
# =============================================================================
TEST_USER_EMAIL: str = "test@example.com"
TEST_USER_PASSWORD: str = "TestPassword123!"
TEST_ADMIN_EMAIL: str = "admin@example.com"

# =============================================================================
# TEST NETWORK CONSTANTS
# =============================================================================
TEST_PORT: int = 8000
TEST_HOST: str = "127.0.0.1"
TEST_BASE_URL: str = f"http://{TEST_HOST}:{TEST_PORT}"

# =============================================================================
# TEST PAGINATION
# =============================================================================
TEST_PAGE_SIZE: int = 10
TEST_MAX_RESULTS: int = 100

# =============================================================================
# TEST SECURITY CONSTANTS
# =============================================================================
TEST_MAX_LOGIN_ATTEMPTS: int = 5
TEST_LOCKOUT_DURATION: int = 300  # 5 minutes
TEST_TOKEN_LENGTH: int = 32
```

**Step 2: Update top 5 test files**

Update these files to use test constants:
1. `backend/tests/security/test_file_upload_security.py` (123 violations)
2. `backend/server/tests/fixtures/seed_data.py` (98 violations)
3. `backend/tests/security/test_production_hardening.py` (98 violations)
4. `backend/tests/test_resource_optimization.py` (78 violations)
5. `backend/tests/test_fog_optimization.py` (67 violations)

**Step 3: Add imports to each test file**

```python
from backend.tests.constants import (
    TEST_SMALL_FILE_SIZE,
    TEST_LARGE_FILE_SIZE,
    TEST_TIMEOUT_SHORT,
    # ... other constants as needed
)
```

**Step 4: Run test suite**

```bash
python -m pytest backend/tests/ -v --tb=short
```

### Success Criteria
- [ ] `backend/tests/constants.py` created
- [ ] Top 5 test files updated
- [ ] All tests pass

### Git Instructions
```bash
git checkout -b refactor/test-constants
git add backend/tests/constants.py
git add backend/tests/security/
git add backend/tests/test_*.py
git add backend/server/tests/
git commit -m "refactor: Create test constants module

- Create backend/tests/constants.py with test-specific values
- Update top 5 test files with most magic literals
- Improves test maintainability and readability

Addresses 464 CoM violations in test files"
```

---

## Execution Order

```
TASK 1 (Foundation)
    |
    +---> TASK 2 (Independent, can run parallel)
    |
    +---> TASK 3 (Depends on Task 1)
              |
              +---> TASK 4 (Depends on Task 1)
```

**Recommended Codex Execution**:
1. Submit TASK 1 first - wait for completion
2. Submit TASK 2 and TASK 3 in parallel (after Task 1 merges)
3. Submit TASK 4 last (lowest priority)

---

## Post-Execution Validation

After all tasks complete, run full connascence analysis:

```bash
cd D:\Projects\connascence
python -m cli.connascence scan D:/Projects/fog-compute/backend --policy strict-core --format json
```

**Expected Results**:
- Total violations: < 500 (down from 1551)
- Production violations: < 200 (down from 697)
- Critical violations: 0 (down from 23)

---

**Document Version**: 1.0
**Created**: 2026-01-04
**Author**: Claude (Prompt Architect Pattern)
