//! Comprehensive functionality tests for L4 enhancements
//! Tests protocol versioning, relay lottery, and Poisson delays

use betanet::core::protocol_version::{negotiate_version, NegotiationResult, ProtocolVersion};
use betanet::core::relay_lottery::{RelayLottery, WeightedRelay};
use betanet::vrf::poisson_delay::{calculate_vrf_poisson_delay, PoissonDelayGenerator};
use std::collections::HashMap;
use std::time::Duration;

#[test]
fn test_protocol_version_real_world_scenario() {
    // Scenario: Node v1.2.0 connects to mixed network
    let our_version = ProtocolVersion::V1_2_0;

    // Test 1: Connect to older v1.1.0 node (should negotiate to v1.1.0)
    let peer_v1_1 = ProtocolVersion::V1_1_0;
    match negotiate_version(our_version, peer_v1_1) {
        NegotiationResult::Compatible(negotiated) => {
            assert_eq!(negotiated, peer_v1_1, "Should negotiate down to v1.1.0");
            println!("✓ Successfully negotiated v1.2.0 -> v1.1.0");
        }
        _ => panic!("Expected compatible negotiation with v1.1.0"),
    }

    // Test 2: Connect to same version node
    let peer_v1_2 = ProtocolVersion::V1_2_0;
    match negotiate_version(our_version, peer_v1_2) {
        NegotiationResult::Compatible(negotiated) => {
            assert_eq!(negotiated, peer_v1_2, "Should use v1.2.0");
            println!("✓ Successfully negotiated v1.2.0 -> v1.2.0");
        }
        _ => panic!("Expected compatible negotiation with v1.2.0"),
    }

    // Test 3: Protocol ID format
    let protocol_id = our_version.to_protocol_id();
    assert_eq!(
        protocol_id, "/betanet/mix/1.2.0",
        "Protocol ID format incorrect"
    );
    println!("✓ Protocol ID format correct: {}", protocol_id);

    // Test 4: Byte encoding roundtrip
    let encoded = our_version.encode_byte();
    assert_eq!(encoded, 0x12, "Version encoding incorrect");
    let decoded = ProtocolVersion::decode_byte(encoded);
    assert_eq!(decoded, Some(our_version), "Version decoding failed");
    println!("✓ Byte encoding roundtrip successful: 0x{:02x}", encoded);
}

#[test]
fn test_relay_lottery_realistic_network() {
    // Scenario: Network with 10 relays of varying quality
    let mut lottery = RelayLottery::new();

    // Add high-quality relays (reputation 0.8-0.95)
    for i in 0..3 {
        lottery.add_relay(WeightedRelay::new(
            format!("192.168.1.{}:8080", 100 + i).parse().unwrap(),
            0.9 + (i as f64 * 0.016), // 0.9, 0.916, 0.932
            0.85,
            10000,
        ));
    }

    // Add medium-quality relays (reputation 0.5-0.7)
    for i in 0..4 {
        lottery.add_relay(WeightedRelay::new(
            format!("192.168.1.{}:8080", 110 + i).parse().unwrap(),
            0.5 + (i as f64 * 0.05), // 0.5, 0.55, 0.6, 0.65
            0.7,
            5000,
        ));
    }

    // Add low-quality relays (reputation 0.2-0.4)
    for i in 0..3 {
        lottery.add_relay(WeightedRelay::new(
            format!("192.168.1.{}:8080", 120 + i).parse().unwrap(),
            0.2 + (i as f64 * 0.1), // 0.2, 0.3, 0.4
            0.5,
            1000,
        ));
    }

    assert_eq!(lottery.relay_count(), 10, "Should have 10 relays");
    println!("✓ Created network with 10 relays (3 high, 4 medium, 3 low quality)");

    // Test 5: Single selection should favor high-quality relays
    let mut selections = HashMap::new();
    for _ in 0..1000 {
        let relay = lottery.select_relay().unwrap();
        *selections.entry(relay.address.to_string()).or_insert(0) += 1;
    }

    // Calculate selection rates by quality tier
    let high_quality_selections: usize = selections
        .iter()
        .filter(|(addr, _)| addr.starts_with("192.168.1.10"))
        .map(|(_, count)| count)
        .sum();
    let low_quality_selections: usize = selections
        .iter()
        .filter(|(addr, _)| addr.starts_with("192.168.1.12"))
        .map(|(_, count)| count)
        .sum();

    let high_rate = high_quality_selections as f64 / 1000.0;
    let low_rate = low_quality_selections as f64 / 1000.0;

    println!(
        "  High-quality relay selection rate: {:.1}%",
        high_rate * 100.0
    );
    println!(
        "  Low-quality relay selection rate: {:.1}%",
        low_rate * 100.0
    );

    assert!(
        high_rate > low_rate * 2.0,
        "High-quality relays should be selected at least 2x more often"
    );
    println!("✓ Weighted selection favors high-quality relays");

    // Test 6: Unique multi-hop path selection
    let path = lottery.select_unique_relays(3).unwrap();
    assert_eq!(path.len(), 3, "Should select exactly 3 relays");

    let unique_count = path.iter().collect::<std::collections::HashSet<_>>().len();
    assert_eq!(unique_count, 3, "All selected relays should be unique");
    println!(
        "✓ Multi-hop path selection works: {} unique relays",
        unique_count
    );

    // Test 7: Reputation update mechanism
    let test_addr = "192.168.1.100:8080".parse().unwrap();
    let initial_relay = lottery.get_relay(&test_addr).unwrap().clone();
    let initial_reputation = initial_relay.reputation;

    // Simulate successful relay
    lottery.update_relay_reputation(&test_addr, true);
    let updated_relay = lottery.get_relay(&test_addr).unwrap();
    assert!(
        updated_relay.reputation > initial_reputation,
        "Reputation should increase after success"
    );

    println!("  Initial reputation: {:.3}", initial_reputation);
    println!("  After success: {:.3}", updated_relay.reputation);
    println!("✓ Reputation update mechanism works correctly");
}

