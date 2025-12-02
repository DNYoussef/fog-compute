//! Cover traffic generation for traffic analysis resistance
//!
//! Implements configurable cover traffic patterns to maintain constant rate
//! and prevent traffic analysis attacks. Features advanced traffic shaping,
//! indistinguishability testing, and adaptive bandwidth management.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use rand::prelude::*;
use rand::rngs::StdRng;
use rand::SeedableRng;
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;
use tracing::debug;

/// Cover traffic generation mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CoverTrafficMode {
    /// Constant rate (always send at target rate)
    ConstantRate,
    /// Adaptive (adjust based on real traffic)
    Adaptive,
    /// Burst (send in bursts to match real traffic patterns)
    Burst,
}

/// Cover traffic configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoverTrafficConfig {
    /// Enable cover traffic
    pub enabled: bool,
    /// Cover traffic mode
    pub mode: CoverTrafficMode,
    /// Target cover traffic rate (packets per second)
    pub target_rate: f64,
    /// Cover packet size (bytes)
    pub packet_size: usize,
    /// Size variability (±percentage, 0.0-1.0)
    pub size_variability: f64,
    /// Minimum real traffic rate before triggering cover (packets/sec)
    pub min_real_traffic_rate: f64,
    /// Maximum bandwidth overhead as percentage (0.0-1.0, e.g., 0.05 = 5%)
    pub max_bandwidth_overhead: f64,
    /// Indistinguishability threshold (0.0-1.0, higher = more similar to real traffic)
    pub indistinguishability_threshold: f64,
}

impl Default for CoverTrafficConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            mode: CoverTrafficMode::Adaptive,
            target_rate: 10.0,
            packet_size: 1024,
            size_variability: 0.2, // ±20% size variation
            min_real_traffic_rate: 5.0,
            max_bandwidth_overhead: 0.05, // 5% maximum overhead
            indistinguishability_threshold: 0.95, // 95% similarity to real traffic
        }
    }
}

/// Real traffic statistics for indistinguishability comparison
#[derive(Debug, Clone)]
pub struct TrafficStatistics {
    /// Average packet size
    pub avg_packet_size: f64,
    /// Packet size standard deviation
    pub size_std_dev: f64,
    /// Average inter-packet interval (ms)
    pub avg_interval_ms: f64,
    /// Interval standard deviation (ms)
    pub interval_std_dev_ms: f64,
    /// Packet count
    pub packet_count: usize,
}

impl TrafficStatistics {
    pub fn new() -> Self {
        Self {
            avg_packet_size: 0.0,
            size_std_dev: 0.0,
            avg_interval_ms: 0.0,
            interval_std_dev_ms: 0.0,
            packet_count: 0,
        }
    }

    /// Calculate similarity score between two traffic statistics (0.0-1.0)
    pub fn similarity_score(&self, other: &TrafficStatistics) -> f64 {
        if self.packet_count == 0 || other.packet_count == 0 {
            return 0.0;
        }

        // Size similarity (using coefficient of variation)
        let size_sim = if self.avg_packet_size > 0.0 && other.avg_packet_size > 0.0 {
            let cv_self = self.size_std_dev / self.avg_packet_size;
            let cv_other = other.size_std_dev / other.avg_packet_size;
            1.0 - ((cv_self - cv_other).abs() / (cv_self + cv_other).max(0.001))
        } else {
            0.0
        };

        // Interval similarity
        let interval_sim = if self.avg_interval_ms > 0.0 && other.avg_interval_ms > 0.0 {
            let cv_self = self.interval_std_dev_ms / self.avg_interval_ms;
            let cv_other = other.interval_std_dev_ms / other.avg_interval_ms;
            1.0 - ((cv_self - cv_other).abs() / (cv_self + cv_other).max(0.001))
        } else {
            0.0
        };

        // Weighted average (size 60%, interval 40%)
        (size_sim * 0.6 + interval_sim * 0.4).clamp(0.0, 1.0)
    }
}

impl Default for TrafficStatistics {
    fn default() -> Self {
        Self::new()
    }
}

/// Advanced cover traffic generator with traffic shaping and indistinguishability
pub struct AdvancedCoverTrafficGenerator {
    config: CoverTrafficConfig,
    packets_sent: AtomicU64,
    bytes_sent: AtomicU64,
    real_traffic_stats: Arc<Mutex<TrafficStatistics>>,
    cover_traffic_stats: Arc<Mutex<TrafficStatistics>>,
    last_packet_time: Arc<Mutex<Option<Instant>>>,
    rng: Arc<Mutex<StdRng>>,
}

