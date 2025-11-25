use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, RwLock};
use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Deserialize, Serialize};
use log::{debug, info, warn};

// Time-series data point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricDataPoint {
    pub timestamp: u64,
    pub value: f64,
    pub labels: HashMap<String, String>,
}

// Metric metadata
#[derive(Debug, Clone)]
pub struct MetricMetadata {
    pub name: String,
    pub description: String,
    pub metric_type: MetricType,
    pub unit: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum MetricType {
    Gauge,      // Instantaneous value
    Counter,    // Monotonically increasing
    Histogram,  // Distribution
}

// Time-series storage with ring buffer (last 24 hours at 15s intervals = 5760 points)
pub struct TimeSeriesBuffer {
    data: VecDeque<MetricDataPoint>,
    max_size: usize,
    name: String,
}

impl TimeSeriesBuffer {
    pub fn new(name: String, max_size: usize) -> Self {
        Self {
            data: VecDeque::with_capacity(max_size),
            max_size,
            name,
        }
    }

    pub fn push(&mut self, point: MetricDataPoint) {
        if self.data.len() >= self.max_size {
            self.data.pop_front();
            debug!("Ring buffer for {} full, removed oldest data point", self.name);
        }
        self.data.push_back(point);
    }

    pub fn get_range(&self, start_time: u64, end_time: u64) -> Vec<MetricDataPoint> {
        self.data
            .iter()
            .filter(|p| p.timestamp >= start_time && p.timestamp <= end_time)
            .cloned()
            .collect()
    }

    pub fn get_all(&self) -> Vec<MetricDataPoint> {
        self.data.iter().cloned().collect()
    }

    pub fn get_latest(&self) -> Option<&MetricDataPoint> {
        self.data.back()
    }

    pub fn len(&self) -> usize {
        self.data.len()
    }

    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
}

// Main metric collector
pub struct MetricCollector {
    // Time-series storage
    time_series: Arc<RwLock<HashMap<String, TimeSeriesBuffer>>>,

    // Metric metadata
    metadata: Arc<RwLock<HashMap<String, MetricMetadata>>>,

    // Configuration
    buffer_size: usize,
    collection_interval_secs: u64,
}

impl MetricCollector {
    pub fn new(buffer_size: usize, collection_interval_secs: u64) -> Self {
        info!(
            "Creating metric collector: buffer_size={}, interval={}s",
            buffer_size, collection_interval_secs
        );

        let collector = Self {
            time_series: Arc::new(RwLock::new(HashMap::new())),
            metadata: Arc::new(RwLock::new(HashMap::new())),
            buffer_size,
            collection_interval_secs,
        };

        // Register default metrics
        collector.register_default_metrics();

        collector
    }

    // Register default system metrics
    fn register_default_metrics(&self) {
        let default_metrics = vec![
            // Node metrics
            ("node_cpu_usage", "CPU usage percentage", MetricType::Gauge, Some("percent")),
            ("node_memory_usage", "Memory usage percentage", MetricType::Gauge, Some("percent")),
            ("node_disk_usage", "Disk usage percentage", MetricType::Gauge, Some("percent")),
            ("node_network_io", "Network I/O bytes per second", MetricType::Gauge, Some("bytes/sec")),

            // Deployment metrics
            ("deployment_replica_count", "Number of replicas", MetricType::Gauge, Some("count")),
            ("deployment_request_rate", "Request rate", MetricType::Gauge, Some("req/sec")),
            ("deployment_error_rate", "Error rate", MetricType::Gauge, Some("errors/sec")),
            ("deployment_latency", "Request latency", MetricType::Histogram, Some("ms")),

            // Betanet metrics
            ("betanet_packets_processed", "Packets processed", MetricType::Counter, Some("packets")),
            ("betanet_packets_dropped", "Packets dropped", MetricType::Counter, Some("packets")),
            ("betanet_latency", "Network latency", MetricType::Histogram, Some("ms")),
            ("betanet_connections", "Active connections", MetricType::Gauge, Some("count")),

            // System metrics
            ("system_uptime", "System uptime", MetricType::Counter, Some("seconds")),
            ("system_total_nodes", "Total nodes in cluster", MetricType::Gauge, Some("count")),
            ("system_active_deployments", "Active deployments", MetricType::Gauge, Some("count")),
        ];

        for (name, description, metric_type, unit) in default_metrics {
            self.register_metric(
                name.to_string(),
                description.to_string(),
                metric_type,
                unit.map(|s| s.to_string()),
            );
        }

        info!("Registered {} default metrics", self.metadata.read().unwrap().len());
    }

    // Register a custom metric
    pub fn register_metric(
        &self,
        name: String,
        description: String,
        metric_type: MetricType,
        unit: Option<String>,
    ) {
        let metadata = MetricMetadata {
            name: name.clone(),
            description,
            metric_type,
            unit,
        };

        self.metadata.write().unwrap().insert(name.clone(), metadata);

        // Initialize time-series buffer
        self.time_series
            .write()
            .unwrap()
            .insert(name.clone(), TimeSeriesBuffer::new(name, self.buffer_size));

        debug!("Registered metric: {}", name);
    }

    // Record a metric value
    pub fn record_metric(&self, name: &str, value: f64, labels: HashMap<String, String>) {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let point = MetricDataPoint {
            timestamp,
            value,
            labels,
        };

        if let Some(buffer) = self.time_series.write().unwrap().get_mut(name) {
            buffer.push(point);
            debug!("Recorded {}: {}", name, value);
        } else {
            warn!("Attempted to record unknown metric: {}", name);
        }
    }

