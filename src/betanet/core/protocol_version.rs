//! Protocol versioning for Betanet v1.2 compliance
//!
//! Implements version negotiation and protocol identification
//! as required by Betanet v1.2 specification.

use serde::{Deserialize, Serialize};
use std::fmt;

/// Betanet protocol version following semantic versioning (MAJOR.MINOR.PATCH).
///
/// Protocol versions determine compatibility between mixnodes in the Betanet network.
/// Nodes with incompatible versions cannot communicate.
///
/// # Compatibility Rules
///
/// - **Major version** must match exactly (breaking changes)
/// - **Minor version** is backward compatible (v1.2 can talk to v1.1, but not vice versa)
/// - **Patch version** is always compatible within the same major.minor
///
/// # Examples
///
/// ```
/// use betanet::core::protocol_version::ProtocolVersion;
///
/// let v1_2_0 = ProtocolVersion::V1_2_0;
/// let v1_1_0 = ProtocolVersion::V1_1_0;
///
/// // v1.2.0 is compatible with v1.1.0 (backward compatible)
/// assert!(v1_2_0.is_compatible_with(&v1_1_0));
///
/// // v1.1.0 is NOT compatible with v1.2.0 (can't talk to newer minor)
/// assert!(!v1_1_0.is_compatible_with(&v1_2_0));
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct ProtocolVersion {
    /// Major version number (breaking changes)
    pub major: u8,
    /// Minor version number (backward compatible features)
    pub minor: u8,
    /// Patch version number (bug fixes, no protocol changes)
    pub patch: u8,
}

impl ProtocolVersion {
    /// Betanet v1.2.0 (current target)
    pub const V1_2_0: Self = Self {
        major: 1,
        minor: 2,
        patch: 0,
    };

    /// Betanet v1.1.0 (previous version for backward compatibility testing)
    pub const V1_1_0: Self = Self {
        major: 1,
        minor: 1,
        patch: 0,
    };

    /// Create new protocol version
    pub const fn new(major: u8, minor: u8, patch: u8) -> Self {
        Self {
            major,
            minor,
            patch,
        }
    }

    /// Check if this version is compatible with another version.
    ///
    /// Compatibility is asymmetric: newer minor versions can communicate with older ones,
    /// but not vice versa. This ensures backward compatibility while allowing protocol evolution.
    ///
    /// # Arguments
    ///
    /// * `other` - The protocol version to check compatibility against
    ///
    /// # Returns
    ///
    /// `true` if this version can communicate with `other`, `false` otherwise
    ///
    /// # Examples
    ///
    /// ```
    /// use betanet::core::protocol_version::ProtocolVersion;
    ///
    /// let v1_2 = ProtocolVersion::new(1, 2, 0);
    /// let v1_1 = ProtocolVersion::new(1, 1, 0);
    /// let v2_0 = ProtocolVersion::new(2, 0, 0);
    ///
    /// assert!(v1_2.is_compatible_with(&v1_1)); // backward compatible
    /// assert!(!v1_1.is_compatible_with(&v1_2)); // can't talk to newer
    /// assert!(!v1_2.is_compatible_with(&v2_0)); // different major version
    /// ```
    pub fn is_compatible_with(&self, other: &Self) -> bool {
        // Major version must match
        if self.major != other.major {
            return false;
        }

        // Minor version compatibility: higher can talk to lower
        // (backward compatible within same major version)
        self.minor >= other.minor
    }

    /// Encode version as a single byte for efficient wire transmission.
    ///
    /// Format: `0x1M` where M is the minor version (for major version 1).
    /// Returns `0xFF` for unknown/unsupported versions.
    ///
    /// # Returns
    ///
    /// Single byte encoding of the protocol version
    ///
    /// # Examples
    ///
    /// ```
    /// use betanet::core::protocol_version::ProtocolVersion;
    ///
    /// let v1_2_0 = ProtocolVersion::new(1, 2, 0);
    /// assert_eq!(v1_2_0.encode_byte(), 0x12); // 0x10 | 0x02
    /// ```
    pub fn encode_byte(&self) -> u8 {
        if self.major == 1 {
            0x10 | (self.minor & 0x0F)
        } else {
            0xFF // Unknown version
        }
    }

