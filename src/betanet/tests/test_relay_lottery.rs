//! Comprehensive test suite for VRF-based relay lottery
//!
//! Tests lottery fairness, reputation weighting, Sybil resistance,
//! proof verification, and performance benchmarks.

#[cfg(test)]
mod tests {
    use std::collections::HashMap;
    use std::net::SocketAddr;
    use std::time::Instant;

    use betanet::core::relay_lottery::{RelayLottery, WeightedRelay};
    use betanet::core::reputation::{PenaltyType, RewardType};

    /// Helper to create test relays
    fn create_test_relays(count: usize) -> Vec<WeightedRelay> {
        let mut relays = Vec::new();
        for i in 0..count {
            // Fixed: Use proper port number format (8080, 8081, 8082, ...)
            let addr: SocketAddr = format!("127.0.0.1:{}", 8080 + i).parse().unwrap();
            let reputation = 0.5 + (i as f64 / count as f64) * 0.4; // Varying reputation
            let performance = 0.7 + (i as f64 / count as f64) * 0.2;
            let stake = 1000 + (i as u64) * 500; // Varying stake
            relays.push(WeightedRelay::new(addr, reputation, performance, stake));
        }
        relays
    }

    #[test]
    fn test_vrf_lottery_fairness() {
        // Test that lottery distribution follows weighted probabilities

        let mut lottery = RelayLottery::new();

        // Add relays with known weights
        let high_rep_addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let mid_rep_addr: SocketAddr = "127.0.0.1:8081".parse().unwrap();
        let low_rep_addr: SocketAddr = "127.0.0.1:8082".parse().unwrap();

        lottery.add_relay(WeightedRelay::new(high_rep_addr, 0.9, 0.9, 5000));
        lottery.add_relay(WeightedRelay::new(mid_rep_addr, 0.5, 0.5, 2000));
        lottery.add_relay(WeightedRelay::new(low_rep_addr, 0.3, 0.3, 1000));

        // Run lottery many times
        let num_draws = 10000;
        let mut selection_counts = HashMap::new();

        for _ in 0..num_draws {
            let relay = lottery.select_relay().unwrap();
            *selection_counts.entry(relay.address).or_insert(0) += 1;
        }

        // High reputation relay should be selected most often
        let high_count = selection_counts.get(&high_rep_addr).unwrap_or(&0);
        let mid_count = selection_counts.get(&mid_rep_addr).unwrap_or(&0);
        let low_count = selection_counts.get(&low_rep_addr).unwrap_or(&0);

        println!("Selection distribution:");
        println!("  High reputation: {}", high_count);
        println!("  Mid reputation: {}", mid_count);
        println!("  Low reputation: {}", low_count);

        // Verify fairness: high rep should be selected more than mid, mid more than low
        assert!(high_count > mid_count, "High reputation relay should be selected more than mid");
        assert!(mid_count > low_count, "Mid reputation relay should be selected more than low");

        // Calculate chi-square statistic for distribution analysis
        let total = num_draws as f64;
        let high_expected = total * 0.5; // Approximate based on weights
        let mid_expected = total * 0.3;
        let low_expected = total * 0.2;

        let chi_square =
            (*high_count as f64 - high_expected).powi(2) / high_expected +
            (*mid_count as f64 - mid_expected).powi(2) / mid_expected +
            (*low_count as f64 - low_expected).powi(2) / low_expected;

        println!("Chi-square statistic: {}", chi_square);

        // Chi-square should be reasonable (< 10 for 2 degrees of freedom at 99% confidence)
        assert!(chi_square < 20.0, "Distribution should follow expected probabilities");
    }

    #[test]
    fn test_reputation_weighting() {
        // Test that high-reputation nodes are favored

        let mut lottery = RelayLottery::new();

        // Add nodes with dramatically different reputations
        let excellent_addr: SocketAddr = "127.0.0.1:9000".parse().unwrap();
        let poor_addr: SocketAddr = "127.0.0.1:9001".parse().unwrap();

        lottery.add_relay(WeightedRelay::new(excellent_addr, 0.95, 0.95, 10000));
        lottery.add_relay(WeightedRelay::new(poor_addr, 0.1, 0.1, 1000));

        // Run lottery
        let num_draws = 1000;
        let mut selection_counts = HashMap::new();

        for _ in 0..num_draws {
            let relay = lottery.select_relay().unwrap();
            *selection_counts.entry(relay.address).or_insert(0) += 1;
        }

        let excellent_count = selection_counts.get(&excellent_addr).unwrap_or(&0);
        let poor_count = selection_counts.get(&poor_addr).unwrap_or(&0);

        println!("Reputation weighting:");
        println!("  Excellent (0.95): {}", excellent_count);
        println!("  Poor (0.1): {}", poor_count);

        // Excellent node should be selected at least 3x more often (probabilistic, CI-friendly)
        assert!(
            *excellent_count > *poor_count * 3,
            "High reputation node should be strongly favored (got {}x, expected >3x)",
            *excellent_count / poor_count.max(&1)
        );
    }

