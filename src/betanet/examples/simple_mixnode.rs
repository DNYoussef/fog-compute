//! Simple mixnode example
//!
//! Demonstrates basic usage of the betanet pipeline

use betanet::{PacketPipeline, PipelinePacket};
use bytes::Bytes;
use std::sync::atomic::Ordering;
use std::time::Duration;
use tokio::time::sleep;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    println!("=== Betanet Simple Mixnode ===\n");

    // Create pipeline with 4 workers
    let mut pipeline = PacketPipeline::new(4);

    println!("Starting pipeline...");
    pipeline.start().await?;

    // Submit test packets
    println!("Submitting 1000 test packets...");
    for i in 0..1000 {
        let packet_data = Bytes::from(vec![0u8; 1200]); // Typical packet size
        let packet = if i % 10 == 0 {
            // Every 10th packet is high priority
            PipelinePacket::with_priority(packet_data, 1)
        } else {
            PipelinePacket::new(packet_data)
        };

        pipeline.submit_packet(packet).await?;

        // Small delay every 100 packets
        if i % 100 == 0 {
            sleep(Duration::from_millis(10)).await;
        }
    }

    println!("All packets submitted. Waiting for processing...\n");
    sleep(Duration::from_secs(1)).await;

    // Get processed packets
    let processed = pipeline.get_processed_packets(1000);
    println!("Retrieved {} processed packets", processed.len());

    // Print statistics
    let stats = pipeline.stats();
    let packets_processed = stats.packets_processed.load(Ordering::Relaxed);
    let packets_dropped = stats.packets_dropped.load(Ordering::Relaxed);
    let avg_time_ns = stats.avg_processing_time_ns();
    let pool_hit_rate = pipeline.memory_pool_hit_rate();
    let (input_depth, output_depth) = pipeline.queue_depths();

    println!("\nPipeline Statistics:");
    println!("  Packets Processed:     {}", packets_processed);
    println!("  Packets Dropped:       {}", packets_dropped);
    println!(
        "  Avg Processing Time:   {:.2}μs",
        avg_time_ns as f64 / 1000.0
    );
    println!("  Memory Pool Hit Rate:  {:.1}%", pool_hit_rate);
    println!("  Input Queue Depth:     {}", input_depth);
    println!("  Output Queue Depth:    {}", output_depth);

    // Memory pool stats
    let (allocated, reused) = pipeline.memory_pool_stats();
    println!("\nMemory Pool:");
    println!("  Buffers Allocated:     {}", allocated);
    println!("  Buffers Reused:        {}", reused);

    // Stop pipeline
    println!("\nStopping pipeline...");
    pipeline.stop().await?;

    println!("Done!");

    Ok(())
}