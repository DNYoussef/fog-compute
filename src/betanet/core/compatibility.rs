//! Protocol Compatibility Layer
//!
//! Provides version translation, packet format adapters, and graceful degradation
//! to maintain backward compatibility across protocol versions.

use serde::{Deserialize, Serialize};

use super::protocol_version::{FeatureFlags, ProtocolVersion};

/// Packet format version
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PacketFormat {
    /// v1.0 format - basic Sphinx packets
    V1_0,
    /// v1.1 format - adds batch processing headers
    V1_1,
    /// v1.2 format - adds VRF and relay lottery fields
    V1_2,
}

impl PacketFormat {
    /// Get packet format for protocol version
    pub fn for_version(version: &ProtocolVersion) -> Self {
        match (version.major, version.minor) {
            (1, 0) => Self::V1_0,
            (1, 1) => Self::V1_1,
            (1, 2) => Self::V1_2,
            _ => Self::V1_0, // Default to oldest format
        }
    }

    /// Check if this format can be converted to target format
    pub fn can_convert_to(&self, target: &Self) -> bool {
        use PacketFormat::*;
        match (self, target) {
            // Same format is always compatible
            (a, b) if a == b => true,
            // Can downgrade from newer to older (lossy)
            (V1_2, V1_1) | (V1_2, V1_0) | (V1_1, V1_0) => true,
            // Cannot upgrade without additional data
            _ => false,
        }
    }
}

/// Packet adapter for format conversion
#[derive(Debug)]
pub struct PacketAdapter {
    source_format: PacketFormat,
    target_format: PacketFormat,
}

impl PacketAdapter {
    /// Create new packet adapter
    pub fn new(source: PacketFormat, target: PacketFormat) -> Result<Self, String> {
        if !source.can_convert_to(&target) {
            return Err(format!(
                "Cannot convert from {:?} to {:?}",
                source, target
            ));
        }
        Ok(Self {
            source_format: source,
            target_format: target,
        })
    }

    /// Convert packet data from source to target format
    pub fn convert(&self, packet_data: &[u8]) -> Result<Vec<u8>, String> {
        use PacketFormat::*;

        match (&self.source_format, &self.target_format) {
            // No conversion needed
            (a, b) if a == b => Ok(packet_data.to_vec()),

            // V1.2 -> V1.1: Strip VRF and relay lottery fields
            (V1_2, V1_1) => self.strip_v1_2_to_v1_1(packet_data),

            // V1.2 -> V1.0: Strip all v1.1 and v1.2 extensions
            (V1_2, V1_0) => self.strip_v1_2_to_v1_0(packet_data),

            // V1.1 -> V1.0: Strip batch processing headers
            (V1_1, V1_0) => self.strip_v1_1_to_v1_0(packet_data),

            _ => Err(format!(
                "Unsupported conversion: {:?} -> {:?}",
                self.source_format, self.target_format
            )),
        }
    }

    /// Strip v1.2 fields to get v1.1 packet
    fn strip_v1_2_to_v1_1(&self, packet_data: &[u8]) -> Result<Vec<u8>, String> {
        // V1.2 packet structure:
        // [4 bytes: packet length] [payload] [32 bytes: VRF proof] [8 bytes: relay lottery]

        if packet_data.len() < 44 {
            return Err("Packet too small for v1.2 format".to_string());
        }

        // Strip last 40 bytes (VRF proof + relay lottery data)
        let v1_1_packet = &packet_data[..packet_data.len() - 40];
        Ok(v1_1_packet.to_vec())
    }

    /// Strip v1.2 fields to get v1.0 packet
    fn strip_v1_2_to_v1_0(&self, packet_data: &[u8]) -> Result<Vec<u8>, String> {
        // First strip to v1.1
        let v1_1_packet = self.strip_v1_2_to_v1_1(packet_data)?;
        // Then strip v1.1 extensions
        self.strip_v1_1_to_v1_0(&v1_1_packet)
    }

    /// Strip v1.1 batch headers to get v1.0 packet
    fn strip_v1_1_to_v1_0(&self, packet_data: &[u8]) -> Result<Vec<u8>, String> {
        // V1.1 packet structure:
        // [4 bytes: packet length] [2 bytes: batch info] [payload]

        if packet_data.len() < 6 {
            return Err("Packet too small for v1.1 format".to_string());
        }

        // Extract length
        let _length = u32::from_be_bytes([
            packet_data[0],
            packet_data[1],
            packet_data[2],
            packet_data[3],
        ]);

        // Skip batch info (2 bytes after length)
        let v1_0_packet = [
            &packet_data[0..4],  // Keep length
            &packet_data[6..],   // Skip batch info
        ].concat();

        // Update length to reflect stripped data
        let new_length = (v1_0_packet.len() - 4) as u32;
        let mut result = new_length.to_be_bytes().to_vec();
        result.extend_from_slice(&v1_0_packet[4..]);

        Ok(result)
    }
}

/// Version translation context
#[derive(Debug, Clone)]
pub struct TranslationContext {
    /// Source protocol version
    pub source_version: ProtocolVersion,
    /// Target protocol version
    pub target_version: ProtocolVersion,
    /// Features available after translation
    pub negotiated_features: FeatureFlags,
}

impl TranslationContext {
    /// Create new translation context
    pub fn new(source: ProtocolVersion, target: ProtocolVersion) -> Self {
        let source_features = FeatureFlags::for_version(&source);
        let target_features = FeatureFlags::for_version(&target);
        let negotiated_features = source_features.intersect(&target_features);

        Self {
            source_version: source,
            target_version: target,
            negotiated_features,
        }
    }