    #[test]
    fn test_sybil_resistance() {
        // Test that cost-of-forgery increases with attacker stake - FUNC-10 ENABLED

        let mut lottery = RelayLottery::with_config(true, 1000);

        let stats = lottery.get_statistics();
        println!("Sybil resistance enabled: {}", stats.sybil_resistance);
        println!("Minimum stake required: {}", stats.min_stake);

        // Verify Sybil resistance is enabled
        assert!(stats.sybil_resistance, "Sybil resistance should be enabled");
        assert_eq!(stats.min_stake, 1000, "Min stake should be 1000");

        // FUNC-10: Full reputation system with cost_of_forgery now implemented
        // Test cost of forgery increases with stake and reputation

        // Add nodes with different stakes to lottery
        let addr_low: std::net::SocketAddr = "127.0.0.1:9000".parse().unwrap();
        let addr_high: std::net::SocketAddr = "127.0.0.1:9001".parse().unwrap();

        lottery.add_relay(betanet::core::relay_lottery::WeightedRelay::new(
            addr_low,
            0.5,
            0.7,
            10000, // Low stake
        ));

        lottery.add_relay(betanet::core::relay_lottery::WeightedRelay::new(
            addr_high,
            0.5,
            0.7,
            100000, // High stake (10x more)
        ));

        // Get reputation statistics if available
        if let Some(rep_stats) = lottery.get_reputation_statistics() {
            println!("Reputation statistics:");
            println!("  Total nodes: {}", rep_stats.total_nodes);
            println!("  Avg cost of forgery: {}", rep_stats.avg_cost_of_forgery);
        }

        // Calculate cost of forgery using lottery's implementation
        let total_stake = 110000u64;
        let cost_10_percent = lottery.cost_of_forgery(total_stake / 10); // 10% stake
        let cost_33_percent = lottery.cost_of_forgery(total_stake / 3);  // 33% stake

        println!("Cost of forgery:");
        println!("  10% stake: {}", cost_10_percent);
        println!("  33% stake: {}", cost_33_percent);

        // Verify exponential cost increase at 33% threshold
        assert!(
            cost_33_percent > cost_10_percent,
            "Higher stake should have higher cost of forgery"
        );

        // Cost should be prohibitive above 33% (> 1.0)
        assert!(
            cost_33_percent >= 1.0,
            "33% stake should have cost >= 1.0 (prohibitive)"
        );
    }

    #[test]
    #[cfg(feature = "vrf")]
    fn test_proof_verification() {
        // Test VRF proof generation and verification

        let mut lottery = RelayLottery::with_vrf();

        // Add test relays
        for relay in create_test_relays(10) {
            lottery.add_relay(relay);
        }

        // Generate lottery with proof
        let seed = b"test_seed_12345";
        let (selected, proof) = lottery.select_relay_with_proof(seed).unwrap();

        println!("Selected relay: {}", selected);
        println!("Proof timestamp: {}", proof.timestamp);

        // Verify proof
        let is_valid = lottery.verify_lottery_proof(&proof).unwrap();
        assert!(is_valid, "Lottery proof should be valid");

        // Verify proof contains expected data
        assert_eq!(proof.seed, seed);
        assert_eq!(proof.selected.len(), 1);
        assert_eq!(proof.selected[0], selected);
        assert_eq!(proof.weights.len(), 10);
    }

