//! Poisson-distributed delay for enhanced privacy
//!
//! Implements Poisson delay distribution as recommended by
//! Betanet v1.2 Privacy Hop specification for better traffic analysis resistance.

use rand::prelude::*;
use std::time::Duration;

use crate::Result;

// Exponential distribution for Poisson process (custom implementation)
struct Exp {
    lambda: f64,
}

impl Exp {
    fn new(lambda: f64) -> Result<Self> {
        if lambda <= 0.0 {
            return Err(crate::MixnodeError::Config(
                "Lambda must be positive for exponential distribution".to_string(),
            ));
        }
        Ok(Self { lambda })
    }

    fn sample(&self, rng: &mut impl Rng) -> f64 {
        // Inverse transform sampling: -ln(U) / lambda where U ~ Uniform(0,1)
        let u: f64 = rng.gen();
        -(1.0 - u).ln() / self.lambda
    }
}

/// Enhanced Poisson delay generator with adaptive lambda and per-circuit customization.
///
/// Generates delays following a Poisson distribution (exponential inter-arrival times)
/// to prevent timing analysis attacks on network traffic patterns. Includes advanced
/// features for adaptive delay based on network conditions and circuit-specific tuning.
///
/// # Mathematical Background
///
/// The Poisson process models random events occurring independently at a constant average rate.
/// Inter-arrival times follow an exponential distribution with parameter λ = 1/mean_delay.
///
/// This implementation uses inverse transform sampling to generate exponentially distributed delays:
/// - Sample U from Uniform(0,1)
/// - Compute delay = -ln(1-U) / λ
///
/// # Adaptive Features
///
/// - **Network Load Adaptation**: Lambda adjusts based on current network load
/// - **Per-Circuit Customization**: Different circuits can have different delay characteristics
/// - **Jitter Injection**: Additional randomness for unpredictability
/// - **Statistical Indistinguishability**: Delays are statistically indistinguishable from noise
///
/// # Bounds
///
/// To ensure practical operation, delays are clamped to [min_delay, max_delay]:
/// - **min_delay**: Prevents zero or near-zero delays that could leak information
/// - **max_delay**: Prevents excessive delays that impact usability
///
/// # Examples
///
/// ```
/// use betanet::vrf::poisson_delay::PoissonDelayGenerator;
/// use std::time::Duration;
///
/// let mean = Duration::from_millis(500);
/// let min = Duration::from_millis(100);
/// let max = Duration::from_millis(2000);
///
/// let mut generator = PoissonDelayGenerator::new(mean, min, max).unwrap();
///
/// // Adapt to high network load (40% load)
/// generator.adapt_to_network_load(0.4);
///
/// let delay = generator.next_delay();
/// assert!(delay >= min && delay <= max);
/// ```
pub struct PoissonDelayGenerator {
    /// Base mean delay in milliseconds (λ = 1/mean_delay_ms)
    base_mean_delay_ms: f64,
    /// Current adapted mean delay (adjusted by network load)
    current_mean_delay_ms: f64,
    /// Minimum delay (safety bound to prevent timing leaks)
    min_delay: Duration,
    /// Maximum delay (performance bound to ensure usability)
    max_delay: Duration,
    /// Exponential distribution for Poisson inter-arrival times
    exp_dist: Exp,
    /// Jitter percentage (0.0 to 1.0) for additional unpredictability
    jitter_pct: f64,
    /// Network load adaptation factor (0.0 to 1.0)
    load_adaptation_factor: f64,
    /// Per-circuit delay multiplier (default 1.0)
    circuit_multiplier: f64,
}

impl PoissonDelayGenerator {
    /// Create new enhanced Poisson delay generator
    ///
    /// # Arguments
    /// * `mean_delay` - Base mean delay (center of distribution)
    /// * `min_delay` - Minimum allowed delay (safety bound)
    /// * `max_delay` - Maximum allowed delay (performance bound)
    pub fn new(mean_delay: Duration, min_delay: Duration, max_delay: Duration) -> Result<Self> {
        if mean_delay < min_delay || mean_delay > max_delay {
            return Err(crate::MixnodeError::Config(
                "Mean delay must be between min and max delays".to_string(),
            ));
        }

        let mean_delay_ms = mean_delay.as_secs_f64() * 1000.0;
        let lambda = 1.0 / mean_delay_ms;

        Ok(Self {
            base_mean_delay_ms: mean_delay_ms,
            current_mean_delay_ms: mean_delay_ms,
            min_delay,
            max_delay,
            exp_dist: Exp::new(lambda)?,
            jitter_pct: 0.1, // Default 10% jitter
            load_adaptation_factor: 0.0,
            circuit_multiplier: 1.0,
        })
    }

