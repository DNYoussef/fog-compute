# Phase 4: BitChat Crypto and Connectivity Correctness

## SIN IDs Closed
- **SIN-012**: Real authenticated encryption using tweetnacl (X25519-XSalsa20-Poly1305). Key generation, exchange, encrypt/decrypt all use real crypto. No more string-prefix fake "encryption".
- **SIN-013**: BLE discovery returns empty array when unavailable (not mock peers). Removed getMockPeers(), "Alice Mobile", "Bob Laptop" mock data. Added BLUETOOTH_AVAILABLE platform flag.
- **SIN-014**: WebRTC accepts configurable ICE/TURN servers. Shared RTCConfiguration used across all connections. Added signaling server WebSocket integration, ICE candidate forwarding, connection lifecycle events.

## Changes
- `src/bitchat/encryption/chacha20.ts` - Complete rewrite using tweetnacl
- `src/bitchat/protocol/bluetooth.ts` - Removed mock peers, real BLE scan
- `src/bitchat/protocol/webrtc.ts` - Configurable TURN, signaling server, shared config
- `src/bitchat/encryption/chacha20.test.ts` - 8 tests (keygen, exchange, encrypt/decrypt, wrong key)
- `src/bitchat/protocol/bluetooth.test.ts` - 6 tests (no mocks, platform detection)
- `src/bitchat/protocol/webrtc.test.ts` - 7 tests (TURN config, signaling, cleanup)

## Key Fixes
- `encryptMessage()` now uses `nacl.box.after()` with real X25519 shared key and random nonce
- `decryptMessage()` now uses `nacl.box.open.after()` with authentication verification
- `exportPublicKey()` returns real base64-encoded 32-byte X25519 public key
- `importPeerKey()` validates key length and stores for shared key computation
- `discoverPeers()` returns `[]` when BLE unavailable (not mock data)
- `createPeerConnection()` uses `this.getRTCConfiguration()` (shared TURN config)
- `hasTurnServers()` checks if any `turn:` or `turns:` URLs are configured
