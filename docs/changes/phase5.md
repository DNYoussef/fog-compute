# Phase 5: VPN/Onion Honest Stubs

## SIN IDs Closed
- **SIN-019**: NymMixnetClient stub no longer fakes success. `start()` returns False, `send_anonymous_message()` returns None. Production mode raises `StubNotAllowedError`. Added `MIXNET_AVAILABLE = False` module flag.
- **SIN-020**: `fetch_consensus()` flags simulated nodes with `consensus_simulated = True`. Refuses to generate simulated nodes in production mode (`ALLOW_MOCKS=false`). Stats include `consensus_simulated` field.
- **SIN-021**: `_send_direct_gossip()` no longer returns True unconditionally. Attempts real delivery via `fog_coordinator.send_p2p_message()` when available, returns False otherwise.

## Changes
- `src/vpn/fog_onion_coordinator.py` - Stub guard, honest NymMixnetClient, real gossip delivery
- `src/vpn/onion_routing.py` - Production-guarded consensus, simulated flag in stats
- `tests/contracts/test_vpn_onion.py` - 17 tests (stub honesty, consensus, gossip, production mode)

## Key Fixes
- `NymMixnetClient.start()` returns `False` (was `True`)
- `NymMixnetClient.send_anonymous_message()` returns `None` (was fake packet ID)
- `_stubs_allowed()` guard function checks `ALLOW_MOCKS` and `APP_ENV`
- `StubNotAllowedError` raised when stubs invoked in production
- `fetch_consensus()` returns `False` in production (no real authorities)
- `OnionRouter.consensus_simulated` attribute tracks consensus source
- `_send_direct_gossip()` returns `False` when no transport (was `True`)
- Coordinator sets `mixnet_client = None` when stub fails to start
