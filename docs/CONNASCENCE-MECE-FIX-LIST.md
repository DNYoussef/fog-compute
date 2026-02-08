# Connascence MECE Fix List for fog-compute

**Generated**: 2026-01-04
**Policy**: strict-core
**Total Findings**: 1551
**Production Findings**: 697

---

## Executive Summary

The connascence analysis identified **1551 total violations** using the strict-core policy. Of these, **697 are in production files** (non-test code). The fixes are categorized into MECE (Mutually Exclusive, Collectively Exhaustive) groups for systematic refactoring.

---

## MECE Categories

### Category 1: Critical Magic Literals (23 findings)
**Priority**: HIGH
**Type**: CoM (Connascence of Meaning)
**Description**: Large magic numbers representing file sizes and time constants

**Files Affected**:
- `security_headers.py:34` - 31536000 (1 year in seconds)
- `database.py:587` - 1048576 (1MB)
- `bitchat.py:142` - 1073741824 (1GB)
- `file_transfer.py:69` - 1048576 (1MB)
- `seed_data.py:68` - 2592000 (30 days in seconds)
- `002_add_bitchat_advanced_features.py:57` - 1048576 (1MB)

**Recommended Constants**:
```python
# In backend/server/constants.py (new file)
ONE_MB = 1048576
TWO_MB = 2097152
FIVE_MB = 5242880
ONE_GB = 1073741824

ONE_YEAR_SECONDS = 31536000
THIRTY_DAYS_SECONDS = 2592000
```

---

### Category 2: Type Annotation Fixes (61 production + 99 test = 160 total)
**Priority**: MEDIUM
**Type**: CoT (Connascence of Type)
**Description**: Functions missing type hints

**Top Production Files**:
- `database.py` - Missing return type annotations
- `deployment.py` - Missing parameter types
- `resource_monitor.py` - Missing type hints

**Codex Task**:
```
Add type annotations to all functions in the following files:
1. backend/server/models/database.py
2. backend/server/models/deployment.py
3. backend/server/services/resource_monitor.py
Use Python 3.10+ style (X | None instead of Optional[X])
```

---

### Category 3: Production Magic Literals (633 findings)
**Priority**: MEDIUM
**Type**: CoM (Connascence of Meaning)

**Subcategory 3.1: Database/Model Files** (150+)
- `database.py` (84 findings)
- `deployment.py` (62 findings)
- `rewards.py` (35 findings)
- `usage.py` (18 findings)

**Subcategory 3.2: Service Files** (100+)
- `betanet.py` (58 findings)
- `resource_monitor.py` (45 findings)
- `memory_profiler.py` (36 findings)
- `scheduler.py` (30 findings)
- `metrics_aggregator.py` (17 findings)
- `enhanced_service_manager.py` (15 findings)

**Subcategory 3.3: Migration Files** (70+)
- `005_create_reward_tables.py` (25)
- `001_initial_schema.py` (16)
- `002_add_bitchat_advanced_features.py` (16)

---

### Category 4: Position Coupling (2 findings)
**Priority**: LOW
**Type**: CoP (Connascence of Position)
**Description**: Function parameters where order matters

**Action**: Refactor to use keyword-only arguments or dataclasses

---

### Category 5: Algorithm Duplication (1 finding)
**Priority**: LOW
**Type**: CoA (Connascence of Algorithm)
**Description**: Duplicated algorithmic logic

**Action**: Extract to shared utility function

---

### Category 6: Test File Magic Literals (755 findings)
**Priority**: LOW (but good hygiene)
**Type**: CoM

**Top Test Files**:
- `test_file_upload_security.py` (123)
- `seed_data.py` (98)
- `test_production_hardening.py` (98)
- `test_resource_optimization.py` (78)
- `test_fog_optimization.py` (67)

**Recommendation**: Create test constants file

---

## Codex Task Batches

### Batch 1: Critical Constants (Priority: Immediate)
```
Create a new constants module at backend/server/constants.py with the following:

1. File size constants:
   - ONE_KB = 1024
   - ONE_MB = 1048576
   - TWO_MB = 2097152
   - FIVE_MB = 5242880
   - TEN_MB = 10485760
   - ONE_GB = 1073741824

2. Time constants:
   - ONE_MINUTE = 60
   - ONE_HOUR = 3600
   - ONE_DAY = 86400
   - ONE_WEEK = 604800
   - THIRTY_DAYS = 2592000
   - ONE_YEAR = 31536000

Then update these files to use the constants:
- backend/server/middleware/security_headers.py (line 34)
- backend/server/models/database.py (line 587)
- backend/server/routes/bitchat.py (line 142)
- backend/server/services/file_transfer.py (line 69)
```

### Batch 2: Database Model Type Annotations
```
Add comprehensive type annotations to:
- backend/server/models/database.py
- backend/server/models/deployment.py
- backend/server/models/rewards.py

Use Python 3.10+ style annotations. All functions should have:
- Parameter type hints
- Return type hints
- Use X | None instead of Optional[X]
```

### Batch 3: Service Layer Magic Literals
```
Refactor magic literals in service files:
1. backend/server/services/betanet.py - extract to constants
2. backend/server/services/resource_monitor.py - extract to constants
3. backend/server/services/memory_profiler.py - extract to constants
4. backend/server/services/scheduler.py - extract to constants

Focus on:
- Timeout values
- Buffer sizes
- Threshold values
- Interval durations
```

### Batch 4: Test Constants
```
Create backend/tests/constants.py with test-specific constants.
Update the top 5 test files with most violations to use these constants.
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Total Violations | 1551 | < 500 |
| Production Violations | 697 | < 200 |
| Critical Violations | 23 | 0 |
| Type Annotation Coverage | ~60% | > 95% |

---

## Execution Order

1. **Batch 1** - Create constants module (unblocks all other batches)
2. **Batch 2** - Type annotations (independent, can parallel)
3. **Batch 3** - Service layer refactoring (depends on Batch 1)
4. **Batch 4** - Test constants (lowest priority)

---

**Generated by**: Connascence Analyzer + Claude
**Policy Used**: strict-core