impl AdvancedCoverTrafficGenerator {
    /// Create new cover traffic generator
    pub fn new(config: CoverTrafficConfig) -> Self {
        Self {
            config,
            packets_sent: AtomicU64::new(0),
            bytes_sent: AtomicU64::new(0),
            real_traffic_stats: Arc::new(Mutex::new(TrafficStatistics::new())),
            cover_traffic_stats: Arc::new(Mutex::new(TrafficStatistics::new())),
            last_packet_time: Arc::new(Mutex::new(None)),
            rng: Arc::new(Mutex::new(StdRng::from_entropy())),
        }
    }

    /// Update real traffic statistics for indistinguishability comparison
    pub async fn update_real_traffic_stats(&self, packet_size: usize) {
        let mut stats = self.real_traffic_stats.lock().await;
        let mut last_time = self.last_packet_time.lock().await;

        // Update packet count
        stats.packet_count += 1;

        // Update size statistics (running average)
        let n = stats.packet_count as f64;
        let old_avg = stats.avg_packet_size;
        stats.avg_packet_size = old_avg + (packet_size as f64 - old_avg) / n;

        // Update size standard deviation (Welford's online algorithm)
        if stats.packet_count > 1 {
            let size_dev = packet_size as f64 - stats.avg_packet_size;
            stats.size_std_dev = (stats.size_std_dev.powi(2) * (n - 2.0)
                + size_dev * (packet_size as f64 - old_avg))
                .sqrt()
                / (n - 1.0).sqrt();
        }

        // Update interval statistics
        if let Some(last) = *last_time {
            let interval_ms = last.elapsed().as_secs_f64() * 1000.0;
            let old_interval_avg = stats.avg_interval_ms;
            stats.avg_interval_ms = old_interval_avg + (interval_ms - old_interval_avg) / (n - 1.0);

            if stats.packet_count > 2 {
                let interval_dev = interval_ms - stats.avg_interval_ms;
                stats.interval_std_dev_ms =
                    (stats.interval_std_dev_ms.powi(2) * (n - 3.0)
                        + interval_dev * (interval_ms - old_interval_avg))
                        .sqrt()
                        / (n - 2.0).sqrt();
            }
        }

        *last_time = Some(Instant::now());
    }

    /// Generate cover packet with indistinguishability from real traffic
    pub async fn generate_cover_packet(&self) -> Option<Vec<u8>> {
        if !self.config.enabled {
            return None;
        }

        // Check bandwidth overhead limit
        let overhead = self.calculate_bandwidth_overhead().await;
        if overhead > self.config.max_bandwidth_overhead {
            debug!(
                "Skipping cover packet: overhead {:.2}% exceeds limit {:.2}%",
                overhead * 100.0,
                self.config.max_bandwidth_overhead * 100.0
            );
            return None;
        }

        // Generate packet with size variability
        let packet_size = self.generate_realistic_packet_size().await;
        let packet = vec![0u8; packet_size]; // Dummy content

        // Update cover traffic statistics
        self.update_cover_stats(packet_size).await;

        // Update counters
        self.packets_sent.fetch_add(1, Ordering::Relaxed);
        self.bytes_sent.fetch_add(packet_size as u64, Ordering::Relaxed);

        Some(packet)
    }

    /// Generate realistic packet size based on real traffic patterns
    async fn generate_realistic_packet_size(&self) -> usize {
        let real_stats = self.real_traffic_stats.lock().await;
        let mut rng = self.rng.lock().await;

        let base_size = if real_stats.avg_packet_size > 0.0 {
            // Match real traffic average
            real_stats.avg_packet_size
        } else {
            // Use configured size if no real traffic yet
            self.config.packet_size as f64
        };

        // Add variability based on configuration
        let variability_range = base_size * self.config.size_variability;
        let offset = (rng.gen::<f64>() - 0.5) * 2.0 * variability_range;
        let final_size = (base_size + offset).max(64.0); // Minimum 64 bytes

        final_size as usize
    }

    /// Update cover traffic statistics
    async fn update_cover_stats(&self, packet_size: usize) {
        let mut stats = self.cover_traffic_stats.lock().await;

        stats.packet_count += 1;
        let n = stats.packet_count as f64;

        // Update size statistics
        let old_avg = stats.avg_packet_size;
        stats.avg_packet_size = old_avg + (packet_size as f64 - old_avg) / n;

        if stats.packet_count > 1 {
            let size_dev = packet_size as f64 - stats.avg_packet_size;
            stats.size_std_dev = (stats.size_std_dev.powi(2) * (n - 2.0)
                + size_dev * (packet_size as f64 - old_avg))
                .sqrt()
                / (n - 1.0).sqrt();
        }
    }