    /// Decode protocol version from a single byte.
    ///
    /// # Arguments
    ///
    /// * `byte` - Encoded version byte (format: `0x1M` for v1.M.0)
    ///
    /// # Returns
    ///
    /// `Some(ProtocolVersion)` if the byte represents a valid version, `None` otherwise
    ///
    /// # Examples
    ///
    /// ```
    /// use betanet::core::protocol_version::ProtocolVersion;
    ///
    /// let version = ProtocolVersion::decode_byte(0x12);
    /// assert_eq!(version, Some(ProtocolVersion::new(1, 2, 0)));
    ///
    /// assert_eq!(ProtocolVersion::decode_byte(0xFF), None); // invalid
    /// ```
    pub fn decode_byte(byte: u8) -> Option<Self> {
        if byte & 0xF0 == 0x10 {
            let minor = byte & 0x0F;
            Some(Self::new(1, minor, 0))
        } else {
            None
        }
    }

    /// Convert to protocol ID string for multiaddr compatibility.
    ///
    /// Format: `/betanet/mix/{major}.{minor}.{patch}`
    ///
    /// # Returns
    ///
    /// Protocol ID string suitable for libp2p multiaddr
    ///
    /// # Examples
    ///
    /// ```
    /// use betanet::core::protocol_version::ProtocolVersion;
    ///
    /// let v1_2_0 = ProtocolVersion::V1_2_0;
    /// assert_eq!(v1_2_0.to_protocol_id(), "/betanet/mix/1.2.0");
    /// ```
    pub fn to_protocol_id(&self) -> String {
        format!("/betanet/mix/{}.{}.{}", self.major, self.minor, self.patch)
    }
}

impl fmt::Display for ProtocolVersion {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)
    }
}

impl Default for ProtocolVersion {
    fn default() -> Self {
        Self::V1_2_0
    }
}

/// Protocol capability for layer negotiation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProtocolCapability {
    /// Layer identifier (l1-l7)
    pub layer: String,
    /// Version for this layer
    pub version: ProtocolVersion,
}

impl ProtocolCapability {
    /// L4 Privacy Hop capability
    pub fn l4_privacy_hop() -> Self {
        Self {
            layer: "l4".to_string(),
            version: ProtocolVersion::V1_2_0,
        }
    }

    /// Create capability for specific layer
    pub fn new(layer: &str, version: ProtocolVersion) -> Self {
        Self {
            layer: layer.to_string(),
            version,
        }
    }
}

/// Feature flags for gradual protocol rollout
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FeatureFlags {
    /// Support for relay lottery (v1.2+)
    pub relay_lottery: bool,
    /// Support for VRF-based delays (v1.2+)
    pub vrf_delays: bool,
    /// Support for cover traffic (v1.2+)
    pub cover_traffic: bool,
    /// Support for batch processing (v1.1+)
    pub batch_processing: bool,
    /// Support for enhanced Sphinx packets (v1.2+)
    pub enhanced_sphinx: bool,
}

impl FeatureFlags {
    /// Create feature flags for v1.0.0
    pub fn v1_0_0() -> Self {
        Self {
            relay_lottery: false,
            vrf_delays: false,
            cover_traffic: false,
            batch_processing: false,
            enhanced_sphinx: false,
        }
    }

    /// Create feature flags for v1.1.0
    pub fn v1_1_0() -> Self {
        Self {
            relay_lottery: false,
            vrf_delays: false,
            cover_traffic: false,
            batch_processing: true,
            enhanced_sphinx: false,
        }
    }

    /// Create feature flags for v1.2.0 (current)
    pub fn v1_2_0() -> Self {
        Self {
            relay_lottery: true,
            vrf_delays: true,
            cover_traffic: true,
            batch_processing: true,
            enhanced_sphinx: true,
        }
    }

    /// Get feature flags for a specific version
    pub fn for_version(version: &ProtocolVersion) -> Self {
        match (version.major, version.minor) {
            (1, 0) => Self::v1_0_0(),
            (1, 1) => Self::v1_1_0(),
            (1, 2) => Self::v1_2_0(),
            _ => Self::v1_0_0(), // Default to most conservative
        }
    }