#[test]
fn test_poisson_delay_statistical_properties() {
    // Scenario: Generate delays for traffic analysis resistance
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(50);
    let max = Duration::from_millis(2000);

    let generator = PoissonDelayGenerator::new(mean, min, max).unwrap();
    println!("✓ Created Poisson delay generator (mean=500ms, min=50ms, max=2000ms)");

    // Test 8: Generate large sample and verify statistical properties
    let sample_size = 10000;
    let delays = generator.next_delays(sample_size);

    // Verify all delays are within bounds
    for (i, delay) in delays.iter().enumerate() {
        assert!(*delay >= min, "Delay {} below minimum: {:?}", i, delay);
        assert!(*delay <= max, "Delay {} above maximum: {:?}", i, delay);
    }
    println!("✓ All {} delays within bounds [50ms, 2000ms]", sample_size);

    // Calculate mean
    let sum: u64 = delays.iter().map(|d| d.as_millis() as u64).sum();
    let actual_mean = sum as f64 / sample_size as f64;
    let expected_mean = mean.as_millis() as f64;
    let tolerance = expected_mean * 0.1; // 10% tolerance

    println!("  Expected mean: {:.1}ms", expected_mean);
    println!("  Actual mean: {:.1}ms", actual_mean);
    println!("  Tolerance: ±{:.1}ms", tolerance);

    assert!(
        (actual_mean - expected_mean).abs() < tolerance,
        "Mean {:.1}ms outside tolerance of {:.1}ms ± {:.1}ms",
        actual_mean,
        expected_mean,
        tolerance
    );
    println!("✓ Statistical mean within 10% tolerance");

    // Test 9: Verify exponential distribution shape (should have long tail)
    let median_delay = {
        let mut sorted = delays.clone();
        sorted.sort();
        sorted[sample_size / 2].as_millis() as f64
    };

    // For exponential distribution: median ≈ 0.693 * mean
    let expected_median = expected_mean * 0.693;
    let median_tolerance = expected_mean * 0.15; // 15% tolerance

    println!("  Expected median: {:.1}ms", expected_median);
    println!("  Actual median: {:.1}ms", median_delay);

    assert!(
        (median_delay - expected_median).abs() < median_tolerance,
        "Median doesn't match exponential distribution"
    );
    println!("✓ Distribution shape matches exponential (Poisson inter-arrival times)");

    // Test 10: Verify variance ≈ mean² (exponential property)
    let variance: f64 = delays
        .iter()
        .map(|d| {
            let diff = d.as_millis() as f64 - actual_mean;
            diff * diff
        })
        .sum::<f64>()
        / sample_size as f64;
    let std_dev = variance.sqrt();

    println!("  Standard deviation: {:.1}ms", std_dev);
    println!("  Mean: {:.1}ms", actual_mean);
    println!("  Ratio (std_dev/mean): {:.2}", std_dev / actual_mean);

    // For exponential: std_dev ≈ mean (coefficient of variation ≈ 1)
    let cv = std_dev / actual_mean;
    assert!(
        cv > 0.8 && cv < 1.2,
        "Coefficient of variation {} outside expected range for exponential",
        cv
    );
    println!("✓ Variance matches exponential distribution properties");
}

