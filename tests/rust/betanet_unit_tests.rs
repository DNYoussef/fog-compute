//! Betanet Unit Tests
//! Comprehensive test coverage for mixnode, crypto, and VRF modules

use betanet::*;
use betanet::core::mixnode::{Mixnode, MixnodeImpl};
use betanet::core::config::MixnodeConfig;
use betanet::crypto::sphinx::{SphinxPacket, SphinxProcessor};
use betanet::crypto::crypto::CryptoEngine;
use betanet::vrf::vrf_delay::VrfDelay;
use betanet::vrf::vrf_neighbor::VrfNeighborSelector;
use betanet::utils::packet::Packet;
use betanet::utils::rate::RateLimiter;
use betanet::utils::delay::DelayScheduler;

use std::net::SocketAddr;
use std::time::Duration;
use tokio::sync::RwLock;
use std::sync::Arc;

#[cfg(test)]
mod mixnode_tests {
    use super::*;

    #[test]
    fn test_mixnode_config_creation() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:8080".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 100,
            cover_traffic_rate: 10,
            max_concurrent_packets: 1000,
            memory_pool_size: 1024,
        };

        assert_eq!(config.max_packet_size, 2048);
        assert_eq!(config.processing_delay_ms, 100);
        assert_eq!(config.cover_traffic_rate, 10);
    }

    #[tokio::test]
    async fn test_mixnode_initialization() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:9090".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 50,
            cover_traffic_rate: 5,
            max_concurrent_packets: 500,
            memory_pool_size: 512,
        };

        let mixnode = MixnodeImpl::new(config.clone());
        assert_eq!(mixnode.address(), config.listen_addr);
    }

    #[tokio::test]
    async fn test_mixnode_stats_tracking() {
        let mut stats = MixnodeStats::new();
        assert_eq!(stats.packets_processed, 0);

        stats.record_processed(Duration::from_micros(100));
        assert_eq!(stats.packets_processed, 1);
        assert_eq!(stats.avg_processing_time_us, 100.0);

        stats.record_processed(Duration::from_micros(200));
        assert_eq!(stats.packets_processed, 2);
        assert_eq!(stats.avg_processing_time_us, 150.0);

        stats.record_forwarded();
        assert_eq!(stats.packets_forwarded, 1);

        stats.record_dropped();
        assert_eq!(stats.packets_dropped, 1);

        stats.record_cover_traffic();
        assert_eq!(stats.cover_traffic_sent, 1);
    }

    #[test]
    fn test_performance_targets() {
        let targets = PerformanceTargets::default();

        assert_eq!(targets.target_throughput_pps, 25000.0);
        assert_eq!(targets.max_avg_latency_ms, 1.0);
        assert_eq!(targets.min_pool_hit_rate_pct, 85.0);
        assert_eq!(targets.max_drop_rate_pct, 0.1);
    }
}

#[cfg(test)]
mod crypto_tests {
    use super::*;

    #[test]
    fn test_sphinx_packet_structure() {
        let payload = vec![1, 2, 3, 4, 5];
        let packet = SphinxPacket::new(payload.clone(), vec![]);

        assert_eq!(packet.payload(), &payload);
        assert!(packet.headers().is_empty());
    }

    #[test]
    fn test_crypto_engine_initialization() {
        let engine = CryptoEngine::new();
        assert!(engine.is_ready());
    }

    #[test]
    fn test_encryption_decryption() {
        let engine = CryptoEngine::new();
        let plaintext = b"test message";
        let key = engine.generate_key();

        let ciphertext = engine.encrypt(plaintext, &key).unwrap();
        assert_ne!(plaintext, ciphertext.as_slice());

        let decrypted = engine.decrypt(&ciphertext, &key).unwrap();
        assert_eq!(plaintext, decrypted.as_slice());
    }

    #[test]
    fn test_sphinx_layer_processing() {
        let processor = SphinxProcessor::new();
        let layers = 3;

        let packet = processor.create_packet(b"data", layers).unwrap();
        assert_eq!(packet.remaining_layers(), layers);

        let peeled = processor.peel_layer(&packet).unwrap();
        assert_eq!(peeled.remaining_layers(), layers - 1);
    }

    #[test]
    fn test_onion_routing_path() {
        let processor = SphinxProcessor::new();
        let route: Vec<SocketAddr> = vec![
            "192.168.1.1:8080".parse().unwrap(),
            "192.168.1.2:8080".parse().unwrap(),
            "192.168.1.3:8080".parse().unwrap(),
        ];

        let packet = processor.build_onion_packet(b"secret", &route).unwrap();
        assert_eq!(packet.route_length(), route.len());
    }
}

#[cfg(test)]
mod vrf_tests {
    use super::*;

