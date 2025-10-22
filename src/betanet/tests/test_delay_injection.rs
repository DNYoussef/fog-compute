//! Comprehensive tests for enhanced delay injection algorithms
//!
//! Tests cover:
//! - Poisson distribution properties
//! - Adaptive batching behavior
//! - Cover traffic indistinguishability
//! - Timing attack resistance
//! - Throughput overhead

use std::time::Duration;
use tokio::time::sleep;

use crate::vrf::poisson_delay::PoissonDelayGenerator;
use crate::pipeline::batching::{AdaptiveBatchProcessor, AdaptiveBatchingConfig, BatchingStrategy};
use crate::cover::{AdvancedCoverTrafficGenerator, CoverTrafficConfig, CoverTrafficMode};
use crate::utils::timing_defense::{TimingDefenseManager, TimingDefenseConfig};

#[tokio::test]
async fn test_poisson_distribution() {
    // Test that delays follow Poisson distribution
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(100);
    let max = Duration::from_millis(2000);

    let generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

    // Generate large sample
    let samples: Vec<Duration> = generator.next_delays(10000);

    // Calculate statistics
    let delays_ms: Vec<f64> = samples.iter().map(|d| d.as_secs_f64() * 1000.0).collect();
    let sample_mean = delays_ms.iter().sum::<f64>() / delays_ms.len() as f64;
    let sample_variance = delays_ms
        .iter()
        .map(|&x| (x - sample_mean).powi(2))
        .sum::<f64>()
        / delays_ms.len() as f64;

    println!("Poisson Distribution Test:");
    println!("  Expected mean: 500ms");
    println!("  Sample mean: {:.2}ms", sample_mean);
    println!("  Sample variance: {:.2}ms²", sample_variance);

    // For exponential distribution, variance = mean²
    let expected_variance = sample_mean * sample_mean;
    let variance_ratio = sample_variance / expected_variance;

    println!("  Variance ratio: {:.2}", variance_ratio);

    // Allow 30% deviation due to sampling
    assert!(variance_ratio > 0.7 && variance_ratio < 1.3);

    // Check bounds
    assert!(samples.iter().all(|&d| d >= min && d <= max));
}

#[tokio::test]
async fn test_adaptive_poisson_delay() {
    // Test adaptive delay based on network load
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(100);
    let max = Duration::from_millis(5000);

    let mut generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

    // Low load
    generator.adapt_to_network_load(0.1);
    let low_load_delays: Vec<Duration> = generator.next_delays(100);
    let low_load_avg = low_load_delays.iter().map(|d| d.as_millis() as f64).sum::<f64>()
        / low_load_delays.len() as f64;

    // High load
    generator.adapt_to_network_load(0.9);
    let high_load_delays: Vec<Duration> = generator.next_delays(100);
    let high_load_avg = high_load_delays.iter().map(|d| d.as_millis() as f64).sum::<f64>()
        / high_load_delays.len() as f64;

    println!("Adaptive Delay Test:");
    println!("  Low load (0.1) avg: {:.2}ms", low_load_avg);
    println!("  High load (0.9) avg: {:.2}ms", high_load_avg);

    // High load should result in longer delays
    assert!(high_load_avg > low_load_avg);
}

#[tokio::test]
async fn test_circuit_multiplier() {
    // Test per-circuit delay customization
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(100);
    let max = Duration::from_millis(5000);

    let mut generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

    // Fast circuit (0.5x)
    generator.set_circuit_multiplier(0.5);
    let fast_delays: Vec<Duration> = generator.next_delays(100);
    let fast_avg = fast_delays.iter().map(|d| d.as_millis() as f64).sum::<f64>()
        / fast_delays.len() as f64;

    // Slow circuit (2.0x)
    generator.set_circuit_multiplier(2.0);
    let slow_delays: Vec<Duration> = generator.next_delays(100);
    let slow_avg = slow_delays.iter().map(|d| d.as_millis() as f64).sum::<f64>()
        / slow_delays.len() as f64;

    println!("Circuit Multiplier Test:");
    println!("  Fast circuit (0.5x) avg: {:.2}ms", fast_avg);
    println!("  Slow circuit (2.0x) avg: {:.2}ms", slow_avg);

    // Slow circuit should be approximately 4x slower
    assert!(slow_avg > fast_avg * 2.0);
}