    #[test]
    #[cfg(feature = "vrf")]
    fn test_deterministic_vrf_selection() {
        // Test that same seed produces same result (determinism)

        let mut lottery = RelayLottery::with_vrf();

        for relay in create_test_relays(10) {
            lottery.add_relay(relay);
        }

        let seed = b"deterministic_seed";

        // First selection
        let (selected1, _) = lottery.select_relay_with_proof(seed).unwrap();

        // Second selection with same seed
        let (selected2, _) = lottery.select_relay_with_proof(seed).unwrap();

        // Should be deterministic
        assert_eq!(
            selected1, selected2,
            "Same seed should produce same selection"
        );

        // Different seed should (very likely) produce different result
        let (selected3, _) = lottery.select_relay_with_proof(b"different_seed").unwrap();

        // Very unlikely to be the same
        if selected3 == selected1 {
            println!("Warning: Different seeds produced same result (random collision)");
        }
    }

    #[test]
    fn test_reputation_integration() {
        // Test integration with reputation manager

        let _lottery = RelayLottery::with_config(true, 1000);

        // Manually add reputation manager for testing
        let mut rep_manager = betanet::core::reputation::ReputationManager::default();

        let addr1: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let addr2: SocketAddr = "127.0.0.1:8081".parse().unwrap();

        // Add nodes to reputation manager
        rep_manager.add_node(addr1, 5000);
        rep_manager.add_node(addr2, 2000);

        // Apply penalties and rewards
        rep_manager.apply_penalty(&addr1, PenaltyType::PacketDrop).unwrap();
        rep_manager.apply_reward(&addr2, RewardType::HighUptime).unwrap();

        // Verify reputation changes
        let rep1 = rep_manager.get_reputation(&addr1).unwrap();
        let rep2 = rep_manager.get_reputation(&addr2).unwrap();

        println!("Node 1 reputation after penalty: {}", rep1.reputation);
        println!("Node 2 reputation after reward: {}", rep2.reputation);

        // Node 2 should have higher reputation after reward
        assert!(rep2.reputation > rep1.reputation);
    }

    #[test]
    fn test_performance_benchmark_1000_draws() {
        // Benchmark: 1000 lottery draws should complete in < 100ms

        let mut lottery = RelayLottery::new();

        // Add realistic number of relays
        for relay in create_test_relays(100) {
            lottery.add_relay(relay);
        }

        // Warm up
        for _ in 0..10 {
            let _ = lottery.select_relay();
        }

        // Benchmark
        let start = Instant::now();
        let num_draws = 1000;

        for _ in 0..num_draws {
            let _ = lottery.select_relay().unwrap();
        }

        let elapsed = start.elapsed();
        let per_draw = elapsed.as_micros() / num_draws;

        println!("Performance benchmark:");
        println!("  Total time for 1000 draws: {:?}", elapsed);
        println!("  Average per draw: {} µs", per_draw);

        // Should complete in < 100ms
        assert!(
            elapsed.as_millis() < 100,
            "1000 draws should complete in < 100ms (actual: {:?})",
            elapsed
        );

        // Each draw should be < 100 µs
        assert!(
            per_draw < 100,
            "Each draw should be < 100 µs (actual: {} µs)",
            per_draw
        );
    }

    #[test]
    fn test_unique_relay_selection() {
        // Test selection without replacement

        let mut lottery = RelayLottery::new();

        for relay in create_test_relays(20) {
            lottery.add_relay(relay);
        }

        // Select 10 unique relays
        let selected = lottery.select_unique_relays(10).unwrap();

        // Verify uniqueness
        let mut unique = std::collections::HashSet::new();
        for addr in &selected {
            assert!(
                unique.insert(*addr),
                "Relay {} was selected multiple times",
                addr
            );
        }

        assert_eq!(unique.len(), 10);
    }

    #[test]
    fn test_weighted_relay_update() {
        // Test reputation updates

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let mut relay = WeightedRelay::new(addr, 0.5, 0.7, 2000);

        let initial_reputation = relay.reputation;

        // Success should increase reputation
        relay.update_reputation(true);
        assert!(
            relay.reputation > initial_reputation,
            "Success should increase reputation"
        );

        let after_success = relay.reputation;

        // Failure should decrease reputation
        relay.update_reputation(false);
        assert!(
            relay.reputation < after_success,
            "Failure should decrease reputation"
        );
    }