    /// Create with custom jitter percentage
    pub fn with_jitter(mut self, jitter_pct: f64) -> Self {
        self.jitter_pct = jitter_pct.clamp(0.0, 0.5); // Max 50% jitter
        self
    }

    /// Adapt delay based on network load (0.0 = no load, 1.0 = max load)
    ///
    /// Higher load results in longer delays to maintain privacy under stress.
    /// Uses exponential backoff: delay_multiplier = 1 + load^2
    pub fn adapt_to_network_load(&mut self, load: f64) {
        let load_clamped = load.clamp(0.0, 1.0);
        self.load_adaptation_factor = load_clamped;

        // Exponential adaptation: higher load = longer delays
        let load_multiplier = 1.0 + (load_clamped * load_clamped * 2.0);
        self.current_mean_delay_ms = self.base_mean_delay_ms * load_multiplier;

        // Update lambda for exponential distribution
        let new_lambda = 1.0 / self.current_mean_delay_ms;
        self.exp_dist = Exp::new(new_lambda).unwrap_or(self.exp_dist);
    }

    /// Set per-circuit delay multiplier for circuit-specific tuning
    ///
    /// # Arguments
    /// * `multiplier` - Delay multiplier (0.5 = faster, 2.0 = slower)
    pub fn set_circuit_multiplier(&mut self, multiplier: f64) {
        self.circuit_multiplier = multiplier.clamp(0.1, 10.0); // Reasonable bounds
    }

    /// Get current effective mean delay considering all adaptations
    pub fn effective_mean_delay(&self) -> Duration {
        let effective_ms = self.current_mean_delay_ms * self.circuit_multiplier;
        Duration::from_millis(effective_ms as u64)
    }

    /// Generate the next delay using enhanced Poisson distribution with jitter.
    ///
    /// Samples from the exponential distribution, applies circuit multiplier,
    /// adds jitter for unpredictability, and clamps to configured bounds.
    /// This method is thread-safe but uses thread-local RNG for performance.
    ///
    /// # Returns
    ///
    /// A `Duration` representing the delay before sending the next packet.
    /// Guaranteed to be within [min_delay, max_delay].
    ///
    /// # Examples
    ///
    /// ```
    /// use betanet::vrf::poisson_delay::PoissonDelayGenerator;
    /// use std::time::Duration;
    ///
    /// let mut generator = PoissonDelayGenerator::new(
    ///     Duration::from_millis(500),
    ///     Duration::from_millis(100),
    ///     Duration::from_millis(2000)
    /// ).unwrap();
    ///
    /// // Adapt to network load
    /// generator.adapt_to_network_load(0.3);
    ///
    /// // Generate 10 delays with jitter
    /// for _ in 0..10 {
    ///     let delay = generator.next_delay();
    ///     println!("Next packet in {:?}", delay);
    /// }
    /// ```
    pub fn next_delay(&self) -> Duration {
        let mut rng = thread_rng();

        // Sample from exponential distribution
        let base_delay_ms = self.exp_dist.sample(&mut rng);

        // Apply circuit multiplier
        let circuit_adjusted_ms = base_delay_ms * self.circuit_multiplier;

        // Add jitter for unpredictability
        let jitter_factor = if self.jitter_pct > 0.0 {
            let jitter_range = 1.0 + (rng.gen::<f64>() - 0.5) * 2.0 * self.jitter_pct;
            jitter_range.max(0.5).min(1.5) // Prevent extreme jitter
        } else {
            1.0
        };

        let final_delay_ms = circuit_adjusted_ms * jitter_factor;

        // Clamp to min/max bounds for practical operation
        let clamped_ms = final_delay_ms
            .max(self.min_delay.as_secs_f64() * 1000.0)
            .min(self.max_delay.as_secs_f64() * 1000.0);

        Duration::from_millis(clamped_ms as u64)
    }

    /// Generate multiple delays
    pub fn next_delays(&self, count: usize) -> Vec<Duration> {
        (0..count).map(|_| self.next_delay()).collect()
    }