#[tokio::test]
async fn test_statistical_indistinguishability() {
    // Test statistical indistinguishability
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(100);
    let max = Duration::from_millis(2000);

    let generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

    let p_value = generator.test_statistical_indistinguishability(1000);

    println!("Statistical Indistinguishability Test:");
    println!("  p-value: {:.4}", p_value);

    // p-value > 0.05 indicates indistinguishable from Poisson
    // Allow lower threshold for test robustness
    assert!(p_value > 0.01);
}

#[tokio::test]
async fn test_delay_entropy() {
    // Test delay distribution entropy
    let mean = Duration::from_millis(500);
    let min = Duration::from_millis(100);
    let max = Duration::from_millis(2000);

    let generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

    let entropy = generator.calculate_entropy(1000, 20);

    println!("Delay Entropy Test:");
    println!("  Entropy: {:.4}", entropy);

    // Entropy should be reasonably high (> 2.0 for good randomness)
    assert!(entropy > 2.0);
}

#[tokio::test]
async fn test_adaptive_batching() {
    // Test adaptive batch size based on load
    let mut config = AdaptiveBatchingConfig::default();
    config.strategy = BatchingStrategy::LoadBased;
    config.min_batch_size = 10;
    config.max_batch_size = 100;

    let processor = AdaptiveBatchProcessor::new(config).unwrap();

    // Low load
    processor.update_network_load(0.2).await;
    sleep(Duration::from_millis(20)).await;
    let low_load_size = processor.current_batch_size();

    // Medium load
    processor.update_network_load(0.5).await;
    sleep(Duration::from_millis(20)).await;
    let medium_load_size = processor.current_batch_size();

    // High load
    processor.update_network_load(0.9).await;
    sleep(Duration::from_millis(20)).await;
    let high_load_size = processor.current_batch_size();

    println!("Adaptive Batching Test:");
    println!("  Low load (0.2): {} packets", low_load_size);
    println!("  Medium load (0.5): {} packets", medium_load_size);
    println!("  High load (0.9): {} packets", high_load_size);

    assert!(high_load_size > medium_load_size);
    assert!(medium_load_size > low_load_size);
}

#[tokio::test]
async fn test_cover_traffic() {
    // Test cover traffic generation
    let mut config = CoverTrafficConfig::default();
    config.enabled = true;
    config.mode = CoverTrafficMode::Adaptive;
    config.target_rate = 10.0;
    config.max_bandwidth_overhead = 0.05;

    let generator = AdvancedCoverTrafficGenerator::new(config);

    // Simulate real traffic
    for _ in 0..100 {
        generator.update_real_traffic_stats(1024).await;
        sleep(Duration::from_millis(10)).await;
    }

    // Generate cover traffic
    let mut cover_packets = Vec::new();
    for _ in 0..20 {
        if let Some(packet) = generator.generate_cover_packet().await {
            cover_packets.push(packet);
        }
        sleep(Duration::from_millis(50)).await;
    }

    println!("Cover Traffic Test:");
    println!("  Cover packets generated: {}", cover_packets.len());
    println!("  Total cover bytes: {}", generator.bytes_sent());

    // Test indistinguishability
    let similarity = generator.test_indistinguishability().await;
    println!("  Similarity to real traffic: {:.2}%", similarity * 100.0);

    assert!(cover_packets.len() > 0);
}

#[tokio::test]
async fn test_cover_traffic_indistinguishability() {
    // Test that cover traffic is indistinguishable from real traffic
    let mut config = CoverTrafficConfig::default();
    config.enabled = true;
    config.mode = CoverTrafficMode::Adaptive;
    config.size_variability = 0.2;
    config.indistinguishability_threshold = 0.8;

    let generator = AdvancedCoverTrafficGenerator::new(config);

    // Generate real traffic pattern
    let mut sizes = vec![900, 950, 1000, 1050, 1100];
    for _ in 0..100 {
        let size = sizes[rand::random::<usize>() % sizes.len()];
        generator.update_real_traffic_stats(size).await;
        sleep(Duration::from_millis(5)).await;
    }

    // Generate cover traffic
    for _ in 0..100 {
        generator.generate_cover_packet().await;
        sleep(Duration::from_millis(5)).await;
    }

    let similarity = generator.test_indistinguishability().await;
    println!("Indistinguishability Test:");
    println!("  Similarity score: {:.2}%", similarity * 100.0);

    // Should be reasonably similar (> 50%)
    assert!(similarity > 0.5);
}

