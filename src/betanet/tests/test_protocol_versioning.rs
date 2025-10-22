//! Protocol Versioning Tests
//!
//! Comprehensive test suite for protocol version negotiation, backward compatibility,
//! and version translation.

#[cfg(test)]
mod tests {
    use crate::core::{
        compatibility::{Feature, PacketAdapter, PacketFormat, TranslationContext},
        protocol_version::{
            FeatureFlags, NegotiationResult, ProtocolAdvertisement, ProtocolVersion,
        },
        versions::{DeprecationTimeline, VersionRegistry},
    };

    // ============================================================================
    // VERSION NEGOTIATION TESTS
    // ============================================================================

    #[test]
    fn test_version_negotiation_compatible() {
        let v1_2 = ProtocolVersion::V1_2_0;
        let v1_1 = ProtocolVersion::V1_1_0;

        // v1.2 can talk to v1.1 (backward compatible)
        match crate::core::protocol_version::negotiate_version(v1_2, v1_1) {
            NegotiationResult::Compatible(negotiated) => {
                assert_eq!(negotiated, v1_1, "Should negotiate to lower version");
            }
            _ => panic!("Expected compatible negotiation"),
        }
    }

    #[test]
    fn test_version_negotiation_incompatible_major() {
        let v1_2 = ProtocolVersion::new(1, 2, 0);
        let v2_0 = ProtocolVersion::new(2, 0, 0);

        // Different major versions are incompatible
        match crate::core::protocol_version::negotiate_version(v1_2, v2_0) {
            NegotiationResult::Incompatible { .. } => {
                // Expected
            }
            _ => panic!("Expected incompatible negotiation"),
        }
    }

    #[test]
    fn test_version_negotiation_newer_to_older() {
        let v1_1 = ProtocolVersion::V1_1_0;
        let v1_2 = ProtocolVersion::V1_2_0;

        // v1.1 cannot talk to v1.2 (missing features)
        match crate::core::protocol_version::negotiate_version(v1_1, v1_2) {
            NegotiationResult::Incompatible { .. } => {
                // Expected - older version can't support newer features
            }
            _ => panic!("v1.1 should not be compatible with v1.2"),
        }
    }

    #[test]
    fn test_version_negotiation_same_version() {
        let v1_2 = ProtocolVersion::V1_2_0;

        match crate::core::protocol_version::negotiate_version(v1_2, v1_2) {
            NegotiationResult::Compatible(negotiated) => {
                assert_eq!(negotiated, v1_2);
            }
            _ => panic!("Same versions should be compatible"),
        }
    }

    // ============================================================================
    // BACKWARD COMPATIBILITY TESTS
    // ============================================================================

    #[test]
    fn test_backward_compatibility_v1_2_to_v1_1() {
        let v1_2 = ProtocolVersion::V1_2_0;
        let v1_1 = ProtocolVersion::V1_1_0;

        // v1.2 node can talk to v1.1 node
        assert!(
            v1_2.is_compatible_with(&v1_1),
            "v1.2 should be backward compatible with v1.1"
        );
    }

    #[test]
    fn test_backward_compatibility_v1_2_to_v1_0() {
        let v1_2 = ProtocolVersion::V1_2_0;
        let v1_0 = ProtocolVersion::new(1, 0, 0);

        // v1.2 node can talk to v1.0 node
        assert!(
            v1_2.is_compatible_with(&v1_0),
            "v1.2 should be backward compatible with v1.0"
        );
    }

    #[test]
    fn test_backward_compatibility_v1_1_to_v1_0() {
        let v1_1 = ProtocolVersion::V1_1_0;
        let v1_0 = ProtocolVersion::new(1, 0, 0);

        // v1.1 node can talk to v1.0 node
        assert!(
            v1_1.is_compatible_with(&v1_0),
            "v1.1 should be backward compatible with v1.0"
        );
    }

    #[test]
    fn test_no_forward_compatibility() {
        let v1_0 = ProtocolVersion::new(1, 0, 0);
        let v1_2 = ProtocolVersion::V1_2_0;

        // v1.0 node cannot talk to v1.2 node
        assert!(
            !v1_0.is_compatible_with(&v1_2),
            "v1.0 should not be forward compatible with v1.2"
        );
    }

    // ============================================================================
    // INCOMPATIBLE VERSION REJECTION TESTS
    // ============================================================================

    #[test]
    fn test_incompatible_rejection_major_version() {
        let v1_2 = ProtocolVersion::new(1, 2, 0);
        let v2_0 = ProtocolVersion::new(2, 0, 0);

        assert!(
            !v1_2.is_compatible_with(&v2_0),
            "Different major versions should be incompatible"
        );
        assert!(
            !v2_0.is_compatible_with(&v1_2),
            "Different major versions should be incompatible (reverse)"
        );
    }

