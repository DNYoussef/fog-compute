//! Timing attack defense mechanisms
//!
//! Implements correlation analysis resistance, inter-packet timing randomization,
//! burst pattern masking, and statistical privacy metrics for timing attack defense.

use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, Instant};
use rand::prelude::*;
use tokio::sync::Mutex;

use crate::Result;

/// Timing defense configuration
#[derive(Debug, Clone)]
pub struct TimingDefenseConfig {
    /// Enable timing defense
    pub enabled: bool,
    /// Timing randomization percentage (0.0-1.0)
    pub randomization_pct: f64,
    /// Correlation window size (number of packets)
    pub correlation_window_size: usize,
    /// Burst detection threshold (packets/sec)
    pub burst_threshold: f64,
    /// Maximum acceptable correlation coefficient
    pub max_correlation: f64,
}

impl Default for TimingDefenseConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            randomization_pct: 0.3, // ±30% randomization
            correlation_window_size: 100,
            burst_threshold: 100.0, // 100 packets/sec
            max_correlation: 0.3, // Maximum 0.3 correlation
        }
    }
}

/// Packet timing information
#[derive(Debug, Clone)]
pub struct PacketTiming {
    /// Packet timestamp
    pub timestamp: Instant,
    /// Packet size (bytes)
    pub size: usize,
    /// Original delay (before randomization)
    pub original_delay_ms: f64,
    /// Actual delay (after randomization)
    pub actual_delay_ms: f64,
}

/// Timing attack defense manager
pub struct TimingDefenseManager {
    config: TimingDefenseConfig,
    timing_history: Arc<Mutex<VecDeque<PacketTiming>>>,
    rng: Arc<Mutex<ThreadRng>>,
}

impl TimingDefenseManager {
    /// Create new timing defense manager
    pub fn new(config: TimingDefenseConfig) -> Self {
        Self {
            timing_history: Arc::new(Mutex::new(VecDeque::with_capacity(
                config.correlation_window_size,
            ))),
            config,
            rng: Arc::new(Mutex::new(thread_rng())),
        }
    }

    /// Apply timing randomization to a delay
    ///
    /// Adds random jitter to prevent correlation attacks.
    /// Randomization is applied as: delay * (1 ± random * randomization_pct)
    pub async fn randomize_delay(&self, delay: Duration) -> Duration {
        if !self.config.enabled {
            return delay;
        }

        let mut rng = self.rng.lock().await;
        let delay_ms = delay.as_secs_f64() * 1000.0;

        // Add randomization: ±randomization_pct
        let randomization = (rng.gen::<f64>() - 0.5) * 2.0 * self.config.randomization_pct;
        let randomized_ms = delay_ms * (1.0 + randomization);

        // Ensure positive delay
        Duration::from_millis(randomized_ms.max(0.0) as u64)
    }

    /// Record packet timing for correlation analysis
    pub async fn record_packet_timing(
        &self,
        size: usize,
        original_delay: Duration,
        actual_delay: Duration,
    ) {
        let timing = PacketTiming {
            timestamp: Instant::now(),
            size,
            original_delay_ms: original_delay.as_secs_f64() * 1000.0,
            actual_delay_ms: actual_delay.as_secs_f64() * 1000.0,
        };

        let mut history = self.timing_history.lock().await;
        history.push_back(timing);

        // Maintain window size
        while history.len() > self.config.correlation_window_size {
            history.pop_front();
        }
    }

    /// Calculate correlation coefficient between original and actual delays
    ///
    /// Uses Pearson correlation coefficient. Returns value in [-1, 1].
    /// Lower absolute value indicates better timing attack resistance.
    pub async fn calculate_correlation(&self) -> f64 {
        let history = self.timing_history.lock().await;

        if history.len() < 2 {
            return 0.0;
        }

        let n = history.len() as f64;
        let original_delays: Vec<f64> = history.iter().map(|t| t.original_delay_ms).collect();
        let actual_delays: Vec<f64> = history.iter().map(|t| t.actual_delay_ms).collect();

        // Calculate means
        let mean_original = original_delays.iter().sum::<f64>() / n;
        let mean_actual = actual_delays.iter().sum::<f64>() / n;

        // Calculate correlation coefficient
        let mut numerator = 0.0;
        let mut sum_sq_original = 0.0;
        let mut sum_sq_actual = 0.0;

        for i in 0..history.len() {
            let diff_original = original_delays[i] - mean_original;
            let diff_actual = actual_delays[i] - mean_actual;

            numerator += diff_original * diff_actual;
            sum_sq_original += diff_original * diff_original;
            sum_sq_actual += diff_actual * diff_actual;
        }

        let denominator = (sum_sq_original * sum_sq_actual).sqrt();

        if denominator == 0.0 {
            return 0.0;
        }

        numerator / denominator
    }

