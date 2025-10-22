# BetaNet Enhanced Delay Injection

## Overview

This document describes the enhanced delay injection algorithms implemented for BetaNet to provide superior timing attack resistance and privacy guarantees. The system combines multiple techniques to protect against traffic analysis attacks while maintaining reasonable performance.

## Architecture

The delay injection system consists of four main components:

1. **Enhanced Poisson Delay Generator** (`src/betanet/vrf/poisson_delay.rs`)
2. **Adaptive Batching** (`src/betanet/pipeline/batching.rs`)
3. **Cover Traffic Generator** (`src/betanet/cover.rs`)
4. **Timing Attack Defense** (`src/betanet/utils/timing_defense.rs`)

## 1. Enhanced Poisson Delay Generator

### Algorithm

The Poisson delay generator creates delays following an exponential distribution (Poisson inter-arrival times):

```
delay = -ln(U) / λ
```

Where:
- `U ~ Uniform(0,1)` - uniformly distributed random variable
- `λ = 1/mean_delay` - rate parameter

### Enhanced Features

#### Network Load Adaptation

The generator adapts to network load using exponential backoff:

```rust
delay_multiplier = 1 + load² × 2
effective_lambda = 1 / (base_mean × multiplier)
```

This ensures privacy is maintained even under high load by increasing delays.

#### Per-Circuit Customization

Different circuits can have different delay characteristics:

```rust
let mut generator = PoissonDelayGenerator::new(mean, min, max)?;
generator.set_circuit_multiplier(2.0); // 2x slower for sensitive circuit
```

#### Jitter Injection

Additional randomness prevents timing fingerprinting:

```rust
jitter_factor = 1 + (random - 0.5) × 2 × jitter_pct
final_delay = base_delay × circuit_multiplier × jitter_factor
```

Default jitter: 10% (±10%)

### Statistical Properties

**Indistinguishability Test**: Chi-squared goodness-of-fit test
```rust
let p_value = generator.test_statistical_indistinguishability(1000);
// p_value > 0.05 → statistically indistinguishable from Poisson
```

**Entropy Calculation**: Measures unpredictability
```rust
let entropy = generator.calculate_entropy(1000, 20);
// Higher entropy = more unpredictable (target: > 2.0)
```

## 2. Adaptive Batching

### Strategies

#### Load-Based
Batch size scales with network load:
```
batch_size = min_size + (max_size - min_size) × load²
```

#### Balanced
Adaptive strategy balancing latency and privacy:
- Low load (< 0.3): min_batch_size (low latency)
- High load (> 0.7): max_batch_size (high privacy)
- Medium load: linear interpolation

#### Min-Latency
Prioritizes fast delivery (smaller batches)

#### Max-Throughput
Prioritizes efficiency (larger batches)

### Configuration

```rust
let config = AdaptiveBatchingConfig {
    min_batch_size: 1,
    max_batch_size: 128,
    strategy: BatchingStrategy::Balanced,
    min_delay_ms: 10,           // Minimum 10ms between batches
    max_throughput_pps: 25000.0, // Target throughput
    load_increase_threshold: 0.7, // High load threshold
    load_decrease_threshold: 0.3, // Low load threshold
};
```

### Privacy-Latency Trade-off

Score calculation:
```
score = (batch_efficiency × 0.6) + (latency_efficiency × 0.4)

where:
  batch_efficiency = current_size / max_size
  latency_efficiency = target_delay / actual_delay
```

## 3. Cover Traffic Generator

### Modes

#### Constant Rate
Sends dummy packets at constant rate regardless of real traffic.

**Pros**: Maximum privacy, predictable bandwidth
**Cons**: Higher overhead

#### Adaptive
Matches real traffic patterns dynamically.

**Pros**: Lower overhead, adaptive
**Cons**: Slightly weaker privacy

#### Burst
Sends in bursts to match real traffic bursting behavior.

**Pros**: Realistic patterns
**Cons**: Harder to tune

### Indistinguishability

The generator tracks real traffic statistics and generates cover traffic that matches:

```rust
pub struct TrafficStatistics {
    pub avg_packet_size: f64,
    pub size_std_dev: f64,
    pub avg_interval_ms: f64,
    pub interval_std_dev_ms: f64,
}

// Similarity score: 0.0 (completely different) to 1.0 (identical)
let similarity = real_stats.similarity_score(&cover_stats);
```

Formula:
```
similarity = (size_sim × 0.6) + (interval_sim × 0.4)

where:
  size_sim = 1 - |CV_real - CV_cover| / (CV_real + CV_cover)
  CV = coefficient of variation = std_dev / mean
```