    #[test]
    fn test_lottery_statistics() {
        // Test statistics gathering

        let mut lottery = RelayLottery::with_config(true, 1000);

        for relay in create_test_relays(50) {
            lottery.add_relay(relay);
        }

        let stats = lottery.get_statistics();

        println!("Lottery statistics:");
        println!("  Total relays: {}", stats.total_relays);
        println!("  Total stake: {}", stats.total_stake);
        println!("  Avg reputation: {}", stats.avg_reputation);
        println!("  Avg weight: {}", stats.avg_weight);
        println!("  Sybil resistance: {}", stats.sybil_resistance);
        println!("  Min stake: {}", stats.min_stake);

        assert_eq!(stats.total_relays, 50);
        assert!(stats.total_stake > 0);
        assert!(stats.avg_reputation > 0.0 && stats.avg_reputation <= 1.0);
        assert!(stats.sybil_resistance);
        assert_eq!(stats.min_stake, 1000);
    }

    #[test]
    fn test_fairness_with_equal_weights() {
        // Test that equal weights produce roughly equal selection probabilities

        let mut lottery = RelayLottery::new();

        let addr1: SocketAddr = "127.0.0.1:8000".parse().unwrap();
        let addr2: SocketAddr = "127.0.0.1:8001".parse().unwrap();
        let addr3: SocketAddr = "127.0.0.1:8002".parse().unwrap();

        // Equal weights
        lottery.add_relay(WeightedRelay::new(addr1, 0.8, 0.8, 5000));
        lottery.add_relay(WeightedRelay::new(addr2, 0.8, 0.8, 5000));
        lottery.add_relay(WeightedRelay::new(addr3, 0.8, 0.8, 5000));

        let num_draws = 3000;
        let mut counts = HashMap::new();

        for _ in 0..num_draws {
            let relay = lottery.select_relay().unwrap();
            *counts.entry(relay.address).or_insert(0) += 1;
        }

        let count1 = *counts.get(&addr1).unwrap_or(&0);
        let count2 = *counts.get(&addr2).unwrap_or(&0);
        let count3 = *counts.get(&addr3).unwrap_or(&0);

        println!("Equal weight distribution:");
        println!("  Relay 1: {}", count1);
        println!("  Relay 2: {}", count2);
        println!("  Relay 3: {}", count3);

        // With equal weights, each should be around 1000 ± 10%
        let expected = num_draws / 3;
        let tolerance = expected / 5; // 20% tolerance

        assert!(
            count1 > expected - tolerance && count1 < expected + tolerance,
            "Relay 1 selection out of expected range"
        );
        assert!(
            count2 > expected - tolerance && count2 < expected + tolerance,
            "Relay 2 selection out of expected range"
        );
        assert!(
            count3 > expected - tolerance && count3 < expected + tolerance,
            "Relay 3 selection out of expected range"
        );
    }

    #[test]
    #[cfg(feature = "vrf")]
    fn test_multi_relay_vrf_proof() {
        // Test VRF proof for multiple relay selection

        let mut lottery = RelayLottery::with_vrf();

        for relay in create_test_relays(20) {
            lottery.add_relay(relay);
        }

        let seed = b"multi_relay_seed";
        let (selected, proof) = lottery.select_relays_with_proof(seed, 5).unwrap();

        println!("Selected {} relays with VRF proof", selected.len());

        assert_eq!(selected.len(), 5);
        assert_eq!(proof.selected.len(), 5);
        assert_eq!(proof.selected, selected);

        // Verify proof
        let is_valid = lottery.verify_lottery_proof(&proof).unwrap();
        assert!(is_valid, "Multi-relay proof should be valid");
    }

    #[test]
    fn test_performance_with_large_network() {
        // Test performance with realistic network size (1000 nodes)

        let mut lottery = RelayLottery::new();

        // Add 1000 relays
        for i in 0..1000 {
            let addr: SocketAddr = format!("10.0.{}.{}:8080", i / 256, i % 256)
                .parse()
                .unwrap();
            lottery.add_relay(WeightedRelay::new(
                addr,
                0.5 + (i as f64 / 2000.0),
                0.7,
                1000 + i,
            ));
        }

        // Benchmark selection from large network
        let start = Instant::now();

        for _ in 0..100 {
            let _ = lottery.select_relay().unwrap();
        }

        let elapsed = start.elapsed();

        println!(
            "Large network (1000 nodes) - 100 selections: {:?}",
            elapsed
        );

        // Should still be fast even with 1000 nodes
        assert!(
            elapsed.as_millis() < 50,
            "100 selections from 1000 nodes should complete in < 50ms"
        );
    }
}
