//! Adaptive batching for privacy-preserving packet processing
//!
//! Implements dynamic batch sizing based on network load, with configurable
//! privacy-latency trade-offs. Batch sizes adapt from 1-128 packets based on
//! current traffic patterns and load conditions.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;
use tracing::debug;

use crate::Result;

/// Adaptive batching strategy
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BatchingStrategy {
    /// Fixed batch size (no adaptation)
    Fixed,
    /// Adapt based on network load (higher load = larger batches)
    LoadBased,
    /// Optimize for minimum latency (smaller batches)
    MinLatency,
    /// Optimize for maximum throughput (larger batches)
    MaxThroughput,
    /// Balanced privacy-latency trade-off
    Balanced,
}

/// Adaptive batching configuration
#[derive(Debug, Clone)]
pub struct AdaptiveBatchingConfig {
    /// Minimum batch size (must be >= 1)
    pub min_batch_size: usize,
    /// Maximum batch size (must be <= 128)
    pub max_batch_size: usize,
    /// Initial batch size
    pub initial_batch_size: usize,
    /// Batching strategy
    pub strategy: BatchingStrategy,
    /// Minimum delay enforcement (milliseconds)
    pub min_delay_ms: u64,
    /// Maximum throughput target (packets per second)
    pub max_throughput_pps: f64,
    /// Load threshold for batch size increase (0.0-1.0)
    pub load_increase_threshold: f64,
    /// Load threshold for batch size decrease (0.0-1.0)
    pub load_decrease_threshold: f64,
}

impl Default for AdaptiveBatchingConfig {
    fn default() -> Self {
        Self {
            min_batch_size: 1,
            max_batch_size: 128,
            initial_batch_size: 32,
            strategy: BatchingStrategy::Balanced,
            min_delay_ms: 10,
            max_throughput_pps: 25000.0,
            load_increase_threshold: 0.7,
            load_decrease_threshold: 0.3,
        }
    }
}

/// Adaptive batch processor with load-based sizing
pub struct AdaptiveBatchProcessor {
    /// Configuration
    config: AdaptiveBatchingConfig,
    /// Current batch size
    current_batch_size: AtomicUsize,
    /// Network load estimate (0.0-1.0)
    network_load: Arc<Mutex<f64>>,
    /// Packet queue
    packet_queue: Arc<Mutex<VecDeque<Vec<u8>>>>,
    /// Statistics
    stats: Arc<BatchingStats>,
    /// Last batch time
    last_batch_time: Arc<Mutex<Instant>>,
    /// Load estimation window
    load_window: Arc<Mutex<VecDeque<f64>>>,
}

/// Batching statistics
#[derive(Debug)]
pub struct BatchingStats {
    /// Total packets processed
    pub packets_processed: AtomicU64,
    /// Total batches created
    pub batches_created: AtomicU64,
    /// Average batch size
    pub avg_batch_size: AtomicU64,
    /// Total delay added (milliseconds)
    pub total_delay_ms: AtomicU64,
    /// Batch size adaptations
    pub adaptations_count: AtomicU64,
}

impl BatchingStats {
    pub fn new() -> Self {
        Self {
            packets_processed: AtomicU64::new(0),
            batches_created: AtomicU64::new(0),
            avg_batch_size: AtomicU64::new(0),
            total_delay_ms: AtomicU64::new(0),
            adaptations_count: AtomicU64::new(0),
        }
    }

    /// Get average batch size
    pub fn average_batch_size(&self) -> f64 {
        let batches = self.batches_created.load(Ordering::Relaxed);
        if batches == 0 {
            return 0.0;
        }
        let packets = self.packets_processed.load(Ordering::Relaxed);
        packets as f64 / batches as f64
    }

    /// Get average delay per packet
    pub fn average_delay_per_packet_ms(&self) -> f64 {
        let packets = self.packets_processed.load(Ordering::Relaxed);
        if packets == 0 {
            return 0.0;
        }
        let total_delay = self.total_delay_ms.load(Ordering::Relaxed);
        total_delay as f64 / packets as f64
    }

    /// Get throughput (packets per second)
    pub fn throughput_pps(&self, duration: Duration) -> f64 {
        let packets = self.packets_processed.load(Ordering::Relaxed);
        packets as f64 / duration.as_secs_f64()
    }
}

impl Default for BatchingStats {
    fn default() -> Self {
        Self::new()
    }
}

impl AdaptiveBatchProcessor {
    /// Create new adaptive batch processor
    pub fn new(config: AdaptiveBatchingConfig) -> Result<Self> {
        if config.min_batch_size < 1 || config.max_batch_size > 128 {
            return Err(crate::MixnodeError::Config(
                "Batch size must be between 1 and 128".to_string(),
            ));
        }

        if config.min_batch_size > config.max_batch_size {
            return Err(crate::MixnodeError::Config(
                "Min batch size must be <= max batch size".to_string(),
            ));
        }

        Ok(Self {
            current_batch_size: AtomicUsize::new(config.initial_batch_size),
            config,
            network_load: Arc::new(Mutex::new(0.0)),
            packet_queue: Arc::new(Mutex::new(VecDeque::new())),
            stats: Arc::new(BatchingStats::new()),
            last_batch_time: Arc::new(Mutex::new(Instant::now())),
            load_window: Arc::new(Mutex::new(VecDeque::with_capacity(100))),
        })
    }