### Bandwidth Overhead Control

Maximum overhead is enforced:

```rust
overhead = cover_bytes / real_bytes
if overhead > max_bandwidth_overhead {
    // Skip cover packet generation
}
```

Target: < 5% overhead

## 4. Timing Attack Defense

### Techniques

#### Inter-Packet Timing Randomization

```rust
randomized_delay = original_delay × (1 ± randomization_pct)
```

Default: ±30% randomization

#### Correlation Analysis Resistance

Pearson correlation coefficient between original and actual delays:

```
r = Σ(x_i - x̄)(y_i - ȳ) / √(Σ(x_i - x̄)² × Σ(y_i - ȳ)²)
```

Target: |r| < 0.3 (low correlation)

#### Burst Pattern Masking

Detects bursts (rate > threshold) and adds delays to break patterns:

```rust
if detect_burst() {
    additional_delay = random(10ms, 100ms)
}
```

### Privacy Metrics

#### Timing Variance
Higher variance = better resistance

```
variance = Σ(interval_i - mean)² / n
```

#### Timing Entropy
Measures unpredictability of timing distribution

```
entropy = -Σ(p_i × log₂(p_i))
```

Target: > 2.0 (for 20 bins)

#### Resistance Score

Combined metric (0.0-1.0):
```
score = (correlation_score × 0.3) +
        (variance_score × 0.3) +
        (entropy_score × 0.4)

where:
  correlation_score = 1 - |correlation|
  variance_score = min(variance / 10000, 1.0)
  entropy_score = min(entropy / 4.32, 1.0)
```

Target: > 0.6 (good resistance)

## Performance Guarantees

### Latency

- **Base latency**: Mean Poisson delay (configurable, default: 100-500ms)
- **Batching delay**: Minimum delay per batch (default: 10ms)
- **Cover traffic**: < 5% overhead
- **Total overhead**: < 20% latency increase

### Throughput

- **Target**: 25,000 packets/second
- **Batch processing**: Up to 128 packets/batch
- **Memory efficiency**: Pool-based allocation (> 80% hit rate)

### Privacy

- **Poisson indistinguishability**: p-value > 0.05
- **Cover traffic similarity**: > 95%
- **Timing correlation**: |r| < 0.3
- **Entropy**: > 2.0

## Usage Examples

### Basic Setup

```rust
use betanet::vrf::poisson_delay::PoissonDelayGenerator;
use betanet::pipeline::batching::{AdaptiveBatchProcessor, AdaptiveBatchingConfig, BatchingStrategy};
use betanet::cover::{AdvancedCoverTrafficGenerator, CoverTrafficConfig, CoverTrafficMode};
use betanet::utils::timing_defense::{TimingDefenseManager, TimingDefenseConfig};
use std::time::Duration;

// 1. Poisson delay
let mut poisson = PoissonDelayGenerator::new(
    Duration::from_millis(200),  // mean
    Duration::from_millis(50),   // min
    Duration::from_millis(1000), // max
)?
.with_jitter(0.2); // 20% jitter

// 2. Adaptive batching
let batching_config = AdaptiveBatchingConfig {
    strategy: BatchingStrategy::Balanced,
    min_batch_size: 1,
    max_batch_size: 64,
    ..Default::default()
};
let batcher = AdaptiveBatchProcessor::new(batching_config)?;

// 3. Cover traffic
let cover_config = CoverTrafficConfig {
    enabled: true,
    mode: CoverTrafficMode::Adaptive,
    max_bandwidth_overhead: 0.05, // 5% max
    ..Default::default()
};
let cover = AdvancedCoverTrafficGenerator::new(cover_config);

// 4. Timing defense
let timing = TimingDefenseManager::new(TimingDefenseConfig::default());
```

### Processing Packets

```rust
// Process incoming packet
async fn process_packet(packet: Vec<u8>) {
    // 1. Get delay
    let delay = poisson.next_delay();

    // 2. Randomize timing
    let randomized_delay = timing.randomize_delay(delay).await;

    // 3. Record timing
    timing.record_packet_timing(
        packet.len(),
        delay,
        randomized_delay
    ).await;

    // 4. Apply delay
    tokio::time::sleep(randomized_delay).await;

    // 5. Submit to batcher
    batcher.submit_packet(packet).await?;

    // 6. Update cover traffic stats
    cover.update_real_traffic_stats(packet.len()).await;

    // 7. Maybe generate cover packet
    if let Some(cover_packet) = cover.generate_cover_packet().await {
        // Send cover packet
        send_packet(cover_packet).await;
    }
}
```

### Monitoring