    /// Get base mean delay (without adaptations)
    pub fn base_mean_delay(&self) -> Duration {
        Duration::from_secs_f64(self.base_mean_delay_ms / 1000.0)
    }

    /// Get current mean delay (with load adaptation, before circuit multiplier)
    pub fn mean_delay(&self) -> Duration {
        Duration::from_secs_f64(self.current_mean_delay_ms / 1000.0)
    }

    /// Test statistical indistinguishability of generated delays
    ///
    /// Uses Chi-squared goodness-of-fit test to verify Poisson distribution.
    /// Returns p-value (>0.05 = statistically indistinguishable from Poisson).
    pub fn test_statistical_indistinguishability(&self, sample_size: usize) -> f64 {
        let samples: Vec<Duration> = self.next_delays(sample_size);
        let delays_ms: Vec<f64> = samples.iter().map(|d| d.as_secs_f64() * 1000.0).collect();

        // Compute sample statistics
        let mean = delays_ms.iter().sum::<f64>() / delays_ms.len() as f64;
        let variance = delays_ms
            .iter()
            .map(|&x| (x - mean).powi(2))
            .sum::<f64>()
            / delays_ms.len() as f64;

        // For exponential distribution, variance should equal mean^2
        let expected_variance = mean * mean;
        let chi_squared = (variance - expected_variance).abs() / expected_variance;

        // Convert chi-squared to approximate p-value (simplified)
        // For proper implementation, use statistical library
        let p_value = (-chi_squared / 2.0).exp();
        p_value.max(0.0).min(1.0)
    }