    /// Submit packet for batching
    pub async fn submit_packet(&self, packet: Vec<u8>) -> Result<()> {
        let mut queue = self.packet_queue.lock().await;
        queue.push_back(packet);
        Ok(())
    }

    /// Update network load estimate (0.0 = idle, 1.0 = saturated)
    pub async fn update_network_load(&self, load: f64) {
        let load_clamped = load.clamp(0.0, 1.0);

        // Update load with moving average
        let mut load_window = self.load_window.lock().await;
        load_window.push_back(load_clamped);
        if load_window.len() > 100 {
            load_window.pop_front();
        }

        // Calculate smoothed load
        let smoothed_load = load_window.iter().sum::<f64>() / load_window.len() as f64;
        *self.network_load.lock().await = smoothed_load;

        // Adapt batch size based on load
        self.adapt_batch_size(smoothed_load).await;
    }

    /// Adapt batch size based on current load and strategy
    async fn adapt_batch_size(&self, load: f64) {
        let new_size = match self.config.strategy {
            BatchingStrategy::Fixed => self.config.initial_batch_size,

            BatchingStrategy::LoadBased => {
                // Higher load = larger batches for efficiency
                let load_factor = load.powi(2); // Exponential scaling
                let range = (self.config.max_batch_size - self.config.min_batch_size) as f64;
                let size = self.config.min_batch_size as f64 + (range * load_factor);
                size.round() as usize
            }

            BatchingStrategy::MinLatency => {
                // Prefer smaller batches for lower latency
                if load < self.config.load_decrease_threshold {
                    self.config.min_batch_size
                } else {
                    (self.config.min_batch_size + self.config.max_batch_size) / 4
                }
            }

            BatchingStrategy::MaxThroughput => {
                // Prefer larger batches for higher throughput
                if load > self.config.load_increase_threshold {
                    self.config.max_batch_size
                } else {
                    (self.config.min_batch_size + self.config.max_batch_size * 3) / 4
                }
            }

            BatchingStrategy::Balanced => {
                // Adaptive: small batches at low load, large at high load
                if load < self.config.load_decrease_threshold {
                    // Low load: prioritize latency
                    self.config.min_batch_size
                } else if load > self.config.load_increase_threshold {
                    // High load: prioritize throughput
                    self.config.max_batch_size
                } else {
                    // Medium load: balanced approach
                    let mid = (self.config.min_batch_size + self.config.max_batch_size) / 2;
                    // Linear interpolation in medium range
                    let normalized = (load - self.config.load_decrease_threshold)
                        / (self.config.load_increase_threshold - self.config.load_decrease_threshold);
                    let range = (self.config.max_batch_size - mid) as f64;
                    (mid as f64 + range * normalized).round() as usize
                }
            }
        };

        let current = self.current_batch_size.load(Ordering::Relaxed);
        if new_size != current {
            self.current_batch_size.store(new_size, Ordering::Relaxed);
            self.stats.adaptations_count.fetch_add(1, Ordering::Relaxed);
            debug!("Batch size adapted: {} -> {} (load: {:.2})", current, new_size, load);
        }
    }

    /// Get next batch with adaptive sizing and minimum delay enforcement
    pub async fn next_batch(&self) -> Result<Vec<Vec<u8>>> {
        let target_size = self.current_batch_size.load(Ordering::Relaxed);

        // Enforce minimum delay between batches
        {
            let mut last_time = self.last_batch_time.lock().await;
            let elapsed = last_time.elapsed();
            let min_delay = Duration::from_millis(self.config.min_delay_ms);

            if elapsed < min_delay {
                let wait_time = min_delay - elapsed;
                drop(last_time); // Release lock before sleeping
                tokio::time::sleep(wait_time).await;
                let mut last_time = self.last_batch_time.lock().await;
                self.stats.total_delay_ms.fetch_add(wait_time.as_millis() as u64, Ordering::Relaxed);
                *last_time = Instant::now();
            } else {
                *last_time = Instant::now();
            }
        }

        // Collect batch
        let mut queue = self.packet_queue.lock().await;
        let actual_size = queue.len().min(target_size);

        if actual_size == 0 {
            return Ok(Vec::new());
        }

        let mut batch = Vec::with_capacity(actual_size);
        for _ in 0..actual_size {
            if let Some(packet) = queue.pop_front() {
                batch.push(packet);
            }
        }

        // Update statistics
        self.stats.packets_processed.fetch_add(batch.len() as u64, Ordering::Relaxed);
        self.stats.batches_created.fetch_add(1, Ordering::Relaxed);

        let batches = self.stats.batches_created.load(Ordering::Relaxed);
        let total_packets = self.stats.packets_processed.load(Ordering::Relaxed);
        let new_avg = total_packets / batches;
        self.stats.avg_batch_size.store(new_avg, Ordering::Relaxed);

        Ok(batch)
    }