```rust
// Check timing defense effectiveness
let stats = timing.get_timing_stats().await;
stats.print();

// Check batching efficiency
let batch_stats = batcher.stats();
println!("Avg batch size: {:.1}", batch_stats.average_batch_size());

// Check cover traffic indistinguishability
let similarity = cover.test_indistinguishability().await;
println!("Cover similarity: {:.2}%", similarity * 100.0);

// Overall resistance score
let resistance = timing.timing_attack_resistance_score().await;
println!("Resistance: {:.2}%", resistance * 100.0);
```

### Adaptive Configuration

```rust
// Adapt to network conditions
async fn adapt_to_network(load: f64) {
    // Update Poisson delays
    poisson.adapt_to_network_load(load);

    // Update batching strategy
    batcher.update_network_load(load).await;

    // Cover traffic adapts automatically
}

// Per-circuit tuning
generator.set_circuit_multiplier(2.0); // Slower for sensitive circuits
generator.set_circuit_multiplier(0.5); // Faster for low-latency circuits
```

## Testing

Run comprehensive tests:

```bash
cargo test --package betanet --test test_delay_injection
```

Tests include:
- ✅ Poisson distribution properties
- ✅ Adaptive delay based on load
- ✅ Circuit-specific delays
- ✅ Statistical indistinguishability
- ✅ Delay entropy
- ✅ Adaptive batching
- ✅ Cover traffic generation
- ✅ Cover traffic indistinguishability
- ✅ Timing attack resistance
- ✅ Throughput overhead (< 5%)
- ✅ Integrated delay injection

## Performance Benchmarks

Run benchmarks:

```bash
python scripts/benchmark_delay_injection.py
```

Metrics measured:
- Delay distribution statistics
- Privacy metrics (correlation, entropy)
- Throughput impact
- Latency overhead
- Batch size efficiency
- Cover traffic overhead

## Security Considerations

### Timing Side-Channels

**Mitigation**:
- Constant-time operations where possible
- Randomization to prevent correlation
- Burst masking to hide patterns

### Traffic Analysis

**Mitigation**:
- Poisson delays prevent timing correlation
- Cover traffic prevents traffic volume analysis
- Batching prevents packet counting

### Adaptive Attacks

**Mitigation**:
- Adaptive parameter adjustment based on load
- Statistical testing for indistinguishability
- Continuous monitoring of privacy metrics

## References

1. **Poisson Delay**: Betanet v1.2 Privacy Hop specification
2. **Traffic Analysis**: "Website Fingerprinting Defenses" (Pulls & Vassilomanolakis, 2020)
3. **Batching**: "High-Throughput Mix Networks" (Danezis & Diaz, 2008)
4. **Cover Traffic**: "CS-BuFLO: A Congestion Sensitive Website Fingerprinting Defense" (Cai et al., 2014)

## Configuration Reference

### Poisson Delay
- `mean_delay`: 100-500ms (default: 200ms)
- `min_delay`: 50-100ms (default: 50ms)
- `max_delay`: 1000-5000ms (default: 2000ms)
- `jitter_pct`: 0.1-0.5 (default: 0.1)

### Batching
- `min_batch_size`: 1-10 (default: 1)
- `max_batch_size`: 64-128 (default: 128)
- `min_delay_ms`: 5-20ms (default: 10ms)
- `max_throughput_pps`: 10000-50000 (default: 25000)

### Cover Traffic
- `target_rate`: 5-20 pkt/s (default: 10)
- `max_bandwidth_overhead`: 0.03-0.10 (default: 0.05)
- `indistinguishability_threshold`: 0.90-0.95 (default: 0.95)

### Timing Defense
- `randomization_pct`: 0.2-0.5 (default: 0.3)
- `max_correlation`: 0.2-0.4 (default: 0.3)

## Troubleshooting

### High Latency
- Reduce `mean_delay` in Poisson generator
- Lower `min_delay_ms` in batching
- Use `MinLatency` batching strategy

### Insufficient Privacy
- Increase `jitter_pct` in Poisson generator
- Use `MaxThroughput` batching for larger batches
- Enable cover traffic or increase `target_rate`
- Increase `randomization_pct` in timing defense

### High Overhead
- Reduce cover traffic `target_rate`
- Lower `max_bandwidth_overhead` limit
- Use `Adaptive` mode for cover traffic

## Future Enhancements

1. **Machine Learning-based Adaptation**: Use ML to predict optimal parameters
2. **Multi-path Delay Correlation**: Coordinate delays across multiple paths
3. **Differential Privacy**: Add formal DP guarantees
4. **Hardware Acceleration**: GPU/FPGA for high-throughput processing