    #[test]
    fn test_incompatible_rejection_advertisement() {
        let v1_2_ad = ProtocolAdvertisement::new(ProtocolVersion::V1_2_0, "node1".to_string());
        let v2_0_ad = ProtocolAdvertisement::new(ProtocolVersion::new(2, 0, 0), "node2".to_string());

        assert!(
            !v1_2_ad.is_compatible_with(&v2_0_ad),
            "Advertisements with different major versions should be incompatible"
        );
    }

    // ============================================================================
    // FEATURE FLAGS TESTS
    // ============================================================================

    #[test]
    fn test_feature_flags_v1_0() {
        let flags = FeatureFlags::v1_0_0();

        assert!(!flags.relay_lottery);
        assert!(!flags.vrf_delays);
        assert!(!flags.cover_traffic);
        assert!(!flags.batch_processing);
        assert!(!flags.enhanced_sphinx);
    }

    #[test]
    fn test_feature_flags_v1_1() {
        let flags = FeatureFlags::v1_1_0();

        assert!(!flags.relay_lottery);
        assert!(!flags.vrf_delays);
        assert!(!flags.cover_traffic);
        assert!(flags.batch_processing, "v1.1 should support batch processing");
        assert!(!flags.enhanced_sphinx);
    }

    #[test]
    fn test_feature_flags_v1_2() {
        let flags = FeatureFlags::v1_2_0();

        assert!(flags.relay_lottery, "v1.2 should support relay lottery");
        assert!(flags.vrf_delays, "v1.2 should support VRF delays");
        assert!(flags.cover_traffic, "v1.2 should support cover traffic");
        assert!(flags.batch_processing, "v1.2 should support batch processing");
        assert!(flags.enhanced_sphinx, "v1.2 should support enhanced sphinx");
    }

    #[test]
    fn test_feature_flags_intersection() {
        let v1_2_flags = FeatureFlags::v1_2_0();
        let v1_1_flags = FeatureFlags::v1_1_0();

        let common = v1_2_flags.intersect(&v1_1_flags);

        // Only batch processing is common
        assert!(!common.relay_lottery);
        assert!(!common.vrf_delays);
        assert!(!common.cover_traffic);
        assert!(common.batch_processing);
        assert!(!common.enhanced_sphinx);
    }

    #[test]
    fn test_feature_flags_supports() {
        let v1_2_flags = FeatureFlags::v1_2_0();
        let v1_1_flags = FeatureFlags::v1_1_0();
        let v1_0_flags = FeatureFlags::v1_0_0();

        // v1.2 supports all features in v1.1 and v1.0
        assert!(v1_2_flags.supports(&v1_1_flags));
        assert!(v1_2_flags.supports(&v1_0_flags));

        // v1.1 doesn't support v1.2 features
        assert!(!v1_1_flags.supports(&v1_2_flags));

        // v1.1 supports v1.0 features
        assert!(v1_1_flags.supports(&v1_0_flags));
    }

    // ============================================================================
    // PACKET TRANSLATION TESTS
    // ============================================================================

    #[test]
    fn test_packet_translation_v1_2_to_v1_1() {
        let adapter = PacketAdapter::new(PacketFormat::V1_2, PacketFormat::V1_1);
        assert!(adapter.is_ok(), "Should be able to create adapter");
    }

    #[test]
    fn test_packet_translation_v1_2_to_v1_0() {
        let adapter = PacketAdapter::new(PacketFormat::V1_2, PacketFormat::V1_0);
        assert!(adapter.is_ok(), "Should be able to downgrade v1.2 to v1.0");
    }

    #[test]
    fn test_packet_translation_no_upgrade() {
        let adapter = PacketAdapter::new(PacketFormat::V1_0, PacketFormat::V1_2);
        assert!(adapter.is_err(), "Should not be able to upgrade without data");
    }

    #[test]
    fn test_packet_format_for_version() {
        assert_eq!(
            PacketFormat::for_version(&ProtocolVersion::new(1, 0, 0)),
            PacketFormat::V1_0
        );
        assert_eq!(
            PacketFormat::for_version(&ProtocolVersion::V1_1_0),
            PacketFormat::V1_1
        );
        assert_eq!(
            PacketFormat::for_version(&ProtocolVersion::V1_2_0),
            PacketFormat::V1_2
        );
    }

    #[test]
    fn test_translation_context() {
        let ctx = TranslationContext::new(ProtocolVersion::V1_2_0, ProtocolVersion::V1_1_0);

        // Should have v1.1 capabilities only
        assert!(!ctx.has_feature(Feature::RelayLottery));
        assert!(!ctx.has_feature(Feature::VrfDelays));
        assert!(ctx.has_feature(Feature::BatchProcessing));
    }

    // ============================================================================
    // VERSION REGISTRY TESTS
    // ============================================================================

    #[test]
    fn test_version_registry_latest() {
        let registry = VersionRegistry::new();
        let latest = registry.latest();

        assert_eq!(latest.version, ProtocolVersion::V1_2_0);
    }

