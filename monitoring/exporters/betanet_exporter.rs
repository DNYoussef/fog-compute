use prometheus::{
    Histogram, HistogramOpts, IntCounter, IntGauge, Opts, Registry,
};
use std::sync::Arc;
use std::collections::HashMap;
use tokio::time::{self, Duration};
use warp::Filter;
use log::{info, error, warn};

mod betanet_client;
use betanet_client::BetanetClient;

mod metric_collector;
use metric_collector::{MetricCollector, NodeMetricSource, DeploymentMetricSource, MetricSource};

mod aggregator;
use aggregator::{MetricAggregator, AggregationWindows};

#[derive(Clone)]
pub struct BetanetMetrics {
    // Network metrics
    pub connected_peers: IntGauge,
    pub total_messages: IntCounter,
    pub bytes_transmitted: IntCounter,
    pub bytes_received: IntCounter,
    pub packets_dropped: IntCounter,

    // Mixnode metrics
    pub mixnode_failures: IntCounter,
    pub mixnode_active: IntGauge,
    pub routing_failures: IntCounter,

    // Performance metrics
    pub message_latency: Histogram,
    pub routing_latency: Histogram,
    pub circuit_build_time: Histogram,

    // VRF metrics
    pub vrf_verifications: IntCounter,
    pub vrf_failures: IntCounter,

    registry: Registry,
}

impl BetanetMetrics {
    pub fn new() -> Result<Self, prometheus::Error> {
        let registry = Registry::new();

        let connected_peers = IntGauge::with_opts(
            Opts::new("betanet_connected_peers", "Number of connected peers")
        )?;

        let total_messages = IntCounter::with_opts(
            Opts::new("betanet_messages_total", "Total messages processed")
        )?;

        let bytes_transmitted = IntCounter::with_opts(
            Opts::new("betanet_bytes_transmitted_total", "Total bytes transmitted")
        )?;

        let bytes_received = IntCounter::with_opts(
            Opts::new("betanet_bytes_received_total", "Total bytes received")
        )?;

        let packets_dropped = IntCounter::with_opts(
            Opts::new("betanet_packets_dropped_total", "Total packets dropped")
        )?;

        let mixnode_failures = IntCounter::with_opts(
            Opts::new("betanet_mixnode_failures_total", "Total mixnode failures")
        )?;

        let mixnode_active = IntGauge::with_opts(
            Opts::new("betanet_mixnode_active", "Number of active mixnodes")
        )?;

        let routing_failures = IntCounter::with_opts(
            Opts::new("betanet_routing_failures_total", "Total routing failures")
        )?;

        let message_latency = Histogram::with_opts(
            HistogramOpts::new("betanet_message_latency_seconds", "Message latency in seconds")
                .buckets(vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])
        )?;

        let routing_latency = Histogram::with_opts(
            HistogramOpts::new("betanet_routing_latency_seconds", "Routing latency in seconds")
                .buckets(vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0])
        )?;

        let circuit_build_time = Histogram::with_opts(
            HistogramOpts::new("betanet_circuit_build_seconds", "Circuit build time in seconds")
                .buckets(vec![0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0])
        )?;

        let vrf_verifications = IntCounter::with_opts(
            Opts::new("betanet_vrf_verifications_total", "Total VRF verifications")
        )?;

        let vrf_failures = IntCounter::with_opts(
            Opts::new("betanet_vrf_failures_total", "Total VRF verification failures")
        )?;

        registry.register(Box::new(connected_peers.clone()))?;
        registry.register(Box::new(total_messages.clone()))?;
        registry.register(Box::new(bytes_transmitted.clone()))?;
        registry.register(Box::new(bytes_received.clone()))?;
        registry.register(Box::new(packets_dropped.clone()))?;
        registry.register(Box::new(mixnode_failures.clone()))?;
        registry.register(Box::new(mixnode_active.clone()))?;
        registry.register(Box::new(routing_failures.clone()))?;
        registry.register(Box::new(message_latency.clone()))?;
        registry.register(Box::new(routing_latency.clone()))?;
        registry.register(Box::new(circuit_build_time.clone()))?;
        registry.register(Box::new(vrf_verifications.clone()))?;
        registry.register(Box::new(vrf_failures.clone()))?;

        Ok(Self {
            connected_peers,
            total_messages,
            bytes_transmitted,
            bytes_received,
            packets_dropped,
            mixnode_failures,
            mixnode_active,
            routing_failures,
            message_latency,
            routing_latency,
            circuit_build_time,
            vrf_verifications,
            vrf_failures,
            registry,
        })
    }

    pub fn registry(&self) -> &Registry {
        &self.registry
    }
}

