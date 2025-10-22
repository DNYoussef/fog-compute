//! Poisson-distributed delay for enhanced privacy
//!
//! Implements Poisson delay distribution as recommended by
//! Betanet v1.2 Privacy Hop specification for better traffic analysis resistance.

use rand::prelude::*;
use std::time::Duration;

use crate::Result;

// Exponential distribution for Poisson process
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

/// Poisson delay generator
pub struct PoissonDelayGenerator {
    /// Mean delay in milliseconds
    mean_delay_ms: f64,
    /// Minimum delay (prevents zero delays)
    min_delay: Duration,
    /// Maximum delay (prevents excessive delays)
    max_delay: Duration,
    /// Exponential distribution for Poisson inter-arrival times
    exp_dist: Exp<f64>,
}

impl PoissonDelayGenerator {
    /// Create new Poisson delay generator
    ///
    /// # Arguments
    /// * `mean_delay` - Mean delay (center of distribution)
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
            mean_delay_ms,
            min_delay,
            max_delay,
            exp_dist: Exp::new(lambda).map_err(|e| {
                crate::MixnodeError::Config(format!("Invalid exponential distribution: {}", e))
            })?,
        })
    }

    /// Generate next delay using Poisson distribution
    pub fn next_delay(&self) -> Duration {
        let mut rng = thread_rng();
        let delay_ms = self.exp_dist.sample(&mut rng);

        // Clamp to min/max bounds
        let clamped_ms = delay_ms.max(self.min_delay.as_secs_f64() * 1000.0)
            .min(self.max_delay.as_secs_f64() * 1000.0);

        Duration::from_millis(clamped_ms as u64)
    }

    /// Generate multiple delays
    pub fn next_delays(&self, count: usize) -> Vec<Duration> {
        (0..count).map(|_| self.next_delay()).collect()
    }

    /// Get mean delay
    pub fn mean_delay(&self) -> Duration {
        Duration::from_secs_f64(self.mean_delay_ms / 1000.0)
    }
}

/// VRF-seeded Poisson delay (combines VRF unpredictability with Poisson distribution)
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
            let delay = calculate_vrf_poisson_delay(&mean, &min, &max).await.unwrap();
            assert!(delay >= min);
            assert!(delay <= max);
        }
    }
}