    /// Detect burst patterns in timing
    ///
    /// Returns true if a burst is detected (packets arriving faster than threshold).
    pub async fn detect_burst(&self) -> bool {
        let history = self.timing_history.lock().await;

        if history.len() < 10 {
            return false; // Not enough data
        }

        // Check recent packets (last 10)
        let recent_count = 10usize.min(history.len());
        let recent_packets: Vec<&PacketTiming> =
            history.iter().rev().take(recent_count).collect();

        if recent_packets.len() < 2 {
            return false;
        }

        // Calculate time span
        let oldest = recent_packets.last().unwrap().timestamp;
        let newest = recent_packets.first().unwrap().timestamp;
        let duration = newest.duration_since(oldest).as_secs_f64();

        if duration == 0.0 {
            return true; // All packets at same time = burst
        }

        // Calculate rate
        let rate = recent_count as f64 / duration;

        rate > self.config.burst_threshold
    }

    /// Apply burst pattern masking
    ///
    /// If a burst is detected, returns additional delay to mask the pattern.
    pub async fn mask_burst_pattern(&self) -> Option<Duration> {
        if !self.detect_burst().await {
            return None;
        }

        // Add random delay between 10-100ms to break up burst
        let mut rng = self.rng.lock().await;
        let delay_ms = 10.0 + rng.gen::<f64>() * 90.0;

        Some(Duration::from_millis(delay_ms as u64))
    }

    /// Calculate inter-packet timing variance
    ///
    /// Higher variance indicates better resistance to timing attacks.
    pub async fn calculate_timing_variance(&self) -> f64 {
        let history = self.timing_history.lock().await;

        if history.len() < 2 {
            return 0.0;
        }

        // Calculate inter-packet intervals
        let mut intervals = Vec::new();
        for i in 1..history.len() {
            let interval = history[i]
                .timestamp
                .duration_since(history[i - 1].timestamp)
                .as_secs_f64()
                * 1000.0;
            intervals.push(interval);
        }

        if intervals.is_empty() {
            return 0.0;
        }

        // Calculate variance
        let mean = intervals.iter().sum::<f64>() / intervals.len() as f64;
        let variance = intervals
            .iter()
            .map(|&x| (x - mean).powi(2))
            .sum::<f64>()
            / intervals.len() as f64;

        variance
    }

    /// Calculate entropy of timing distribution
    ///
    /// Higher entropy indicates more unpredictable timing.
    pub async fn calculate_timing_entropy(&self, num_bins: usize) -> f64 {
        let history = self.timing_history.lock().await;

        if history.len() < 10 {
            return 0.0;
        }

        // Extract actual delays
        let delays: Vec<f64> = history.iter().map(|t| t.actual_delay_ms).collect();

        // Find min/max for binning
        let min_delay = delays.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_delay = delays.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let bin_width = (max_delay - min_delay) / num_bins as f64;

        if bin_width == 0.0 {
            return 0.0; // All delays the same
        }

        // Count delays in each bin
        let mut bin_counts = vec![0usize; num_bins];
        for &delay in &delays {
            let bin_idx = ((delay - min_delay) / bin_width).floor() as usize;
            let bin_idx = bin_idx.min(num_bins - 1);
            bin_counts[bin_idx] += 1;
        }

        // Calculate entropy: H = -Σ(p_i * log2(p_i))
        let total = delays.len() as f64;
        let entropy = bin_counts
            .iter()
            .filter(|&&count| count > 0)
            .map(|&count| {
                let p = count as f64 / total;
                -p * p.log2()
            })
            .sum();

        entropy
    }

    /// Get timing attack resistance score (0.0-1.0, higher = better)
    ///
    /// Combines multiple metrics:
    /// - Low correlation (30%)
    /// - High timing variance (30%)
    /// - High entropy (40%)
    pub async fn timing_attack_resistance_score(&self) -> f64 {
        let correlation = self.calculate_correlation().await.abs();
        let variance = self.calculate_timing_variance().await;
        let entropy = self.calculate_timing_entropy(20).await;

        // Normalize metrics to [0, 1]
        let correlation_score = (1.0 - correlation).clamp(0.0, 1.0);

        // Variance score (normalize to typical range 0-10000ms²)
        let variance_score = (variance / 10000.0).min(1.0);

        // Entropy score (normalize to max entropy for 20 bins ≈ 4.32)
        let entropy_score = (entropy / 4.32).min(1.0);

        // Weighted combination
        (correlation_score * 0.3) + (variance_score * 0.3) + (entropy_score * 0.4)
    }

    /// Check if timing defense is effective (correlation below threshold)
    pub async fn is_defense_effective(&self) -> bool {
        let correlation = self.calculate_correlation().await.abs();
        correlation < self.config.max_correlation
    }