#[tokio::main]
async fn main() {
    // Initialize logger
    env_logger::init();

    info!("Starting Betanet metrics exporter with metric collection");

    let metrics = Arc::new(BetanetMetrics::new().expect("Failed to create metrics"));
    let metrics_clone = metrics.clone();

    // Initialize Betanet client
    let betanet_client = Arc::new(BetanetClient::new("http://localhost:9000".to_string()));
    let client_clone = betanet_client.clone();

    // Initialize metric collector (5760 data points = 24h at 15s intervals)
    let collector = Arc::new(MetricCollector::new(5760, 15));
    let collector_clone = collector.clone();
    let collector_clone2 = collector.clone();

    // Initialize aggregator
    let aggregator = Arc::new(MetricAggregator::new(collector.clone()));
    let aggregator_clone = aggregator.clone();

    // Spawn Betanet metrics collection task
    tokio::spawn(async move {
        let mut interval = time::interval(Duration::from_secs(15));

        loop {
            interval.tick().await;
            collect_betanet_metrics(&metrics_clone, &client_clone).await;
        }
    });

    // Spawn additional metrics collection task (node & deployment metrics)
    tokio::spawn(async move {
        let mut interval = time::interval(Duration::from_secs(15));

        // Create metric sources
        let sources: Vec<Box<dyn MetricSource>> = vec![
            Box::new(NodeMetricSource::new("node-1".to_string())),
            Box::new(NodeMetricSource::new("node-2".to_string())),
            Box::new(DeploymentMetricSource::new("deployment-1".to_string())),
        ];

        loop {
            interval.tick().await;
            info!("Collecting metrics from additional sources");
            collector_clone.collect_from_sources(&sources).await;
        }
    });

    // Metrics endpoint (Prometheus format)
    let metrics_route = warp::path("metrics")
        .map(move || {
            use prometheus::Encoder;
            let encoder = prometheus::TextEncoder::new();
            let metric_families = metrics.registry().gather();
            let mut buffer = Vec::new();
            encoder.encode(&metric_families, &mut buffer).unwrap();

            warp::http::Response::builder()
                .header("Content-Type", "text/plain; version=0.0.4")
                .body(buffer)
        });

    // Aggregated metrics endpoint
    let agg_metrics_route = warp::path("metrics")
        .and(warp::path("aggregated"))
        .map(move || {
            let mut output = String::new();

            // Aggregate last 5 minutes of key metrics
            let metric_names = vec![
                "node_cpu_usage",
                "node_memory_usage",
                "deployment_latency",
                "betanet_latency",
            ];

            for metric_name in metric_names {
                if let Some(agg) = aggregator_clone.rolling_window(metric_name, AggregationWindows::LAST_5_MINUTES) {
                    output.push_str(&aggregator_clone.export_prometheus_format(&agg));
                }
            }

            warp::http::Response::builder()
                .header("Content-Type", "text/plain; version=0.0.4")
                .body(output)
        });

    // Stats endpoint (JSON format with buffer statistics)
    let stats_route = warp::path("stats")
        .map(move || {
            let buffer_stats = collector_clone2.get_buffer_stats();
            let metric_list = collector_clone2.list_metrics();

            warp::reply::json(&serde_json::json!({
                "buffer_stats": buffer_stats,
                "registered_metrics": metric_list,
                "total_metrics": metric_list.len()
            }))
        });

    // Health endpoint
    let health_route = warp::path("health")
        .map(|| warp::reply::json(&serde_json::json!({"status": "healthy"})));

    let routes = metrics_route
        .or(agg_metrics_route)
        .or(stats_route)
        .or(health_route);

    println!("Betanet metrics exporter listening on 0.0.0.0:9200");
    println!("Endpoints:");
    println!("  - http://0.0.0.0:9200/metrics (Prometheus format)");
    println!("  - http://0.0.0.0:9200/metrics/aggregated (Aggregated metrics)");
    println!("  - http://0.0.0.0:9200/stats (Buffer statistics)");
    println!("  - http://0.0.0.0:9200/health (Health check)");
    warp::serve(routes).run(([0, 0, 0, 0], 9200)).await;
}

async fn collect_betanet_metrics(
    metrics: &Arc<BetanetMetrics>,
    client: &Arc<BetanetClient>,
) {
    info!("Collecting Betanet metrics...");

    match client.fetch_metrics().await {
        Ok(betanet_metrics) => {
            // Update Prometheus metrics with real Betanet data
            metrics.connected_peers.set(betanet_metrics.node_count as i64);
            metrics.bytes_transmitted.inc_by(betanet_metrics.throughput_bytes);
            metrics.packets_dropped.inc_by(betanet_metrics.packets_dropped);
            metrics.mixnode_active.set(betanet_metrics.active_connections as i64);

            // Record latency histogram
            metrics.message_latency.observe(betanet_metrics.latency_ms / 1000.0);

            info!(
                "Updated metrics: nodes={}, connections={}, throughput={} bytes, latency={}ms",
                betanet_metrics.node_count,
                betanet_metrics.active_connections,
                betanet_metrics.throughput_bytes,
                betanet_metrics.latency_ms
            );

            // Check circuit breaker status
            if client.is_circuit_open() {
                warn!("Circuit breaker is OPEN - service may be degraded");
            }
        }
        Err(e) => {
            error!("Failed to fetch Betanet metrics: {}", e);
            // Metrics remain at last known values, which is graceful degradation
        }
    }
}