#[cfg(feature = "vrf")]
#[tokio::test]
async fn test_vrf_poisson_delay_unpredictability() {
    // Test 11: VRF-seeded delays should be unpredictable but valid
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(100);
    let max = Duration::from_millis(2000);

    let mut delays = Vec::new();
    for _ in 0..100 {
        let delay = calculate_vrf_poisson_delay(&mean, &min, &max)
            .await
            .unwrap();
        assert!(delay >= min && delay <= max, "VRF delay out of bounds");
        delays.push(delay);
    }

    println!("✓ Generated 100 VRF-seeded Poisson delays");

    // Verify delays are not all the same (unpredictability)
    let unique_delays: std::collections::HashSet<_> =
        delays.iter().map(|d| d.as_millis()).collect();

    assert!(
        unique_delays.len() > 50,
        "VRF delays should be highly varied (got {} unique values)",
        unique_delays.len()
    );

    println!("  Unique delay values: {}/100", unique_delays.len());
    println!("✓ VRF delays demonstrate proper unpredictability");
}

#[test]
fn test_integration_protocol_and_relay_selection() {
    // Test 12: Integration test - protocol negotiation + relay selection
    println!("\n=== Integration Test: Protocol + Relay Selection ===");

    // Setup: Create network with versioned relays
    let mut lottery = RelayLottery::new();

    // Add v1.2.0 relays
    for i in 0..5 {
        lottery.add_relay(WeightedRelay::new(
            format!("10.0.0.{}:8080", i).parse().unwrap(),
            0.9,
            0.9,
            10000,
        ));
    }

    // Negotiate protocol with peer
    let our_version = ProtocolVersion::V1_2_0;
    let peer_version = ProtocolVersion::V1_1_0;

    let negotiated = match negotiate_version(our_version, peer_version) {
        NegotiationResult::Compatible(v) => v,
        _ => panic!("Negotiation failed"),
    };

    println!(
        "✓ Protocol negotiated: {} with {}",
        our_version, peer_version
    );
    println!("  Using version: {}", negotiated);

    // Select relay for connection
    let relay = lottery.select_relay().unwrap();
    let relay_addr = relay.address;
    let relay_reputation = relay.reputation;
    println!("✓ Selected relay: {}", relay_addr);
    println!("  Relay reputation: {:.2}", relay_reputation);
    println!("  Relay weight: {:.3}", relay.weight);

    // Simulate connection attempt
    lottery.update_relay_reputation(&relay_addr, true);
    let updated = lottery.get_relay(&relay_addr).unwrap();

    println!(
        "✓ Connection successful, reputation updated: {:.2} -> {:.2}",
        relay_reputation, updated.reputation
    );
}

#[test]
fn test_edge_cases_and_error_handling() {
    println!("\n=== Edge Case Testing ===");

    // Test 13: Empty relay lottery
    let mut empty_lottery = RelayLottery::new();
    let result = empty_lottery.select_relay();
    assert!(result.is_err(), "Should fail to select from empty lottery");
    println!("✓ Empty lottery correctly returns error");

    // Test 14: Request more unique relays than available
    let mut small_lottery = RelayLottery::new();
    for i in 0..3 {
        small_lottery.add_relay(WeightedRelay::new(
            format!("10.0.0.{}:8080", i).parse().unwrap(),
            0.8,
            0.8,
            1000,
        ));
    }

    let result = small_lottery.select_unique_relays(5);
    assert!(
        result.is_err(),
        "Should fail when requesting more relays than available"
    );
    println!("✓ Correctly handles over-selection request");

    // Test 15: Invalid Poisson delay configuration
    let result = PoissonDelayGenerator::new(
        Duration::from_millis(500),  // mean
        Duration::from_millis(600),  // min > mean (invalid)
        Duration::from_millis(1000), // max
    );
    assert!(result.is_err(), "Should reject invalid delay configuration");
    println!("✓ Invalid delay configuration correctly rejected");

    // Test 16: Protocol version incompatibility
    let v1 = ProtocolVersion::new(1, 2, 0);
    let v2 = ProtocolVersion::new(2, 0, 0); // Different major version

    match negotiate_version(v1, v2) {
        NegotiationResult::Incompatible { .. } => {
            println!("✓ Incompatible major versions correctly detected");
        }
        _ => panic!("Should detect incompatible major versions"),
    }
}
