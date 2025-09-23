//! Betanet Network Performance Tests
//! Tests for network throughput and latency under various conditions

use betanet::*;
use betanet::pipeline::{PacketPipeline, PipelinePacket};
use betanet::core::config::MixnodeConfig;

use std::time::{Duration, Instant};
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Debug)]
struct NetworkTestResult {
    throughput_pps: f64,
    avg_latency_ms: f64,
    p95_latency_ms: f64,
    p99_latency_ms: f64,
    packet_loss_rate: f64,
    bandwidth_mbps: f64,
}

struct NetworkPerformanceTest {
    results: Vec<NetworkTestResult>,
}

impl NetworkPerformanceTest {
    fn new() -> Self {
        Self {
            results: Vec::new(),
        }
    }

    async fn test_throughput(&mut self, packet_count: usize, packet_size: usize) -> NetworkTestResult {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:12000".parse().unwrap(),
            max_packet_size: 4096,
            processing_delay_ms: 0,
            cover_traffic_rate: 0,
            max_concurrent_packets: 10000,
            memory_pool_size: 4096,
        };

        let pipeline = Arc::new(PacketPipeline::new(config));
        let start = Instant::now();
        let mut latencies = Vec::new();
        let mut packets_sent = 0;
        let mut packets_lost = 0;

        for i in 0..packet_count {
            let packet = PipelinePacket::new(vec![i as u8; packet_size]);
            let packet_start = Instant::now();

            match pipeline.process(packet).await {
                Ok(_) => {
                    let latency = packet_start.elapsed();
                    latencies.push(latency.as_micros() as f64 / 1000.0);
                    packets_sent += 1;
                }
                Err(_) => {
                    packets_lost += 1;
                }
            }
        }

        let total_time = start.elapsed();
        let throughput = packets_sent as f64 / total_time.as_secs_f64();

        latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let avg_latency = latencies.iter().sum::<f64>() / latencies.len() as f64;
        let p95_index = (latencies.len() as f64 * 0.95) as usize;
        let p99_index = (latencies.len() as f64 * 0.99) as usize;
        let p95_latency = latencies[p95_index];
        let p99_latency = latencies[p99_index];

        let packet_loss_rate = (packets_lost as f64 / packet_count as f64) * 100.0;
        let total_bytes = packets_sent * packet_size;
        let bandwidth_mbps = (total_bytes as f64 * 8.0) / (total_time.as_secs_f64() * 1_000_000.0);

        let result = NetworkTestResult {
            throughput_pps: throughput,
            avg_latency_ms: avg_latency,
            p95_latency_ms: p95_latency,
            p99_latency_ms: p99_latency,
            packet_loss_rate,
            bandwidth_mbps,
        };

