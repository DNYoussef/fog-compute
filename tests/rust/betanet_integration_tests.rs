//! Betanet Integration Tests
//! Pipeline performance and integration testing

use betanet::*;
use betanet::pipeline::{PacketPipeline, PipelinePacket, PipelineBenchmark, PipelineStats};
use betanet::core::config::MixnodeConfig;

use std::time::{Duration, Instant};
use std::sync::Arc;
use tokio::sync::RwLock;

#[cfg(test)]
mod pipeline_performance_tests {
    use super::*;

    #[tokio::test]
    async fn test_pipeline_throughput() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11000".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 1000,
            memory_pool_size: 1024,
        };

        let pipeline = PacketPipeline::new(config);
        let packet_count = 1000;
        let start = Instant::now();

        for i in 0..packet_count {
            let packet = PipelinePacket::new(vec![i as u8; 512]);
            pipeline.process(packet).await.unwrap();
        }

        let elapsed = start.elapsed();
        let throughput = packet_count as f64 / elapsed.as_secs_f64();

        // Target: 25,000 packets/sec (70% improvement over 15k baseline)
        assert!(
            throughput >= 20000.0,
            "Throughput {} pps below target 20,000 pps",
            throughput
        );
    }

    #[tokio::test]
    async fn test_pipeline_latency() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11001".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 500,
            memory_pool_size: 512,
        };

        let pipeline = PacketPipeline::new(config);
        let iterations = 100;
        let mut latencies = Vec::new();

        for i in 0..iterations {
            let packet = PipelinePacket::new(vec![i as u8; 256]);
            let start = Instant::now();

            pipeline.process(packet).await.unwrap();

            let latency = start.elapsed();
            latencies.push(latency.as_micros() as f64);
        }

        let avg_latency_us = latencies.iter().sum::<f64>() / latencies.len() as f64;
        let avg_latency_ms = avg_latency_us / 1000.0;

        // Target: <1ms average latency
        assert!(
            avg_latency_ms < 1.0,
            "Average latency {}ms exceeds target 1ms",
            avg_latency_ms
        );
    }

    #[tokio::test]
    async fn test_memory_pool_efficiency() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11002".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 0,
            cover_traffic_rate: 0,
            max_concurrent_packets: 1024,
            memory_pool_size: 1024,
        };

        let pipeline = PacketPipeline::new(config);
        let stats = Arc::new(RwLock::new(PipelineStats::default()));

        for i in 0..500 {
            let packet = PipelinePacket::new(vec![i as u8; 128]);
            pipeline.process_with_stats(packet, stats.clone()).await.unwrap();
        }

        let final_stats = stats.read().await;
        let hit_rate = final_stats.pool_hit_rate();

        // Target: >85% pool hit rate
        assert!(
            hit_rate >= 85.0,
            "Pool hit rate {}% below target 85%",
            hit_rate
        );
    }

    #[tokio::test]
    async fn test_packet_drop_rate() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11003".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 100,
            memory_pool_size: 128,
        };

        let pipeline = PacketPipeline::new(config);
        let stats = Arc::new(RwLock::new(PipelineStats::default()));
        let total_packets = 1000;

        for i in 0..total_packets {
            let packet = PipelinePacket::new(vec![i as u8; 256]);
            let _ = pipeline.process_with_stats(packet, stats.clone()).await;
        }

        let final_stats = stats.read().await;
        let drop_rate = final_stats.drop_rate();

        // Target: <0.1% drop rate
        assert!(
            drop_rate < 0.1,
            "Drop rate {}% exceeds target 0.1%",
            drop_rate
        );
    }

    #[tokio::test]
    async fn test_concurrent_pipeline_load() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11004".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 2000,
            memory_pool_size: 2048,
        };

        let pipeline = Arc::new(PacketPipeline::new(config));
        let mut handles = vec![];
        let tasks = 10;
        let packets_per_task = 100;

        let start = Instant::now();

        for task_id in 0..tasks {
            let p = pipeline.clone();
            let handle = tokio::spawn(async move {
                for i in 0..packets_per_task {
                    let packet = PipelinePacket::new(vec![(task_id * packets_per_task + i) as u8; 512]);
                    p.process(packet).await.unwrap();
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.await.unwrap();
        }

        let elapsed = start.elapsed();
        let total_packets = tasks * packets_per_task;
        let throughput = total_packets as f64 / elapsed.as_secs_f64();

        // Should maintain high throughput under concurrent load
        assert!(
            throughput >= 15000.0,
            "Concurrent throughput {} pps below minimum 15,000 pps",
            throughput
        );
    }
}

#[cfg(test)]
mod pipeline_benchmark_tests {
    use super::*;

    #[tokio::test]
    async fn test_benchmark_suite() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11005".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 1000,
            memory_pool_size: 1024,
        };

        let benchmark = PipelineBenchmark::new(config);
        let results = benchmark.run_full_suite().await.unwrap();

        assert!(results.throughput_pps >= 20000.0);
        assert!(results.avg_latency_ms < 1.0);
        assert!(results.pool_hit_rate >= 85.0);
        assert!(results.drop_rate < 0.1);
    }

    #[tokio::test]
    async fn test_performance_targets_validation() {
        let targets = PerformanceTargets::default();
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11006".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 1000,
            memory_pool_size: 1024,
        };

        let benchmark = PipelineBenchmark::new(config);
        let results = benchmark.run_full_suite().await.unwrap();

        assert!(
            results.throughput_pps >= targets.target_throughput_pps,
            "Throughput target not met"
        );
        assert!(
            results.avg_latency_ms <= targets.max_avg_latency_ms,
            "Latency target not met"
        );
        assert!(
            results.pool_hit_rate >= targets.min_pool_hit_rate_pct,
            "Pool hit rate target not met"
        );
        assert!(
            results.drop_rate <= targets.max_drop_rate_pct,
            "Drop rate target not met"
        );
    }

    #[tokio::test]
    async fn test_stress_test() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11007".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 0,
            cover_traffic_rate: 0,
            max_concurrent_packets: 5000,
            memory_pool_size: 4096,
        };

        let pipeline = Arc::new(PacketPipeline::new(config));
        let duration = Duration::from_secs(5);
        let start = Instant::now();
        let mut total_packets = 0;

        while start.elapsed() < duration {
            let packet = PipelinePacket::new(vec![0u8; 1024]);
            if pipeline.process(packet).await.is_ok() {
                total_packets += 1;
            }
        }

        let throughput = total_packets as f64 / duration.as_secs_f64();

        // Sustained load test
        assert!(
            throughput >= 15000.0,
            "Sustained throughput {} pps below minimum",
            throughput
        );
    }
}