    #[test]
    fn test_version_registry_lookup() {
        let registry = VersionRegistry::new();

        let v1_2_meta = registry.get(&ProtocolVersion::V1_2_0);
        assert!(v1_2_meta.is_some());
        assert_eq!(v1_2_meta.unwrap().version, ProtocolVersion::V1_2_0);
    }

    #[test]
    fn test_version_registry_upgrade_path() {
        let registry = VersionRegistry::new();

        let path = registry.upgrade_path(
            &ProtocolVersion::new(1, 0, 0),
            &ProtocolVersion::V1_2_0,
        );

        assert!(path.is_some());
        let path = path.unwrap();
        assert_eq!(path.len(), 2); // v1.1 and v1.2
        assert_eq!(path[0].version, ProtocolVersion::V1_1_0);
        assert_eq!(path[1].version, ProtocolVersion::V1_2_0);
    }

    #[test]
    fn test_version_registry_no_cross_major_upgrade() {
        let registry = VersionRegistry::new();

        let path = registry.upgrade_path(
            &ProtocolVersion::new(1, 2, 0),
            &ProtocolVersion::new(2, 0, 0),
        );

        assert!(path.is_none(), "No upgrade path across major versions");
    }

    #[test]
    fn test_deprecation_timeline() {
        let timeline = DeprecationTimeline::v1_0_0();

        assert_eq!(timeline.version, ProtocolVersion::new(1, 0, 0));
        assert_eq!(timeline.upgrade_to, ProtocolVersion::V1_2_0);
    }

    // ============================================================================
    // PROTOCOL ADVERTISEMENT TESTS
    // ============================================================================

    #[test]
    fn test_protocol_advertisement_encoding() {
        let ad = ProtocolAdvertisement::new(ProtocolVersion::V1_2_0, "test-node".to_string());

        let encoded = ad.encode();
        assert!(encoded.is_ok());

        let decoded = ProtocolAdvertisement::decode(&encoded.unwrap());
        assert!(decoded.is_ok());

        let decoded_ad = decoded.unwrap();
        assert_eq!(decoded_ad.version, ProtocolVersion::V1_2_0);
        assert_eq!(decoded_ad.node_id, "test-node");
    }

    #[test]
    fn test_protocol_advertisement_compatibility() {
        let ad1 = ProtocolAdvertisement::new(ProtocolVersion::V1_2_0, "node1".to_string());
        let ad2 = ProtocolAdvertisement::new(ProtocolVersion::V1_1_0, "node2".to_string());

        assert!(ad1.is_compatible_with(&ad2), "v1.2 should be compatible with v1.1");
        assert!(!ad2.is_compatible_with(&ad1), "v1.1 should not be compatible with v1.2");
    }

    // ============================================================================
    // VERSION ENCODING/DECODING TESTS
    // ============================================================================

    #[test]
    fn test_version_encode_decode() {
        let v1_2 = ProtocolVersion::V1_2_0;
        let encoded = v1_2.encode_byte();

        assert_eq!(encoded, 0x12);

        let decoded = ProtocolVersion::decode_byte(encoded);
        assert!(decoded.is_some());
        assert_eq!(decoded.unwrap(), ProtocolVersion::new(1, 2, 0));
    }

    #[test]
    fn test_version_decode_invalid() {
        let decoded = ProtocolVersion::decode_byte(0xFF);
        assert!(decoded.is_none(), "Invalid byte should return None");
    }

    #[test]
    fn test_version_protocol_id() {
        let v1_2 = ProtocolVersion::V1_2_0;
        assert_eq!(v1_2.to_protocol_id(), "/betanet/mix/1.2.0");
    }

    // ============================================================================
    // INTEGRATION TESTS
    // ============================================================================

    #[test]
    fn test_full_negotiation_workflow() {
        // Simulate two nodes negotiating
        let node1_version = ProtocolVersion::V1_2_0;
        let node2_version = ProtocolVersion::V1_1_0;

        // Node 1 advertisement
        let node1_ad = ProtocolAdvertisement::new(node1_version, "node1".to_string());

        // Node 2 advertisement
        let node2_ad = ProtocolAdvertisement::new(node2_version, "node2".to_string());

        // Check compatibility
        assert!(node1_ad.is_compatible_with(&node2_ad));

        // Negotiate version
        match crate::core::protocol_version::negotiate_version(node1_version, node2_version) {
            NegotiationResult::Compatible(negotiated) => {
                assert_eq!(negotiated, node2_version, "Should negotiate to v1.1");

                // Check features available
                let ctx = TranslationContext::new(node1_version, negotiated);
                assert!(ctx.has_feature(Feature::BatchProcessing));
                assert!(!ctx.has_feature(Feature::RelayLottery));
            }
            _ => panic!("Negotiation should succeed"),
        }
    }
}