    /// Check if all features in other are supported by this
    pub fn supports(&self, other: &Self) -> bool {
        (!other.relay_lottery || self.relay_lottery)
            && (!other.vrf_delays || self.vrf_delays)
            && (!other.cover_traffic || self.cover_traffic)
            && (!other.batch_processing || self.batch_processing)
            && (!other.enhanced_sphinx || self.enhanced_sphinx)
    }

    /// Get intersection of two feature sets (common features)
    pub fn intersect(&self, other: &Self) -> Self {
        Self {
            relay_lottery: self.relay_lottery && other.relay_lottery,
            vrf_delays: self.vrf_delays && other.vrf_delays,
            cover_traffic: self.cover_traffic && other.cover_traffic,
            batch_processing: self.batch_processing && other.batch_processing,
            enhanced_sphinx: self.enhanced_sphinx && other.enhanced_sphinx,
        }
    }
}

impl Default for FeatureFlags {
    fn default() -> Self {
        Self::v1_2_0()
    }
}

/// Protocol capabilities advertisement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolAdvertisement {
    /// Protocol version
    pub version: ProtocolVersion,
    /// Supported features
    pub features: FeatureFlags,
    /// Supported layers
    pub capabilities: Vec<ProtocolCapability>,
    /// Node identifier
    pub node_id: String,
}

impl ProtocolAdvertisement {
    /// Create new protocol advertisement
    pub fn new(version: ProtocolVersion, node_id: String) -> Self {
        Self {
            features: FeatureFlags::for_version(&version),
            capabilities: vec![ProtocolCapability::l4_privacy_hop()],
            version,
            node_id,
        }
    }

    /// Check compatibility with another advertisement
    pub fn is_compatible_with(&self, other: &Self) -> bool {
        self.version.is_compatible_with(&other.version)
    }

    /// Encode to bytes for handshake
    pub fn encode(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(self).map_err(|e| format!("Failed to encode advertisement: {}", e))
    }

    /// Decode from bytes
    pub fn decode(bytes: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(bytes).map_err(|e| format!("Failed to decode advertisement: {}", e))
    }
}

/// Version negotiation result
#[derive(Debug, Clone)]
pub enum NegotiationResult {
    /// Versions are compatible
    Compatible(ProtocolVersion),
    /// Incompatible versions
    Incompatible {
        our_version: ProtocolVersion,
        their_version: ProtocolVersion,
    },
    /// Version not supported
    Unsupported(u8),
}

/// Negotiate protocol version with peer
pub fn negotiate_version(
    our_version: ProtocolVersion,
    their_version: ProtocolVersion,
) -> NegotiationResult {
    if our_version.is_compatible_with(&their_version) {
        // Use the lower version for compatibility
        let negotiated = if our_version < their_version {
            our_version
        } else {
            their_version
        };
        NegotiationResult::Compatible(negotiated)
    } else {
        NegotiationResult::Incompatible {
            our_version,
            their_version,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version_encoding() {
        let v1_2 = ProtocolVersion::V1_2_0;
        assert_eq!(v1_2.encode_byte(), 0x12);

        let decoded = ProtocolVersion::decode_byte(0x12);
        assert_eq!(decoded, Some(ProtocolVersion::new(1, 2, 0)));
    }

    #[test]
    fn test_version_compatibility() {
        let v1_2 = ProtocolVersion::V1_2_0;
        let v1_1 = ProtocolVersion::V1_1_0;

        // v1.2 can talk to v1.1 (backward compatible)
        assert!(v1_2.is_compatible_with(&v1_1));

        // v1.1 cannot talk to v1.2 (missing features)
        assert!(!v1_1.is_compatible_with(&v1_2));
    }

    #[test]
    fn test_protocol_id() {
        let v1_2 = ProtocolVersion::V1_2_0;
        assert_eq!(v1_2.to_protocol_id(), "/betanet/mix/1.2.0");
    }

    #[test]
    fn test_negotiation() {
        let v1_2 = ProtocolVersion::V1_2_0;
        let v1_1 = ProtocolVersion::V1_1_0;

        match negotiate_version(v1_2, v1_1) {
            NegotiationResult::Compatible(version) => {
                assert_eq!(version, v1_1); // Should use lower version
            }
            _ => panic!("Expected compatible versions"),
        }
    }
}
