# Phase 3: P2P De-Stub and Transport Hardening

## SIN IDs Closed
- **SIN-009**: Removed fake imports from `...infrastructure.p2p.*` (never existed). TRANSPORTS_AVAILABLE now truthful (False when stubs, True only with real modules).
- **SIN-010**: `_get_transport_capabilities()` uses local `TransportCapabilities` from `src/p2p/transports/base_transport.py` instead of broken import.
- **SIN-011**: `_initialize_transports()` uses real transport constructors (`BetaNetTransport`, `BitChatTransport`). Message handlers accept dict format. Direct transport `send()` used.
- **SIN-015**: `ServiceStatus.DEGRADED` added. Service manager surfaces degraded state when P2P transports unavailable. `get_health()` reports "degraded" status.

## Changes
- `src/p2p/unified_p2p_system.py` - Import rewire, transport init fix, handler dict format, degraded mode
- `backend/server/services/registry.py` - Added `DEGRADED` to ServiceStatus enum
- `backend/server/services/enhanced_service_manager.py` - P2P init checks TRANSPORTS_AVAILABLE, surfaces degraded state
- `tests/contracts/test_p2p_transports.py` - 14 tests covering all 4 SINs

## Key Fixes
- Replaced 7 `from ...infrastructure.p2p.*` imports with `from .transports.*` (local package)
- Eliminated all stub classes (HtxClient, BitChatTransport, BitChatMessage, TransportManager stubs)
- `_initialize_transports()` now constructs real `BetaNetTransport(node_id=, betanet_api_url=)` and `BitChatBLETransport(node_id=, bitchat_api_url=)`
- `_send_via_direct_transport()` calls `transport.send(dict)` matching `TransportInterface.send()` ABC
- `_handle_bitchat_message()` and `_handle_betanet_message()` accept plain dict (real transport format) instead of `unified_message.metadata.*` object
- Removed dead TransportManager initialization (no local implementation exists)
- Removed dead mobile bridge import from nonexistent path