    // Get latest value for a metric
    pub fn get_latest(&self, name: &str) -> Option<MetricDataPoint> {
        self.time_series
            .read()
            .unwrap()
            .get(name)
            .and_then(|buffer| buffer.get_latest().cloned())
    }

    // Get time-series data for a metric
    pub fn get_time_series(&self, name: &str, start_time: u64, end_time: u64) -> Vec<MetricDataPoint> {
        self.time_series
            .read()
            .unwrap()
            .get(name)
            .map(|buffer| buffer.get_range(start_time, end_time))
            .unwrap_or_default()
    }

    // Get all data for a metric
    pub fn get_all_data(&self, name: &str) -> Vec<MetricDataPoint> {
        self.time_series
            .read()
            .unwrap()
            .get(name)
            .map(|buffer| buffer.get_all())
            .unwrap_or_default()
    }

    // Get metric metadata
    pub fn get_metadata(&self, name: &str) -> Option<MetricMetadata> {
        self.metadata.read().unwrap().get(name).cloned()
    }

    // List all registered metrics
    pub fn list_metrics(&self) -> Vec<String> {
        self.metadata.read().unwrap().keys().cloned().collect()
    }

    // Get buffer statistics
    pub fn get_buffer_stats(&self) -> HashMap<String, usize> {
        self.time_series
            .read()
            .unwrap()
            .iter()
            .map(|(name, buffer)| (name.clone(), buffer.len()))
            .collect()
    }

    // Collect metrics from multiple sources
    pub async fn collect_from_sources(&self, sources: &[MetricSource]) {
        for source in sources {
            match source.fetch_metrics().await {
                Ok(metrics) => {
                    for (name, value, labels) in metrics {
                        self.record_metric(&name, value, labels);
                    }
                }
                Err(e) => {
                    warn!("Failed to collect metrics from {}: {}", source.name(), e);
                }
            }
        }
    }
}

// Trait for metric sources
#[async_trait::async_trait]
pub trait MetricSource: Send + Sync {
    fn name(&self) -> &str;
    async fn fetch_metrics(&self) -> Result<Vec<(String, f64, HashMap<String, String>)>, String>;
}

// Node metric source
pub struct NodeMetricSource {
    node_id: String,
}

impl NodeMetricSource {
    pub fn new(node_id: String) -> Self {
        Self { node_id }
    }
}

#[async_trait::async_trait]
impl MetricSource for NodeMetricSource {
    fn name(&self) -> &str {
        "node_metrics"
    }

    async fn fetch_metrics(&self) -> Result<Vec<(String, f64, HashMap<String, String>)>, String> {
        // In production, this would query actual system metrics
        // For now, return simulated data
        let mut labels = HashMap::new();
        labels.insert("node_id".to_string(), self.node_id.clone());

        Ok(vec![
            ("node_cpu_usage".to_string(), 45.5, labels.clone()),
            ("node_memory_usage".to_string(), 62.3, labels.clone()),
            ("node_disk_usage".to_string(), 78.1, labels.clone()),
            ("node_network_io".to_string(), 1024000.0, labels),
        ])
    }
}

// Deployment metric source
pub struct DeploymentMetricSource {
    deployment_id: String,
}

impl DeploymentMetricSource {
    pub fn new(deployment_id: String) -> Self {
        Self { deployment_id }
    }
}

#[async_trait::async_trait]
impl MetricSource for DeploymentMetricSource {
    fn name(&self) -> &str {
        "deployment_metrics"
    }

    async fn fetch_metrics(&self) -> Result<Vec<(String, f64, HashMap<String, String>)>, String> {
        let mut labels = HashMap::new();
        labels.insert("deployment_id".to_string(), self.deployment_id.clone());

        Ok(vec![
            ("deployment_replica_count".to_string(), 3.0, labels.clone()),
            ("deployment_request_rate".to_string(), 125.5, labels.clone()),
            ("deployment_error_rate".to_string(), 0.5, labels.clone()),
            ("deployment_latency".to_string(), 45.2, labels),
        ])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_time_series_buffer_ring() {
        let mut buffer = TimeSeriesBuffer::new("test".to_string(), 3);

        for i in 0..5 {
            buffer.push(MetricDataPoint {
                timestamp: i,
                value: i as f64,
                labels: HashMap::new(),
            });
        }

        assert_eq!(buffer.len(), 3);
        assert_eq!(buffer.get_latest().unwrap().value, 4.0);
    }

    #[test]
    fn test_metric_registration() {
        let collector = MetricCollector::new(100, 15);

        collector.register_metric(
            "custom_metric".to_string(),
            "A custom metric".to_string(),
            MetricType::Gauge,
            Some("units".to_string()),
        );

        let metadata = collector.get_metadata("custom_metric");
        assert!(metadata.is_some());
        assert_eq!(metadata.unwrap().name, "custom_metric");
    }

    #[test]
    fn test_metric_recording() {
        let collector = MetricCollector::new(100, 15);

        collector.register_metric(
            "test_metric".to_string(),
            "Test".to_string(),
            MetricType::Gauge,
            None,
        );

        let mut labels = HashMap::new();
        labels.insert("test".to_string(), "value".to_string());

        collector.record_metric("test_metric", 42.0, labels);

        let latest = collector.get_latest("test_metric");
        assert!(latest.is_some());
        assert_eq!(latest.unwrap().value, 42.0);
    }

    #[tokio::test]
    async fn test_node_metric_source() {
        let source = NodeMetricSource::new("node-1".to_string());
        let metrics = source.fetch_metrics().await.unwrap();

        assert!(!metrics.is_empty());
        assert_eq!(metrics[0].2.get("node_id").unwrap(), "node-1");
    }
}
