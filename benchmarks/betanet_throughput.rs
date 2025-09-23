// Betanet Throughput Benchmark
// Target: 25,000 packets per second (pps)

use std::time::{Duration, Instant};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

#[derive(Debug)]
struct ThroughputMetrics {
    packets_sent: u64,
    packets_received: u64,
    duration_ms: u128,
    throughput_pps: f64,
    p50_latency_us: u64,
    p95_latency_us: u64,
    p99_latency_us: u64,
}

struct BetanetThroughputBenchmark {
    packet_counter: Arc<AtomicU64>,
    latencies: Vec<u64>,
}

impl BetanetThroughputBenchmark {
    fn new() -> Self {
        Self {
            packet_counter: Arc::new(AtomicU64::new(0)),
            latencies: Vec::new(),
        }
    }

    fn calculate_percentile(&self, percentile: f64) -> u64 {
        if self.latencies.is_empty() {
            return 0;
        }

        let mut sorted = self.latencies.clone();
        sorted.sort_unstable();

        let idx = ((sorted.len() as f64) * percentile) as usize;
        sorted[idx.min(sorted.len() - 1)]
    }

    async fn bench_packet_throughput(&mut self, duration_secs: u64, target_pps: u64) -> ThroughputMetrics {
        let start = Instant::now();
        let mut packets_sent = 0u64;
        let mut packets_received = 0u64;

        let interval_ns = 1_000_000_000 / target_pps; // nanoseconds per packet

        while start.elapsed().as_secs() < duration_secs {
            let packet_start = Instant::now();

            // Simulate packet creation
            let packet = self.create_packet(packets_sent);

            // Simulate network send
            self.send_packet(&packet).await;
            packets_sent += 1;

            // Simulate packet receive
            if self.receive_packet(&packet).await {
                packets_received += 1;

                let latency_us = packet_start.elapsed().as_micros() as u64;
                self.latencies.push(latency_us);
            }

            // Rate limiting
            let elapsed_ns = packet_start.elapsed().as_nanos() as u64;
            if elapsed_ns < interval_ns {
                tokio::time::sleep(Duration::from_nanos(interval_ns - elapsed_ns)).await;
            }
        }

        let duration_ms = start.elapsed().as_millis();
        let throughput_pps = (packets_sent as f64) / (duration_ms as f64 / 1000.0);

        ThroughputMetrics {
            packets_sent,
            packets_received,
            duration_ms,
            throughput_pps,
            p50_latency_us: self.calculate_percentile(0.50),
            p95_latency_us: self.calculate_percentile(0.95),
            p99_latency_us: self.calculate_percentile(0.99),
        }
    }

    fn create_packet(&self, seq: u64) -> Vec<u8> {
        // Simulate 1KB packet
        let mut packet = vec![0u8; 1024];
        packet[0..8].copy_from_slice(&seq.to_le_bytes());
        packet
    }

    async fn send_packet(&self, _packet: &[u8]) {
        // Simulate network send operation (non-blocking)
        tokio::time::sleep(Duration::from_micros(10)).await;
    }

    async fn receive_packet(&self, _packet: &[u8]) -> bool {
        // Simulate packet acknowledgment
        tokio::time::sleep(Duration::from_micros(5)).await;
        true
    }

    async fn bench_concurrent_streams(&mut self, num_streams: usize, duration_secs: u64) -> Vec<ThroughputMetrics> {
        let mut handles = vec![];

        for stream_id in 0..num_streams {
            let counter = self.packet_counter.clone();

            let handle = tokio::spawn(async move {
                let mut stream_latencies = Vec::new();
                let start = Instant::now();
                let mut packets = 0u64;

                while start.elapsed().as_secs() < duration_secs {
                    let packet_start = Instant::now();

                    // Simulate packet processing
                    tokio::time::sleep(Duration::from_micros(20)).await;

                    packets += 1;
                    counter.fetch_add(1, Ordering::Relaxed);

                    stream_latencies.push(packet_start.elapsed().as_micros() as u64);
                }

                (stream_id, packets, stream_latencies)
            });

            handles.push(handle);
        }

        let mut results = Vec::new();

        for handle in handles {
            if let Ok((_stream_id, packets, latencies)) = handle.await {
                let mut sorted_latencies = latencies.clone();
                sorted_latencies.sort_unstable();

                let n = sorted_latencies.len();

                results.push(ThroughputMetrics {
                    packets_sent: packets,
                    packets_received: packets,
                    duration_ms: duration_secs * 1000,
                    throughput_pps: (packets as f64) / (duration_secs as f64),
                    p50_latency_us: sorted_latencies.get(n / 2).copied().unwrap_or(0),
                    p95_latency_us: sorted_latencies.get(n * 95 / 100).copied().unwrap_or(0),
                    p99_latency_us: sorted_latencies.get(n * 99 / 100).copied().unwrap_or(0),
                });
            }
        }

        results
    }
}

#[tokio::main]
async fn main() {
    println!("Betanet Throughput Benchmark");
    println!("{}", "=".repeat(70));

    let mut bench = BetanetThroughputBenchmark::new();

    println!("\n1. Single Stream Throughput (target: 25,000 pps)");
    let result = bench.bench_packet_throughput(10, 25000).await;
    println!("   Packets Sent: {}", result.packets_sent);
    println!("   Throughput: {:.2} pps", result.throughput_pps);
    println!("   P50 Latency: {} μs", result.p50_latency_us);
    println!("   P95 Latency: {} μs", result.p95_latency_us);
    println!("   P99 Latency: {} μs", result.p99_latency_us);

    let passes = result.throughput_pps >= 25000.0;
    println!("   Target Met: {}", if passes { "YES" } else { "NO" });

    println!("\n2. Concurrent Streams (10 streams, 5 seconds each)");
    let results = bench.bench_concurrent_streams(10, 5).await;

    let total_throughput: f64 = results.iter().map(|r| r.throughput_pps).sum();
    println!("   Total Throughput: {:.2} pps", total_throughput);
    println!("   Streams: {}", results.len());

    println!("\n{}", "=".repeat(70));

    // Generate JSON report
    let report = serde_json::json!({
        "benchmark": "betanet_throughput",
        "timestamp": std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
        "single_stream": {
            "packets_sent": result.packets_sent,
            "throughput_pps": result.throughput_pps,
            "p50_latency_us": result.p50_latency_us,
            "p95_latency_us": result.p95_latency_us,
            "p99_latency_us": result.p99_latency_us,
            "target_met": passes
        },
        "concurrent_streams": {
            "num_streams": results.len(),
            "total_throughput_pps": total_throughput,
            "avg_throughput_pps": total_throughput / results.len() as f64
        },
        "performance_gate": {
            "target_pps": 25000,
            "actual_pps": result.throughput_pps,
            "pass": passes
        }
    });

    std::fs::write(
        "C:/Users/17175/Desktop/fog-compute/benchmarks/betanet_throughput_report.json",
        serde_json::to_string_pretty(&report).unwrap()
    ).expect("Failed to write report");

    println!("\nReport saved to: benchmarks/betanet_throughput_report.json");
}