#[cfg(test)]
mod batch_processing_tests {
    use super::*;

    #[tokio::test]
    async fn test_batch_processing() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11008".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 1000,
            memory_pool_size: 1024,
        };

        let pipeline = PacketPipeline::new(config);
        let batch_size = 128; // From pipeline specification

        let mut batch = Vec::new();
        for i in 0..batch_size {
            batch.push(PipelinePacket::new(vec![i as u8; 256]));
        }

        let start = Instant::now();
        let results = pipeline.process_batch(batch).await.unwrap();
        let elapsed = start.elapsed();

        assert_eq!(results.len(), batch_size);
        assert!(elapsed.as_millis() < 100); // Should be very fast
    }

    #[tokio::test]
    async fn test_batch_vs_sequential() {
        let config = MixnodeConfig {
            listen_addr: "127.0.0.1:11009".parse().unwrap(),
            max_packet_size: 2048,
            processing_delay_ms: 1,
            cover_traffic_rate: 0,
            max_concurrent_packets: 500,
            memory_pool_size: 512,
        };

        let pipeline = PacketPipeline::new(config);
        let count = 100;

        // Sequential processing
        let start_seq = Instant::now();
        for i in 0..count {
            let packet = PipelinePacket::new(vec![i as u8; 256]);
            pipeline.process(packet).await.unwrap();
        }
        let sequential_time = start_seq.elapsed();

        // Batch processing
        let mut batch = Vec::new();
        for i in 0..count {
            batch.push(PipelinePacket::new(vec![i as u8; 256]));
        }

        let start_batch = Instant::now();
        pipeline.process_batch(batch).await.unwrap();
        let batch_time = start_batch.elapsed();

        // Batch should be significantly faster
        let improvement = (sequential_time.as_micros() as f64 / batch_time.as_micros() as f64 - 1.0) * 100.0;
        assert!(
            improvement >= 50.0,
            "Batch processing improvement {}% below target 50%",
            improvement
        );
    }
}