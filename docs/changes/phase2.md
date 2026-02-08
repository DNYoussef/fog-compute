# Phase 2: Idle Compute Contract Repair

## SIN IDs Closed
- **SIN-016**: register_device properly awaits async EdgeManager.register_device with correct kwargs
- **SIN-017**: heartbeat and unregister fail explicitly (501/404) instead of silent no-ops
- **SIN-018**: Typed DTOs and _device_to_response helper replace dynamic getattr chains

## Changes
- `backend/server/routes/idle_compute.py` - Complete rewrite with typed DTOs
- `tests/contracts/test_idle_compute.py` - 6 tests covering all 3 SINs

## Key Fixes
- DeviceRegisterRequest now includes device_name field matching EdgeManager signature
- HeartbeatRequest uses Pydantic Field(ge=0, le=100) for battery validation
- _get_edge_service() helper centralizes 503 handling
- _device_to_response() provides typed conversion from EdgeDevice to canonical schema