        self.results.push(result);
        self.results.last().unwrap().clone()
    }

    async fn test_concurrent_throughput(&mut self, concurrent_clients: usize) -> NetworkTestResult {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:12001".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 0,
            cover_traffic_rate: 0,
            max_concurrent_packets: concurrent_clients * 100,
            memory_pool_size: 4096,
        };

        let pipeline = Arc::new(PacketPipeline::new(config));
        let start = Instant::now();
        let latencies = Arc::new(Mutex::new(Vec::new()));
        let total_packets = Arc::new(Mutex::new(0usize));

        let mut handles = Vec::new();

        for client_id in 0..concurrent_clients {
            let p = pipeline.clone();
            let lats = latencies.clone();
            let total = total_packets.clone();

            let handle = tokio::spawn(async move {
                for i in 0..100 {
                    let packet = PipelinePacket::new(vec![(client_id + i) as u8; 512]);
                    let packet_start = Instant::now();

                    if p.process(packet).await.is_ok() {
                        let latency = packet_start.elapsed().as_micros() as f64 / 1000.0;
                        lats.lock().await.push(latency);
                        *total.lock().await += 1;
                    }
                }
            });

            handles.push(handle);
        }

        for handle in handles {
            handle.await.unwrap();
        }

        let total_time = start.elapsed();
        let packets_sent = *total_packets.lock().await;
        let throughput = packets_sent as f64 / total_time.as_secs_f64();

        let mut lat_vec = latencies.lock().await.clone();
        lat_vec.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let avg_latency = lat_vec.iter().sum::<f64>() / lat_vec.len() as f64;
        let p95_index = (lat_vec.len() as f64 * 0.95) as usize;
        let p99_index = (lat_vec.len() as f64 * 0.99) as usize;

        NetworkTestResult {
            throughput_pps: throughput,
            avg_latency_ms: avg_latency,
            p95_latency_ms: lat_vec[p95_index],
            p99_latency_ms: lat_vec[p99_index],
            packet_loss_rate: 0.0,
            bandwidth_mbps: (packets_sent * 512 * 8) as f64 / (total_time.as_secs_f64() * 1_000_000.0),
        }
    }

    async fn test_variable_packet_sizes(&mut self) {
        println!("Testing variable packet sizes...");

        let sizes = vec![64, 128, 256, 512, 1024, 1536, 2048];

        for size in sizes {
            let result = self.test_throughput(1000, size).await;
            println!(
                "Packet size {}B: {:.2} pps, {:.3} ms latency, {:.2} Mbps",
                size, result.throughput_pps, result.avg_latency_ms, result.bandwidth_mbps
            );
        }
    }

    async fn test_scalability(&mut self) {
        println!("\nTesting scalability with concurrent clients...");

        let client_counts = vec![1, 10, 25, 50, 100, 250];

        for count in client_counts {
            let result = self.test_concurrent_throughput(count).await;
            println!(
                "{} clients: {:.2} pps, {:.3} ms avg, {:.3} ms p95",
                count, result.throughput_pps, result.avg_latency_ms, result.p95_latency_ms
            );
        }
    }

    async fn test_sustained_load(&mut self, duration_secs: u64) {
        println!("\nTesting sustained load ({} seconds)...", duration_secs);

        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:12002".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 0,
            cover_traffic_rate: 0,
            max_concurrent_packets: 5000,
            memory_pool_size: 4096,
        };

        let pipeline = Arc::new(PacketPipeline::new(config));
        let start = Instant::now();
        let mut total_packets = 0;
        let mut latencies = Vec::new();

        while start.elapsed().as_secs() < duration_secs {
            let packet = PipelinePacket::new(vec![0u8; 1024]);
            let packet_start = Instant::now();

            if pipeline.process(packet).await.is_ok() {
                let latency = packet_start.elapsed().as_micros() as f64 / 1000.0;
                latencies.push(latency);
                total_packets += 1;
            }
        }

        let total_time = start.elapsed();
        let throughput = total_packets as f64 / total_time.as_secs_f64();
        let avg_latency = latencies.iter().sum::<f64>() / latencies.len() as f64;

        println!(
            "Sustained load: {:.2} pps average, {:.3} ms latency over {} seconds",
            throughput, avg_latency, duration_secs
        );
    }

    fn generate_report(&self) {
        println!("\n{}", "=".repeat(80));
        println!("NETWORK PERFORMANCE TEST REPORT");
        println!("{}", "=".repeat(80));

        if self.results.is_empty() {
            println!("No results to report");
            return;
        }

        println!("\n{:<15} {:<15} {:<15} {:<15} {:<15}", "Throughput", "Avg Latency", "P95 Latency", "P99 Latency", "Bandwidth");
        println!("{:<15} {:<15} {:<15} {:<15} {:<15}", "(pps)", "(ms)", "(ms)", "(ms)", "(Mbps)");
        println!("{}", "-".repeat(75));

        for result in &self.results {
            println!(
                "{:<15.2} {:<15.3} {:<15.3} {:<15.3} {:<15.2}",
                result.throughput_pps,
                result.avg_latency_ms,
                result.p95_latency_ms,
                result.p99_latency_ms,
                result.bandwidth_mbps
            );
        }

        // Calculate averages
        let avg_throughput: f64 = self.results.iter().map(|r| r.throughput_pps).sum::<f64>() / self.results.len() as f64;
        let avg_latency: f64 = self.results.iter().map(|r| r.avg_latency_ms).sum::<f64>() / self.results.len() as f64;

        println!("\nAverage Metrics:");
        println!("  Throughput: {:.2} pps", avg_throughput);
        println!("  Latency: {:.3} ms", avg_latency);

        // Performance grade
        let grade = if avg_throughput >= 25000.0 && avg_latency <= 1.0 {
            "A - Excellent"
        } else if avg_throughput >= 20000.0 && avg_latency <= 2.0 {
            "B - Good"
        } else if avg_throughput >= 15000.0 && avg_latency <= 5.0 {
            "C - Acceptable"
        } else {
            "D - Needs Improvement"
        };

        println!("\nPerformance Grade: {}", grade);
    }
}

impl Clone for NetworkTestResult {
    fn clone(&self) -> Self {
        Self {
            throughput_pps: self.throughput_pps,
            avg_latency_ms: self.avg_latency_ms,
            p95_latency_ms: self.p95_latency_ms,
            p99_latency_ms: self.p99_latency_ms,
            packet_loss_rate: self.packet_loss_rate,
            bandwidth_mbps: self.bandwidth_mbps,
        }
    }
}

#[tokio::main]
async fn main() {
    println!("Betanet Network Performance Test Suite");
    println!("{}", "=".repeat(80));

    let mut tester = NetworkPerformanceTest::new();

    // Basic throughput test
    println!("\nBaseline throughput test...");
    let result = tester.test_throughput(10000, 1024).await;
    println!(
        "Result: {:.2} pps, {:.3} ms avg latency, {:.2} Mbps bandwidth",
        result.throughput_pps, result.avg_latency_ms, result.bandwidth_mbps
    );

    // Variable packet sizes
    tester.test_variable_packet_sizes().await;

    // Scalability test
    tester.test_scalability().await;

    // Sustained load test
    tester.test_sustained_load(10).await;

    // Generate report
    tester.generate_report();
}