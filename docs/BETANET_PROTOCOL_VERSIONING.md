# BetaNet Protocol Versioning

## Overview

BetaNet implements semantic versioning (MAJOR.MINOR.PATCH) for protocol evolution with backward compatibility and graceful degradation. This document describes the versioning policy, upgrade procedures, and migration guides.

## Table of Contents

1. [Versioning Policy](#versioning-policy)
2. [Protocol Versions](#protocol-versions)
3. [Version Negotiation](#version-negotiation)
4. [Backward Compatibility](#backward-compatibility)
5. [Feature Flags](#feature-flags)
6. [Upgrade Procedures](#upgrade-procedures)
7. [Migration Guides](#migration-guides)
8. [Breaking Changes](#breaking-changes)
9. [Deprecation Timeline](#deprecation-timeline)
10. [Compatibility Matrix](#compatibility-matrix)

---

## Versioning Policy

### Semantic Versioning

BetaNet follows semantic versioning (SemVer):

```
MAJOR.MINOR.PATCH

- MAJOR: Breaking changes, incompatible with previous major versions
- MINOR: Backward-compatible new features
- PATCH: Backward-compatible bug fixes
```

### Compatibility Rules

1. **Major Version**: Must match exactly
   - v1.x.x cannot communicate with v2.x.x
   - Breaking protocol changes require major version bump

2. **Minor Version**: Backward compatible
   - v1.2.x can communicate with v1.1.x
   - v1.1.x cannot use v1.2.x features
   - Newer minor versions support older ones

3. **Patch Version**: Always compatible
   - v1.2.1 is fully compatible with v1.2.0
   - Bug fixes only, no protocol changes

---

## Protocol Versions

### v1.0.0 (Baseline)

**Release Date**: 2024-01-01
**Status**: Deprecated (EOL: 2025-06-01)

**Features**:
- Basic Sphinx packet routing
- Simple mixnet topology
- Basic delay mechanisms

**Limitations**:
- No batch processing
- No VRF-based delays
- No relay lottery
- Limited privacy guarantees

---

### v1.1.0 (Batch Processing)

**Release Date**: 2024-06-01
**Status**: Supported

**Features**:
- Batch packet processing for higher throughput
- Improved pipeline architecture
- Enhanced metrics and monitoring
- Backward compatible with v1.0.0

**New Capabilities**:
- Process up to 100 packets per batch
- 2-3x throughput improvement
- Better resource utilization

**Migration from v1.0.0**:
```bash
# 1. Update node software
./update-node.sh v1.1.0

# 2. Enable batch processing
echo "batch_processing=true" >> config.toml

# 3. Restart node
systemctl restart betanet-node
```

---

### v1.2.0 (L4 Privacy Hop) - CURRENT

**Release Date**: 2025-01-01
**Status**: Stable (Current)

**Features**:
- L4 Privacy Hop with relay lottery
- VRF-based delay mechanisms
- Cover traffic generation
- Enhanced Sphinx packet format
- Backward compatible with v1.1.0 and v1.0.0

**New Capabilities**:
- Relay lottery for L4 privacy
- VRF-based verifiable delays
- Automatic cover traffic
- Enhanced packet format with VRF proofs

**Migration from v1.1.0**:
```bash
# 1. Update node software
./update-node.sh v1.2.0

# 2. Enable v1.2 features
cat >> config.toml <<EOF
relay_lottery=true
vrf_delays=true
cover_traffic=true
enhanced_sphinx=true
EOF

# 3. Restart node
systemctl restart betanet-node

# 4. Verify VRF functionality
betanet-cli verify-vrf
```

---

## Version Negotiation

### Handshake Protocol

When two nodes connect, they exchange protocol advertisements and negotiate a common version:

```
┌──────────┐                           ┌──────────┐
│  Node A  │                           │  Node B  │
│ (v1.2.0) │                           │ (v1.1.0) │
└──────────┘                           └──────────┘
      │                                      │
      │  1. Send Advertisement (v1.2.0)     │
      │─────────────────────────────────────>│
      │                                      │
      │     2. Send Advertisement (v1.1.0)  │
      │<─────────────────────────────────────│
      │                                      │
      │  3. Check Compatibility              │
      │     ✓ Compatible (same major)       │
      │                                      │
      │  4. Send Negotiated Version (v1.1)  │
      │─────────────────────────────────────>│
      │                                      │
      │  5. Send Confirmation (v1.1)        │
      │<─────────────────────────────────────│
      │                                      │
      │  6. Communication using v1.1        │
      │<────────────────────────────────────>│
```

### Negotiation Steps

1. **Advertisement Exchange**: Each node sends its version and capabilities
2. **Compatibility Check**: Verify major versions match
3. **Version Selection**: Negotiate to lower version for compatibility
4. **Confirmation**: Both nodes confirm negotiated version
5. **Communication**: Use negotiated version features

### Example Code

```rust
use betanet::core::{ProtocolVersion, ProtocolAdvertisement};

// Create advertisement
let our_version = ProtocolVersion::V1_2_0;
let our_ad = ProtocolAdvertisement::new(our_version, "node-123".to_string());

// Check compatibility with peer
let their_ad = receive_advertisement().await?;
if our_ad.is_compatible_with(&their_ad) {
    // Negotiate version
    let negotiated = negotiate_version(our_version, their_ad.version)?;
    println!("Negotiated version: {}", negotiated);
}
```

---

## Backward Compatibility

### Compatibility Matrix

| Your Version | Peer v1.0.0 | Peer v1.1.0 | Peer v1.2.0 | Peer v2.0.0 |
|--------------|-------------|-------------|-------------|-------------|
| **v1.0.0**   | ✓           | ✗           | ✗           | ✗           |
| **v1.1.0**   | ✓           | ✓           | ✗           | ✗           |
| **v1.2.0**   | ✓           | ✓           | ✓           | ✗           |
| **v2.0.0**   | ✗           | ✗           | ✗           | ✓           |

Legend:
- ✓ = Compatible (can communicate)
- ✗ = Incompatible (cannot communicate)

### Graceful Degradation

When communicating with older versions, newer nodes gracefully degrade:

**v1.2 Node ↔ v1.1 Node**:
- ✓ Batch processing (v1.1 feature)
- ✗ Relay lottery (v1.2 feature disabled)
- ✗ VRF delays (v1.2 feature disabled)
- ✗ Cover traffic (v1.2 feature disabled)

**v1.2 Node ↔ v1.0 Node**:
- ✗ Batch processing (disabled)
- ✗ All v1.2 features (disabled)
- Uses basic v1.0 packet format

### Packet Format Translation

BetaNet automatically translates packet formats between versions:

```rust
use betanet::core::compatibility::{PacketAdapter, PacketFormat};

// Create adapter for v1.2 -> v1.1 translation
let adapter = PacketAdapter::new(
    PacketFormat::V1_2,
    PacketFormat::V1_1
)?;

// Convert packet
let v1_2_packet = create_v1_2_packet();
let v1_1_packet = adapter.convert(&v1_2_packet)?;
```

**Packet Format Differences**:

| Format | Structure |
|--------|-----------|
| **v1.0** | `[length:4][payload]` |
| **v1.1** | `[length:4][batch_info:2][payload]` |
| **v1.2** | `[length:4][batch_info:2][payload][vrf_proof:32][lottery:8]` |

---

## Feature Flags

### Available Features

```rust
pub struct FeatureFlags {
    pub relay_lottery: bool,      // v1.2+
    pub vrf_delays: bool,          // v1.2+
    pub cover_traffic: bool,       // v1.2+
    pub batch_processing: bool,    // v1.1+
    pub enhanced_sphinx: bool,     // v1.2+
}
```

### Feature Availability by Version

| Feature | v1.0.0 | v1.1.0 | v1.2.0 |
|---------|--------|--------|--------|
| Relay Lottery | ✗ | ✗ | ✓ |
| VRF Delays | ✗ | ✗ | ✓ |
| Cover Traffic | ✗ | ✗ | ✓ |
| Batch Processing | ✗ | ✓ | ✓ |
| Enhanced Sphinx | ✗ | ✗ | ✓ |

### Checking Feature Availability

```rust
use betanet::core::compatibility::{TranslationContext, Feature};

// Create context for v1.2 -> v1.1 communication
let ctx = TranslationContext::new(
    ProtocolVersion::V1_2_0,
    ProtocolVersion::V1_1_0
);

// Check available features
if ctx.has_feature(Feature::BatchProcessing) {
    // Use batch processing
}

if !ctx.has_feature(Feature::RelayLottery) {
    // Relay lottery not available, use fallback
}
```

---

## Upgrade Procedures

### Pre-Upgrade Checklist

- [ ] Backup node configuration
- [ ] Review release notes for breaking changes
- [ ] Check compatibility with network peers
- [ ] Plan maintenance window (if needed)
- [ ] Test upgrade in staging environment

### Upgrade Paths

#### v1.0.0 → v1.2.0

**Option 1: Direct Upgrade**
```bash
# Stop node
systemctl stop betanet-node

# Backup
cp -r /etc/betanet /etc/betanet.backup

# Update software
./update-node.sh v1.2.0

# Update config
cat >> /etc/betanet/config.toml <<EOF
# v1.1 features
batch_processing=true

# v1.2 features
relay_lottery=true
vrf_delays=true
cover_traffic=true
enhanced_sphinx=true
EOF

# Start node
systemctl start betanet-node

# Verify
betanet-cli status
betanet-cli verify-version
```

**Option 2: Staged Upgrade** (Recommended)
```bash
# Stage 1: Upgrade to v1.1.0
./update-node.sh v1.1.0
# Verify stability for 24-48 hours

# Stage 2: Upgrade to v1.2.0
./update-node.sh v1.2.0
# Verify all features working
```

#### v1.1.0 → v1.2.0

```bash
# Stop node
systemctl stop betanet-node

# Update software
./update-node.sh v1.2.0

# Enable v1.2 features
cat >> /etc/betanet/config.toml <<EOF
relay_lottery=true
vrf_delays=true
cover_traffic=true
enhanced_sphinx=true
EOF

# Start node
systemctl start betanet-node

# Verify VRF
betanet-cli verify-vrf
```

### Post-Upgrade Verification

```bash
# Check version
betanet-cli version
# Expected: v1.2.0

# Verify connectivity
betanet-cli peers
# Should show connections to v1.1 and v1.2 peers

# Check feature status
betanet-cli features
# Should show all v1.2 features enabled

# Monitor logs
journalctl -u betanet-node -f
# Look for "Protocol version negotiated" messages
```

---

## Migration Guides

### v1.0.0 → v1.1.0 Migration

**Changes**:
- New batch processing feature
- Updated packet format with batch headers

**Configuration Changes**:
```toml
# Add to config.toml
batch_processing = true
batch_size = 100  # Process up to 100 packets per batch
```

**Code Changes** (if running custom mixnode):
```rust
// Old (v1.0):
pipeline.process_packet(packet).await?;

// New (v1.1):
pipeline.submit_packet(packet).await?;  // Batch processing
```

**Testing**:
```bash
# Send test packets
betanet-cli send-test --count 1000

# Verify batch processing
betanet-cli metrics | grep batch_processed
```

---

### v1.1.0 → v1.2.0 Migration

**Changes**:
- Relay lottery for L4 privacy
- VRF-based delay mechanisms
- Cover traffic generation
- Enhanced Sphinx packet format

**Configuration Changes**:
```toml
# Add to config.toml
relay_lottery = true
relay_lottery_threshold = 0.5  # 50% selection probability

vrf_delays = true
vrf_delay_min_ms = 10
vrf_delay_max_ms = 100

cover_traffic = true
cover_traffic_rate = 10  # packets per second

enhanced_sphinx = true
```

**Code Changes** (if running custom mixnode):
```rust
// Import new modules
use betanet::vrf::{VrfDelay, PoissonDelay};
use betanet::core::RelayLottery;

// Initialize relay lottery
let lottery = RelayLottery::new(0.5)?;

// Check if selected
if lottery.is_selected(&packet)? {
    // Apply VRF delay
    let delay = PoissonDelay::new(10, 100);
    delay.apply(&packet).await?;
}
```

**Testing**:
```bash
# Verify VRF
betanet-cli verify-vrf
# Expected: VRF verification successful

# Check relay lottery
betanet-cli lottery-stats
# Expected: ~50% selection rate

# Monitor cover traffic
betanet-cli metrics | grep cover_traffic
# Expected: ~10 packets/sec
```

---

## Breaking Changes

### v1.0.0 → v1.1.0

**No Breaking Changes** - Fully backward compatible

Additions:
- Batch processing feature (optional)
- New metrics API

---

### v1.1.0 → v1.2.0

**No Breaking Changes** - Fully backward compatible

Additions:
- Relay lottery (optional)
- VRF delays (optional)
- Cover traffic (optional)
- Enhanced packet format (backward compatible)

---

### v1.x.x → v2.0.0 (Future)

**Breaking Changes** (Planned):
- New cryptographic primitives
- Updated Sphinx packet format
- New routing algorithm
- Consensus protocol changes

**Migration Required**:
- Cannot run v1.x and v2.x nodes simultaneously
- Network-wide coordinated upgrade
- Migration timeline: 6-12 months notice

---

## Deprecation Timeline

### v1.0.0 Deprecation

**Announcement**: 2024-12-01
**End of Life**: 2025-06-01
**Reason**: Lacks critical L4 privacy features and VRF-based security

**Timeline**:
- **2024-12-01**: Deprecation announced
- **2025-03-01**: Warning messages added to v1.0 nodes
- **2025-04-01**: v1.0 nodes no longer eligible for rewards
- **2025-06-01**: v1.0 support removed, nodes must upgrade

**Recommended Action**: Upgrade to v1.2.0 by 2025-05-01

**Upgrade Support**:
```bash
# Check if your node is affected
betanet-cli version-check

# Get upgrade guide
betanet-cli upgrade-guide

# Automated upgrade (with confirmation)
betanet-cli auto-upgrade --to v1.2.0
```

---

## Compatibility Matrix

### Node Version Compatibility

| Feature | v1.0.0 | v1.1.0 | v1.2.0 |
|---------|--------|--------|--------|
| **Basic Routing** | ✓ | ✓ | ✓ |
| **Batch Processing** | ✗ | ✓ | ✓ |
| **Relay Lottery** | ✗ | ✗ | ✓ |
| **VRF Delays** | ✗ | ✗ | ✓ |
| **Cover Traffic** | ✗ | ✗ | ✓ |
| **Enhanced Sphinx** | ✗ | ✗ | ✓ |

### API Compatibility

| API Endpoint | v1.0.0 | v1.1.0 | v1.2.0 |
|--------------|--------|--------|--------|
| `/status` | ✓ | ✓ | ✓ |
| `/mixnodes` | ✓ | ✓ | ✓ |
| `/metrics` | ✓ | ✓ | ✓ |
| `/batch-stats` | ✗ | ✓ | ✓ |
| `/vrf-status` | ✗ | ✗ | ✓ |
| `/lottery-stats` | ✗ | ✗ | ✓ |

### Configuration Compatibility

All configuration options are backward compatible. New options have sensible defaults:

```toml
# v1.0 config works with v1.1 and v1.2
listen_addr = "0.0.0.0:9000"
buffer_size = 8192

# v1.1 additions (optional in v1.2)
batch_processing = true
batch_size = 100

# v1.2 additions (optional)
relay_lottery = true
vrf_delays = true
cover_traffic = true
```

---

## Best Practices

### Version Management

1. **Always use latest stable version** in production
2. **Test upgrades** in staging environment first
3. **Monitor peer versions** to understand network composition
4. **Plan upgrades** during low-traffic periods
5. **Keep backups** of configuration before upgrades

### Compatibility Testing

```bash
# Test compatibility with different versions
betanet-test --peer-version v1.0.0
betanet-test --peer-version v1.1.0
betanet-test --peer-version v1.2.0

# Verify feature negotiation
betanet-test --verify-features
```

### Monitoring

```bash
# Monitor version distribution
betanet-cli network-versions

# Check negotiated versions
journalctl -u betanet-node | grep "negotiated"

# Track feature usage
betanet-cli feature-stats
```

---

## Support

For questions or issues:
- **Documentation**: https://betanet.docs.io
- **Issues**: https://github.com/betanet/issues
- **Discord**: https://discord.gg/betanet
- **Email**: support@betanet.io

## Version History

| Version | Release Date | Status | EOL Date |
|---------|--------------|--------|----------|
| v1.0.0 | 2024-01-01 | Deprecated | 2025-06-01 |
| v1.1.0 | 2024-06-01 | Supported | TBD |
| v1.2.0 | 2025-01-01 | Current | - |