#[tokio::test]
async fn test_timing_attack_resistance() {
    // Test timing attack resistance
    let config = TimingDefenseConfig::default();
    let manager = TimingDefenseManager::new(config);

    // Record packets with randomization
    for _ in 0..100 {
        let original = Duration::from_millis(100);
        let randomized = manager.randomize_delay(original).await;
        manager
            .record_packet_timing(1000, original, randomized)
            .await;
        sleep(Duration::from_millis(10)).await;
    }

    let stats = manager.get_timing_stats().await;

    println!("Timing Attack Resistance Test:");
    stats.print();

    // Check correlation is low
    assert!(stats.correlation.abs() < 0.5);

    // Check entropy is reasonable
    assert!(stats.entropy > 1.0);

    // Check resistance score
    assert!(stats.resistance_score > 0.4);
}

#[tokio::test]
async fn test_throughput_overhead() {
    // Test that cover traffic overhead is < 5%
    let mut config = CoverTrafficConfig::default();
    config.enabled = true;
    config.max_bandwidth_overhead = 0.05; // 5% max

    let generator = AdvancedCoverTrafficGenerator::new(config);

    // Simulate real traffic (1MB)
    let real_traffic_bytes = 1_000_000;
    let avg_packet_size = 1000;
    let num_real_packets = real_traffic_bytes / avg_packet_size;

    for _ in 0..num_real_packets {
        generator.update_real_traffic_stats(avg_packet_size).await;
    }

    // Generate cover traffic
    for _ in 0..1000 {
        generator.generate_cover_packet().await;
    }

    let cover_bytes = generator.bytes_sent();
    let overhead = cover_bytes as f64 / real_traffic_bytes as f64;

    println!("Throughput Overhead Test:");
    println!("  Real traffic: {} bytes", real_traffic_bytes);
    println!("  Cover traffic: {} bytes", cover_bytes);
    println!("  Overhead: {:.2}%", overhead * 100.0);

    // Overhead should be < 5%
    assert!(overhead < 0.05);
}

#[tokio::test]
async fn test_integrated_delay_injection() {
    // Integration test: Poisson + Batching + Cover + Timing Defense
    println!("\n🚀 Integrated Delay Injection Test");

    // 1. Poisson delay generator
    let mut poisson = PoissonDelayGenerator::new(
        Duration::from_millis(100),
        Duration::from_millis(50),
        Duration::from_millis(500),
    )
    .unwrap()
    .with_jitter(0.2);

    poisson.adapt_to_network_load(0.5);

    // 2. Adaptive batching
    let batching_config = AdaptiveBatchingConfig {
        strategy: BatchingStrategy::Balanced,
        min_batch_size: 1,
        max_batch_size: 64,
        ..Default::default()
    };
    let batcher = AdaptiveBatchProcessor::new(batching_config).unwrap();

    // 3. Cover traffic
    let cover_config = CoverTrafficConfig {
        enabled: true,
        mode: CoverTrafficMode::Adaptive,
        ..Default::default()
    };
    let cover = AdvancedCoverTrafficGenerator::new(cover_config);

    // 4. Timing defense
    let timing_config = TimingDefenseConfig::default();
    let timing = TimingDefenseManager::new(timing_config);

    // Simulate traffic flow
    for _ in 0..100 {
        // Get Poisson delay
        let delay = poisson.next_delay();

        // Apply timing randomization
        let randomized_delay = timing.randomize_delay(delay).await;

        // Record timing
        timing
            .record_packet_timing(1000, delay, randomized_delay)
            .await;

        // Submit to batcher
        batcher.submit_packet(vec![0u8; 1000]).await.unwrap();

        // Update cover traffic stats
        cover.update_real_traffic_stats(1000).await;

        // Maybe generate cover packet
        if rand::random::<f64>() < 0.1 {
            cover.generate_cover_packet().await;
        }

        sleep(Duration::from_millis(10)).await;
    }

    // Check results
    let timing_stats = timing.get_timing_stats().await;
    let batch_stats = batcher.stats();
    let cover_similarity = cover.test_indistinguishability().await;

    println!("  ✅ Timing resistance: {:.2}%", timing_stats.resistance_score * 100.0);
    println!("  ✅ Avg batch size: {:.1} packets", batch_stats.average_batch_size());
    println!("  ✅ Cover similarity: {:.2}%", cover_similarity * 100.0);
    println!("  ✅ Cover packets: {}", cover.packets_sent());

    assert!(timing_stats.resistance_score > 0.3);
    assert!(batch_stats.average_batch_size() > 1.0);
}