    /// Check if feature is available in negotiated context
    pub fn has_feature(&self, feature: Feature) -> bool {
        match feature {
            Feature::RelayLottery => self.negotiated_features.relay_lottery,
            Feature::VrfDelays => self.negotiated_features.vrf_delays,
            Feature::CoverTraffic => self.negotiated_features.cover_traffic,
            Feature::BatchProcessing => self.negotiated_features.batch_processing,
            Feature::EnhancedSphinx => self.negotiated_features.enhanced_sphinx,
        }
    }

    /// Get packet adapter for this context
    pub fn get_adapter(&self) -> Result<PacketAdapter, String> {
        let source_format = PacketFormat::for_version(&self.source_version);
        let target_format = PacketFormat::for_version(&self.target_version);
        PacketAdapter::new(source_format, target_format)
    }
}

/// Protocol features
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Feature {
    /// Relay lottery for L4 privacy
    RelayLottery,
    /// VRF-based delays
    VrfDelays,
    /// Cover traffic generation
    CoverTraffic,
    /// Batch packet processing
    BatchProcessing,
    /// Enhanced Sphinx packet format
    EnhancedSphinx,
}

/// Migration helper for protocol upgrades
#[derive(Debug)]
pub struct MigrationHelper {
    from_version: ProtocolVersion,
    to_version: ProtocolVersion,
}

impl MigrationHelper {
    /// Create new migration helper
    pub fn new(from: ProtocolVersion, to: ProtocolVersion) -> Self {
        Self {
            from_version: from,
            to_version: to,
        }
    }

    /// Check if migration is needed
    pub fn needs_migration(&self) -> bool {
        self.from_version != self.to_version
    }

    /// Check if migration is supported
    pub fn is_supported(&self) -> bool {
        // Only support migrations within same major version
        self.from_version.major == self.to_version.major
    }

    /// Get migration steps
    pub fn get_steps(&self) -> Vec<String> {
        let mut steps = Vec::new();

        if !self.needs_migration() {
            return steps;
        }

        // Example migration steps from v1.0 to v1.2
        if self.from_version == ProtocolVersion::new(1, 0, 0)
            && self.to_version == ProtocolVersion::new(1, 2, 0)
        {
            steps.push("1. Enable batch processing (v1.1 feature)".to_string());
            steps.push("2. Upgrade packet format to include batch headers".to_string());
            steps.push("3. Enable relay lottery (v1.2 feature)".to_string());
            steps.push("4. Enable VRF delays (v1.2 feature)".to_string());
            steps.push("5. Upgrade packet format to include VRF fields".to_string());
            steps.push("6. Enable cover traffic generation".to_string());
        } else if self.from_version == ProtocolVersion::new(1, 1, 0)
            && self.to_version == ProtocolVersion::new(1, 2, 0)
        {
            steps.push("1. Enable relay lottery (v1.2 feature)".to_string());
            steps.push("2. Enable VRF delays (v1.2 feature)".to_string());
            steps.push("3. Upgrade packet format to include VRF fields".to_string());
            steps.push("4. Enable cover traffic generation".to_string());
        }

        steps
    }

    /// Get deprecation warnings
    pub fn get_deprecation_warnings(&self) -> Vec<String> {
        let mut warnings = Vec::new();

        if self.from_version.minor < 2 && self.to_version.minor >= 2 {
            warnings.push(
                "Warning: Simple delay mechanisms deprecated in v1.2, use VRF delays instead"
                    .to_string(),
            );
        }

        warnings
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_packet_format_conversion() {
        assert!(PacketFormat::V1_2.can_convert_to(&PacketFormat::V1_1));
        assert!(PacketFormat::V1_2.can_convert_to(&PacketFormat::V1_0));
        assert!(PacketFormat::V1_1.can_convert_to(&PacketFormat::V1_0));
        assert!(!PacketFormat::V1_0.can_convert_to(&PacketFormat::V1_1));
    }

    #[test]
    fn test_translation_context() {
        let ctx = TranslationContext::new(
            ProtocolVersion::V1_2_0,
            ProtocolVersion::V1_1_0,
        );

        // v1.1 doesn't have relay lottery
        assert!(!ctx.has_feature(Feature::RelayLottery));
        // v1.1 has batch processing
        assert!(ctx.has_feature(Feature::BatchProcessing));
    }

    #[test]
    fn test_migration_helper() {
        let helper = MigrationHelper::new(
            ProtocolVersion::new(1, 0, 0),
            ProtocolVersion::new(1, 2, 0),
        );

        assert!(helper.needs_migration());
        assert!(helper.is_supported());
        assert!(!helper.get_steps().is_empty());
    }

    #[test]
    fn test_packet_adapter_v1_1_to_v1_0() {
        let adapter = PacketAdapter::new(PacketFormat::V1_1, PacketFormat::V1_0).unwrap();

        // Create mock v1.1 packet: [length:4][batch_info:2][payload]
        let v1_1_packet = vec![
            0, 0, 0, 10,  // length = 10
            0, 5,          // batch info
            1, 2, 3, 4, 5, 6, 7, 8  // payload (8 bytes)
        ];

        let v1_0_packet = adapter.convert(&v1_1_packet).unwrap();

        // v1.0 should have length=8 and payload only
        assert_eq!(v1_0_packet.len(), 12); // 4 bytes length + 8 bytes payload
        assert_eq!(&v1_0_packet[4..], &[1, 2, 3, 4, 5, 6, 7, 8]);
    }
}