    /// Get current batch size
    pub fn current_batch_size(&self) -> usize {
        self.current_batch_size.load(Ordering::Relaxed)
    }

    /// Get current network load estimate
    pub async fn current_network_load(&self) -> f64 {
        *self.network_load.lock().await
    }

    /// Get queue length
    pub async fn queue_length(&self) -> usize {
        self.packet_queue.lock().await.len()
    }

    /// Get statistics
    pub fn stats(&self) -> &BatchingStats {
        &self.stats
    }

    /// Calculate privacy-latency trade-off score (0.0-1.0, higher = better)
    ///
    /// Combines batch size efficiency with latency constraints.
    /// Score = (batch_efficiency * 0.6) + (latency_efficiency * 0.4)
    pub async fn privacy_latency_score(&self) -> f64 {
        let current_size = self.current_batch_size.load(Ordering::Relaxed) as f64;
        let max_size = self.config.max_batch_size as f64;

        // Batch efficiency: larger batches = better privacy
        let batch_efficiency = (current_size / max_size).min(1.0);

        // Latency efficiency: actual delay vs target
        let avg_delay = self.stats.average_delay_per_packet_ms();
        let target_delay = self.config.min_delay_ms as f64;
        let latency_efficiency = if avg_delay > 0.0 {
            (target_delay / avg_delay).min(1.0)
        } else {
            1.0
        };

        // Weighted combination (60% privacy, 40% latency)
        (batch_efficiency * 0.6) + (latency_efficiency * 0.4)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::time::sleep;

    #[tokio::test]
    async fn test_adaptive_batching_basic() {
        let config = AdaptiveBatchingConfig::default();
        let processor = AdaptiveBatchProcessor::new(config).unwrap();

        // Submit packets
        for i in 0..100 {
            let packet = format!("packet_{}", i).into_bytes();
            processor.submit_packet(packet).await.unwrap();
        }

        assert_eq!(processor.queue_length().await, 100);

        // Get batch
        let batch = processor.next_batch().await.unwrap();
        assert!(!batch.is_empty());
        assert!(batch.len() <= 128);
    }

    #[tokio::test]
    async fn test_load_based_adaptation() {
        let mut config = AdaptiveBatchingConfig::default();
        config.strategy = BatchingStrategy::LoadBased;
        config.min_batch_size = 10;
        config.max_batch_size = 100;

        let processor = AdaptiveBatchProcessor::new(config).unwrap();

        // Low load: should use small batches
        processor.update_network_load(0.1).await;
        sleep(Duration::from_millis(10)).await;
        let low_load_size = processor.current_batch_size();

        // High load: should use large batches
        processor.update_network_load(0.9).await;
        sleep(Duration::from_millis(10)).await;
        let high_load_size = processor.current_batch_size();

        assert!(high_load_size > low_load_size);
        println!("Low load size: {}, High load size: {}", low_load_size, high_load_size);
    }

    #[tokio::test]
    async fn test_min_delay_enforcement() {
        let mut config = AdaptiveBatchingConfig::default();
        config.min_delay_ms = 50; // 50ms minimum delay

        let processor = AdaptiveBatchProcessor::new(config).unwrap();

        // Submit packets
        for _ in 0..10 {
            processor.submit_packet(b"test".to_vec()).await.unwrap();
        }

        let start = Instant::now();

        // Get two batches
        let _batch1 = processor.next_batch().await.unwrap();
        let _batch2 = processor.next_batch().await.unwrap();

        let elapsed = start.elapsed();

        // Should have at least 50ms delay between batches
        assert!(elapsed >= Duration::from_millis(50));
    }

    #[tokio::test]
    async fn test_strategy_differences() {
        let strategies = vec![
            BatchingStrategy::MinLatency,
            BatchingStrategy::MaxThroughput,
            BatchingStrategy::Balanced,
        ];

        for strategy in strategies {
            let mut config = AdaptiveBatchingConfig::default();
            config.strategy = strategy;
            config.min_batch_size = 1;
            config.max_batch_size = 100;

            let processor = AdaptiveBatchProcessor::new(config).unwrap();
            processor.update_network_load(0.5).await;

            let size = processor.current_batch_size();
            println!("Strategy {:?}: batch size = {}", strategy, size);

            assert!(size >= 1 && size <= 100);
        }
    }

    #[tokio::test]
    async fn test_privacy_latency_score() {
        let config = AdaptiveBatchingConfig::default();
        let processor = AdaptiveBatchProcessor::new(config).unwrap();

        // Submit and process some packets
        for _ in 0..50 {
            processor.submit_packet(b"test".to_vec()).await.unwrap();
        }

        let _batch = processor.next_batch().await.unwrap();

        let score = processor.privacy_latency_score().await;
        assert!(score >= 0.0 && score <= 1.0);
        println!("Privacy-latency score: {:.2}", score);
    }
}
