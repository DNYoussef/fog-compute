//! High-performance pipeline benchmark
//!
//! Demonstrates the 70% performance improvement target

use betanet::{PipelineBenchmark, PerformanceTargets};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    println!("=== Betanet Pipeline Benchmark ===\n");

    // Performance targets
    let targets = PerformanceTargets::default();
    println!("Performance Targets:");
    println!("  Throughput:      {:.0} pkt/s", targets.target_throughput_pps);
    println!("  Max Latency:     {:.2} ms", targets.max_avg_latency_ms);
    println!("  Pool Hit Rate:   {:.1}%", targets.min_pool_hit_rate_pct);
    println!("  Max Drop Rate:   {:.2}%\n", targets.max_drop_rate_pct);

    // Create benchmark with 4 workers and 10,000 test packets
    let mut bench = PipelineBenchmark::new(4, 10_000);

    println!("Running 10-second throughput test...\n");

    // Run benchmark
    let results = bench.run_throughput_test(10).await?;

    // Print results
    results.print_results();

    // Verify performance targets
    println!("\nPerformance Analysis:");

    let throughput_ok = results.meets_target(targets.target_throughput_pps);
    println!(
        "  Throughput:      {} (target: {:.0} pkt/s)",
        if throughput_ok { "✓ PASS" } else { "✗ FAIL" },
        targets.target_throughput_pps
    );

    let latency_us = results.avg_processing_time_ns as f64 / 1000.0;
    let latency_ok = latency_us < (targets.max_avg_latency_ms * 1000.0);
    println!(
        "  Latency:         {} ({:.2}μs vs {:.0}μs max)",
        if latency_ok { "✓ PASS" } else { "✗ FAIL" },
        latency_us,
        targets.max_avg_latency_ms * 1000.0
    );

    let pool_hit_ok = results.memory_pool_hit_rate >= (targets.min_pool_hit_rate_pct / 100.0);
    println!(
        "  Pool Hit Rate:   {} ({:.1}% vs {:.1}% min)",
        if pool_hit_ok { "✓ PASS" } else { "✗ FAIL" },
        results.memory_pool_hit_rate * 100.0,
        targets.min_pool_hit_rate_pct
    );

    let drop_rate = (results.packets_dropped as f64 / results.packets_sent as f64) * 100.0;
    let drop_ok = drop_rate <= targets.max_drop_rate_pct;
    println!(
        "  Drop Rate:       {} ({:.2}% vs {:.2}% max)",
        if drop_ok { "✓ PASS" } else { "✗ FAIL" },
        drop_rate,
        targets.max_drop_rate_pct
    );

    // Overall result
    let all_pass = throughput_ok && latency_ok && pool_hit_ok && drop_ok;
    println!(
        "\nOverall: {}",
        if all_pass {
            "✓ ALL TARGETS MET"
        } else {
            "✗ SOME TARGETS MISSED"
        }
    );

    // Calculate improvement over baseline
    let baseline_pps = 15000.0;
    let improvement_pct = ((results.throughput_pps - baseline_pps) / baseline_pps) * 100.0;
    println!(
        "\nImprovement over baseline ({:.0} pkt/s): {:.1}%",
        baseline_pps, improvement_pct
    );

    Ok(())
}