    /// Get timing statistics
    pub async fn get_timing_stats(&self) -> TimingStats {
        let correlation = self.calculate_correlation().await;
        let variance = self.calculate_timing_variance().await;
        let entropy = self.calculate_timing_entropy(20).await;
        let burst_detected = self.detect_burst().await;
        let resistance_score = self.timing_attack_resistance_score().await;

        TimingStats {
            correlation,
            variance,
            entropy,
            burst_detected,
            resistance_score,
        }
    }

    /// Reset timing history
    pub async fn reset_history(&self) {
        self.timing_history.lock().await.clear();
    }
}

/// Timing statistics
#[derive(Debug, Clone)]
pub struct TimingStats {
    /// Correlation coefficient between original and actual delays
    pub correlation: f64,
    /// Timing variance (ms²)
    pub variance: f64,
    /// Timing entropy
    pub entropy: f64,
    /// Whether burst pattern is detected
    pub burst_detected: bool,
    /// Overall timing attack resistance score (0-1)
    pub resistance_score: f64,
}

impl TimingStats {
    pub fn print(&self) {
        println!("🛡️  Timing Attack Defense Statistics:");
        println!("  Correlation:      {:.4}", self.correlation);
        println!("  Variance:         {:.2} ms²", self.variance);
        println!("  Entropy:          {:.4}", self.entropy);
        println!("  Burst detected:   {}", self.burst_detected);
        println!("  Resistance score: {:.2}%", self.resistance_score * 100.0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::time::sleep;

    #[tokio::test]
    async fn test_timing_randomization() {
        let config = TimingDefenseConfig::default();
        let manager = TimingDefenseManager::new(config);

        let base_delay = Duration::from_millis(100);

        // Generate multiple randomized delays
        let mut delays = Vec::new();
        for _ in 0..100 {
            let randomized = manager.randomize_delay(base_delay).await;
            delays.push(randomized.as_millis() as f64);
        }

        // Check that delays vary
        let mean = delays.iter().sum::<f64>() / delays.len() as f64;
        let variance = delays
            .iter()
            .map(|&x| (x - mean).powi(2))
            .sum::<f64>()
            / delays.len() as f64;

        println!("Mean: {:.2}ms, Variance: {:.2}ms²", mean, variance);
        assert!(variance > 0.0); // Should have some variance
    }

    #[tokio::test]
    async fn test_correlation_calculation() {
        let config = TimingDefenseConfig::default();
        let manager = TimingDefenseManager::new(config);

        // Record some packets with randomization
        for _ in 0..50 {
            let original = Duration::from_millis(100);
            let actual = manager.randomize_delay(original).await;
            manager
                .record_packet_timing(1000, original, actual)
                .await;
        }

        let correlation = manager.calculate_correlation().await;
        println!("Correlation: {:.4}", correlation);

        // With good randomization, correlation should be low
        assert!(correlation.abs() < 0.8); // Allow some correlation
    }

    #[tokio::test]
    async fn test_burst_detection() {
        let config = TimingDefenseConfig {
            burst_threshold: 50.0, // 50 packets/sec
            ..Default::default()
        };
        let manager = TimingDefenseManager::new(config);

        // Simulate burst (10 packets in quick succession)
        for _ in 0..10 {
            manager
                .record_packet_timing(
                    1000,
                    Duration::from_millis(10),
                    Duration::from_millis(10),
                )
                .await;
            sleep(Duration::from_millis(5)).await; // 200 pkt/s = burst
        }

        let is_burst = manager.detect_burst().await;
        println!("Burst detected: {}", is_burst);
        assert!(is_burst);
    }

    #[tokio::test]
    async fn test_entropy_calculation() {
        let config = TimingDefenseConfig::default();
        let manager = TimingDefenseManager::new(config);

        // Record packets with varied delays
        for i in 0..100 {
            let delay = Duration::from_millis(50 + (i % 20) * 10);
            manager
                .record_packet_timing(1000, delay, delay)
                .await;
        }

        let entropy = manager.calculate_timing_entropy(20).await;
        println!("Entropy: {:.4}", entropy);
        assert!(entropy > 0.0);
    }

    #[tokio::test]
    async fn test_resistance_score() {
        let config = TimingDefenseConfig::default();
        let manager = TimingDefenseManager::new(config);

        // Record packets with randomization
        for _ in 0..100 {
            let original = Duration::from_millis(100);
            let actual = manager.randomize_delay(original).await;
            manager
                .record_packet_timing(1000, original, actual)
                .await;
            sleep(Duration::from_millis(10)).await;
        }

        let score = manager.timing_attack_resistance_score().await;
        let stats = manager.get_timing_stats().await;

        stats.print();
        println!("Resistance score: {:.2}%", score * 100.0);

        assert!(score > 0.0 && score <= 1.0);
    }
}