    /// Calculate current bandwidth overhead (cover/real ratio)
    async fn calculate_bandwidth_overhead(&self) -> f64 {
        let cover_bytes = self.bytes_sent.load(Ordering::Relaxed) as f64;
        let real_stats = self.real_traffic_stats.lock().await;

        if real_stats.packet_count == 0 {
            return 0.0; // No real traffic yet
        }

        let real_bytes = real_stats.avg_packet_size * real_stats.packet_count as f64;
        if real_bytes == 0.0 {
            return 0.0;
        }

        cover_bytes / real_bytes
    }

    /// Get interval between cover packets based on mode
    pub async fn cover_interval(&self) -> Duration {
        match self.config.mode {
            CoverTrafficMode::ConstantRate => {
                if self.config.target_rate > 0.0 {
                    Duration::from_secs_f64(1.0 / self.config.target_rate)
                } else {
                    Duration::from_secs(1)
                }
            }

            CoverTrafficMode::Adaptive => {
                // Match real traffic rate
                let real_stats = self.real_traffic_stats.lock().await;
                if real_stats.avg_interval_ms > 0.0 {
                    Duration::from_millis(real_stats.avg_interval_ms as u64)
                } else {
                    Duration::from_secs_f64(1.0 / self.config.target_rate)
                }
            }

            CoverTrafficMode::Burst => {
                // Variable intervals with bursts
                let mut rng = self.rng.lock().await;
                let base_interval = 1.0 / self.config.target_rate;
                let variability = base_interval * 0.5; // ±50% variability
                let offset = (rng.gen::<f64>() - 0.5) * 2.0 * variability;
                Duration::from_secs_f64((base_interval + offset).max(0.001))
            }
        }
    }

    /// Test indistinguishability from real traffic
    pub async fn test_indistinguishability(&self) -> f64 {
        let real_stats = self.real_traffic_stats.lock().await;
        let cover_stats = self.cover_traffic_stats.lock().await;

        real_stats.similarity_score(&cover_stats)
    }

    /// Check if indistinguishability threshold is met
    pub async fn is_indistinguishable(&self) -> bool {
        let similarity = self.test_indistinguishability().await;
        similarity >= self.config.indistinguishability_threshold
    }

    /// Get statistics
    pub fn packets_sent(&self) -> u64 {
        self.packets_sent.load(Ordering::Relaxed)
    }

    pub fn bytes_sent(&self) -> u64 {
        self.bytes_sent.load(Ordering::Relaxed)
    }

    pub async fn get_real_traffic_stats(&self) -> TrafficStatistics {
        self.real_traffic_stats.lock().await.clone()
    }

    pub async fn get_cover_traffic_stats(&self) -> TrafficStatistics {
        self.cover_traffic_stats.lock().await.clone()
    }

    /// Update configuration
    pub fn update_config(&mut self, config: CoverTrafficConfig) {
        self.config = config;
    }

    /// Reset statistics
    pub async fn reset_stats(&self) {
        *self.real_traffic_stats.lock().await = TrafficStatistics::new();
        *self.cover_traffic_stats.lock().await = TrafficStatistics::new();
        self.packets_sent.store(0, Ordering::Relaxed);
        self.bytes_sent.store(0, Ordering::Relaxed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cover_traffic_basic() {
        let config = CoverTrafficConfig::default();
        let mut generator = AdvancedCoverTrafficGenerator::new(config);

        // Disabled by default
        assert!(generator.generate_cover_packet().is_none());

        // Enable and generate
        generator.update_config(CoverTrafficConfig {
            enabled: true,
            ..Default::default()
        });

        let packet = generator.generate_cover_packet();
        assert!(packet.is_some());
        assert_eq!(packet.unwrap().len(), 1024);
        assert_eq!(generator.packets_sent(), 1);
    }

    #[test]
    fn test_cover_interval() {
        let config = CoverTrafficConfig {
            target_rate: 10.0,
            ..Default::default()
        };
        let generator = AdvancedCoverTrafficGenerator::new(config);

        let interval = generator.cover_interval();
        assert_eq!(interval.as_millis(), 100); // 1/10 second
    }
}