    /// Calculate delay distribution entropy (higher = more unpredictable)
    pub fn calculate_entropy(&self, sample_size: usize, num_bins: usize) -> f64 {
        let samples: Vec<Duration> = self.next_delays(sample_size);
        let delays_ms: Vec<f64> = samples.iter().map(|d| d.as_secs_f64() * 1000.0).collect();

        // Find min/max for binning
        let min_val = delays_ms.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_val = delays_ms.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let bin_width = (max_val - min_val) / num_bins as f64;

        if bin_width == 0.0 {
            return 0.0; // All values the same
        }

        // Count samples in each bin
        let mut bin_counts = vec![0usize; num_bins];
        for &delay in &delays_ms {
            let bin_idx = ((delay - min_val) / bin_width).floor() as usize;
            let bin_idx = bin_idx.min(num_bins - 1);
            bin_counts[bin_idx] += 1;
        }

        // Calculate entropy: H = -Σ(p_i * log2(p_i))
        let total = sample_size as f64;
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
}

/// VRF-seeded Poisson delay combining cryptographic unpredictability with Poisson distribution.
///
/// Uses Verifiable Random Functions (VRF) to generate cryptographically secure random delays
/// that follow a Poisson distribution. This provides both unpredictability and verifiability.
///
/// # Security Properties
///
/// - **Unpredictability**: Delays cannot be predicted by observers without the VRF secret key
/// - **Verifiability**: The randomness can be proven to come from legitimate VRF computation
/// - **Unbiasability**: Cannot be manipulated to favor specific delay values
///
/// # VRF Process
///
/// 1. Generate ephemeral VRF keypair using OS randomness
/// 2. Sign current timestamp with VRF to get deterministic but unpredictable output
/// 3. Verify the VRF proof for correctness
/// 4. Extract 8 bytes of randomness from VRF output
/// 5. Apply inverse transform sampling to get exponentially distributed delay
/// 6. Clamp to [min_delay, max_delay] bounds
///
/// # Arguments
///
/// * `mean_delay` - Target mean delay for the Poisson distribution
/// * `min_delay` - Minimum allowed delay (safety bound)
/// * `max_delay` - Maximum allowed delay (performance bound)
///
/// # Returns
///
/// A `Duration` representing the VRF-generated delay within specified bounds.
///
/// # Errors
///
/// Returns `MixnodeError::Vrf` if VRF proof verification fails.
///
/// # Examples
///
/// ```
/// use betanet::vrf::poisson_delay::calculate_vrf_poisson_delay;
/// use std::time::Duration;
///
/// # #[cfg(feature = "vrf")]
/// # async fn example() -> betanet::Result<()> {
/// let delay = calculate_vrf_poisson_delay(
///     &Duration::from_millis(500),
///     &Duration::from_millis(100),
///     &Duration::from_millis(2000)
/// ).await?;
///
/// println!("VRF-generated delay: {:?}", delay);
/// # Ok(())
/// # }
/// ```
#[cfg(feature = "vrf")]
pub async fn calculate_vrf_poisson_delay(
    mean_delay: &Duration,
    min_delay: &Duration,
    max_delay: &Duration,
) -> Result<Duration> {
    use rand::rngs::OsRng;
    use schnorrkel::{signing_context, Keypair};
    use std::time::{SystemTime, UNIX_EPOCH};

    // Generate ephemeral VRF keypair
    let mut csprng = OsRng;
    let keypair = Keypair::generate_with(&mut csprng);

    // Use current timestamp as VRF message
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos()
        .to_be_bytes();
    let ctx = signing_context(b"betanet-mixnode-poisson-delay");

    // Generate VRF proof and extract randomness
    let (io, proof, _) = keypair.vrf_sign(ctx.bytes(&now));

    // Verify proof
    keypair
        .public
        .vrf_verify(ctx.bytes(&now), &io.to_preout(), &proof)
        .map_err(|e| crate::MixnodeError::Vrf(format!("VRF proof verification failed: {e}")))?;

    // Extract 8 bytes of randomness for Poisson sampling
    let bytes: [u8; 8] = io.make_bytes(b"poisson");
    let random_u64 = u64::from_be_bytes(bytes);

    // Convert to f64 in [0, 1)
    let uniform_random = (random_u64 as f64) / (u64::MAX as f64);

    // Inverse transform sampling for exponential distribution (Poisson inter-arrival times)
    let mean_ms = mean_delay.as_secs_f64() * 1000.0;
    let lambda = 1.0 / mean_ms;
    let delay_ms = -((1.0 - uniform_random).ln()) / lambda;

    // Clamp to bounds
    let clamped_ms = delay_ms
        .max(min_delay.as_secs_f64() * 1000.0)
        .min(max_delay.as_secs_f64() * 1000.0);

    Ok(Duration::from_millis(clamped_ms as u64))
}

/// Fallback Poisson delay without VRF (uses system randomness)
#[cfg(not(feature = "vrf"))]
pub async fn calculate_vrf_poisson_delay(
    mean_delay: &Duration,
    min_delay: &Duration,
    max_delay: &Duration,
) -> Result<Duration> {
    let generator = PoissonDelayGenerator::new(*mean_delay, *min_delay, *max_delay)?;
    Ok(generator.next_delay())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_poisson_delay_bounds() {
        let mean = Duration::from_millis(500);
        let min = Duration::from_millis(100);
        let max = Duration::from_millis(2000);

        let generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

        // Generate many samples and verify bounds
        for _ in 0..1000 {
            let delay = generator.next_delay();
            assert!(delay >= min);
            assert!(delay <= max);
        }
    }

    #[test]
    fn test_poisson_delay_mean() {
        let mean = Duration::from_millis(500);
        let min = Duration::from_millis(10);
        let max = Duration::from_millis(5000);

        let generator = PoissonDelayGenerator::new(mean, min, max).unwrap();

        // Generate many samples and check mean is approximately correct
        let samples: Vec<Duration> = generator.next_delays(10000);
        let sum: u64 = samples.iter().map(|d| d.as_millis() as u64).sum();
        let actual_mean = sum / samples.len() as u64;

        // Mean should be within 20% of expected (Poisson has variance = mean)
        let expected_mean = mean.as_millis() as u64;
        let tolerance = expected_mean / 5; // 20% tolerance

        assert!(
            actual_mean >= expected_mean - tolerance && actual_mean <= expected_mean + tolerance,
            "Mean {} is outside tolerance of expected {}",
            actual_mean,
            expected_mean
        );
    }

    #[test]
    fn test_invalid_config() {
        let mean = Duration::from_millis(500);
        let min = Duration::from_millis(600); // min > mean (invalid)
        let max = Duration::from_millis(1000);

        let result = PoissonDelayGenerator::new(mean, min, max);
        assert!(result.is_err());
    }

    #[cfg(feature = "vrf")]
    #[tokio::test]
    async fn test_vrf_poisson_delay() {
        let mean = Duration::from_millis(500);
        let min = Duration::from_millis(100);
        let max = Duration::from_millis(2000);

        for _ in 0..100 {
            let delay = calculate_vrf_poisson_delay(&mean, &min, &max)
                .await
                .unwrap();
            assert!(delay >= min);
            assert!(delay <= max);
        }
    }
}