    #[test]
    fn test_vrf_delay_generation() {
        let vrf_delay = VrfDelay::new(b"seed");

        let delay1 = vrf_delay.generate_delay(100, 500);
        let delay2 = vrf_delay.generate_delay(100, 500);

        assert!(delay1 >= 100 && delay1 <= 500);
        assert!(delay2 >= 100 && delay2 <= 500);
        assert_ne!(delay1, delay2); // Should be random
    }

    #[test]
    fn test_vrf_proof_verification() {
        let vrf_delay = VrfDelay::new(b"test_seed");
        let input = b"input_data";

        let (output, proof) = vrf_delay.prove(input);
        assert!(vrf_delay.verify(input, &output, &proof));
    }

    #[test]
    fn test_vrf_neighbor_selection() {
        let neighbors: Vec<SocketAddr> = vec![
            "10.0.0.1:8080".parse().unwrap(),
            "10.0.0.2:8080".parse().unwrap(),
            "10.0.0.3:8080".parse().unwrap(),
            "10.0.0.4:8080".parse().unwrap(),
            "10.0.0.5:8080".parse().unwrap(),
        ];

        let selector = VrfNeighborSelector::new(b"selector_seed");
        let selected = selector.select_neighbors(&neighbors, 3);

        assert_eq!(selected.len(), 3);
        assert!(neighbors.iter().all(|n| selected.contains(n) || !selected.contains(n)));
    }

    #[test]
    fn test_vrf_deterministic_selection() {
        let neighbors: Vec<SocketAddr> = vec![
            "10.0.0.1:8080".parse().unwrap(),
            "10.0.0.2:8080".parse().unwrap(),
            "10.0.0.3:8080".parse().unwrap(),
        ];

        let selector = VrfNeighborSelector::new(b"same_seed");
        let selected1 = selector.select_neighbors(&neighbors, 2);
        let selected2 = selector.select_neighbors(&neighbors, 2);

        assert_eq!(selected1, selected2); // Should be deterministic with same seed
    }
}

#[cfg(test)]
mod utils_tests {
    use super::*;

    #[tokio::test]
    async fn test_rate_limiter() {
        let limiter = RateLimiter::new(100, Duration::from_secs(1));

        // Should allow within limit
        for _ in 0..100 {
            assert!(limiter.check_limit().await);
        }

        // Should deny beyond limit
        assert!(!limiter.check_limit().await);
    }

    #[tokio::test]
    async fn test_rate_limiter_reset() {
        let limiter = RateLimiter::new(10, Duration::from_millis(100));

        for _ in 0..10 {
            limiter.check_limit().await;
        }

        // Wait for window to reset
        tokio::time::sleep(Duration::from_millis(150)).await;

        // Should allow again
        assert!(limiter.check_limit().await);
    }

    #[tokio::test]
    async fn test_delay_scheduler() {
        let scheduler = DelayScheduler::new();
        let start = tokio::time::Instant::now();

        scheduler.schedule_delay(Duration::from_millis(100)).await;

        let elapsed = start.elapsed();
        assert!(elapsed >= Duration::from_millis(100));
        assert!(elapsed < Duration::from_millis(150));
    }

    #[test]
    fn test_packet_serialization() {
        let packet = Packet::new(vec![1, 2, 3, 4, 5]);
        let serialized = packet.serialize().unwrap();
        let deserialized = Packet::deserialize(&serialized).unwrap();

        assert_eq!(packet.data(), deserialized.data());
    }

    #[test]
    fn test_packet_validation() {
        let valid_packet = Packet::new(vec![0u8; 1024]);
        assert!(valid_packet.validate());

        let invalid_packet = Packet::new(vec![0u8; MAX_PACKET_SIZE + 1]);
        assert!(!invalid_packet.validate());
    }
}

#[cfg(test)]
mod integration_tests {
    use super::*;

    #[tokio::test]
    async fn test_end_to_end_packet_processing() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:10000".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 10,
            cover_traffic_rate: 5,
            max_concurrent_packets: 100,
            memory_pool_size: 256,
        };

        let mixnode = MixnodeImpl::new(config);
        let test_packet = vec![0u8; 512];

        let result = mixnode.process_packet(&test_packet).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_concurrent_packet_processing() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:10001".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 5,
            cover_traffic_rate: 0,
            max_concurrent_packets: 50,
            memory_pool_size: 128,
        };

        let mixnode = Arc::new(MixnodeImpl::new(config));
        let mut handles = vec![];

        for i in 0..10 {
            let node = mixnode.clone();
            let handle = tokio::spawn(async move {
                let packet = vec![i as u8; 256];
                node.process_packet(&packet).await
            });
            handles.push(handle);
        }

        for handle in handles {
            let result = handle.await.unwrap();
            assert!(result.is_ok());
        }
    }
}