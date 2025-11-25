use crate::metric_collector::{MetricDataPoint, MetricCollector};
use std::collections::HashMap;
use log::{debug, info};

// Aggregation result
#[derive(Debug, Clone)]
pub struct AggregatedMetric {
    pub metric_name: String,
    pub start_time: u64,
    pub end_time: u64,
    pub count: usize,
    pub avg: f64,
    pub min: f64,
    pub max: f64,
    pub sum: f64,
    pub p50: f64,
    pub p95: f64,
    pub p99: f64,
    pub labels: HashMap<String, String>,
}

// Aggregator for computing statistics
pub struct MetricAggregator {
    collector: std::sync::Arc<MetricCollector>,
}

impl MetricAggregator {
    pub fn new(collector: std::sync::Arc<MetricCollector>) -> Self {
        Self { collector }
    }

    // Aggregate a metric over a time range
    pub fn aggregate(
        &self,
        metric_name: &str,
        start_time: u64,
        end_time: u64,
        label_filter: Option<HashMap<String, String>>,
    ) -> Option<AggregatedMetric> {
        let data_points = self.collector.get_time_series(metric_name, start_time, end_time);

        if data_points.is_empty() {
            debug!("No data points found for {} in time range", metric_name);
            return None;
        }

        // Filter by labels if provided
        let filtered_points: Vec<&MetricDataPoint> = if let Some(ref filter) = label_filter {
            data_points
                .iter()
                .filter(|p| Self::matches_labels(&p.labels, filter))
                .collect()
        } else {
            data_points.iter().collect()
        };

        if filtered_points.is_empty() {
            debug!("No data points matched label filter");
            return None;
        }

        // Extract values
        let mut values: Vec<f64> = filtered_points.iter().map(|p| p.value).collect();
        values.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let count = values.len();
        let sum: f64 = values.iter().sum();
        let avg = sum / count as f64;
        let min = *values.first().unwrap();
        let max = *values.last().unwrap();

        // Calculate percentiles
        let p50 = Self::percentile(&values, 50.0);
        let p95 = Self::percentile(&values, 95.0);
        let p99 = Self::percentile(&values, 99.0);

        // Use labels from first matching point
        let labels = filtered_points[0].labels.clone();

        info!(
            "Aggregated {}: count={}, avg={:.2}, min={:.2}, max={:.2}, p50={:.2}, p95={:.2}, p99={:.2}",
            metric_name, count, avg, min, max, p50, p95, p99
        );

        Some(AggregatedMetric {
            metric_name: metric_name.to_string(),
            start_time,
            end_time,
            count,
            avg,
            min,
            max,
            sum,
            p50,
            p95,
            p99,
            labels,
        })
    }

    // Aggregate multiple metrics at once
    pub fn aggregate_batch(
        &self,
        metric_names: &[&str],
        start_time: u64,
        end_time: u64,
    ) -> Vec<AggregatedMetric> {
        metric_names
            .iter()
            .filter_map(|name| self.aggregate(name, start_time, end_time, None))
            .collect()
    }

    // Aggregate by label (e.g., per node_id or deployment_id)
    pub fn aggregate_by_label(
        &self,
        metric_name: &str,
        start_time: u64,
        end_time: u64,
        label_key: &str,
    ) -> HashMap<String, AggregatedMetric> {
        let data_points = self.collector.get_time_series(metric_name, start_time, end_time);

        // Group by label value
        let mut grouped: HashMap<String, Vec<MetricDataPoint>> = HashMap::new();
        for point in data_points {
            if let Some(label_value) = point.labels.get(label_key) {
                grouped
                    .entry(label_value.clone())
                    .or_insert_with(Vec::new)
                    .push(point);
            }
        }

        // Aggregate each group
        let mut results = HashMap::new();
        for (label_value, points) in grouped {
            if let Some(aggregated) = Self::aggregate_points(&points, metric_name, start_time, end_time) {
                results.insert(label_value, aggregated);
            }
        }

        results
    }

    // Rolling window aggregation (e.g., last 5 minutes, last hour, last day)
    pub fn rolling_window(
        &self,
        metric_name: &str,
        window_seconds: u64,
    ) -> Option<AggregatedMetric> {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let start_time = now.saturating_sub(window_seconds);
        self.aggregate(metric_name, start_time, now, None)
    }

    // Calculate rate of change (for counters)
    pub fn calculate_rate(
        &self,
        metric_name: &str,
        window_seconds: u64,
    ) -> Option<f64> {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let start_time = now.saturating_sub(window_seconds);
        let data_points = self.collector.get_time_series(metric_name, start_time, now);

        if data_points.len() < 2 {
            return None;
        }

        let first = data_points.first().unwrap();
        let last = data_points.last().unwrap();

        let value_delta = last.value - first.value;
        let time_delta = (last.timestamp - first.timestamp) as f64;

        if time_delta > 0.0 {
            Some(value_delta / time_delta)
        } else {
            None
        }
    }

    // Export aggregated metrics for monitoring systems
    pub fn export_prometheus_format(&self, aggregated: &AggregatedMetric) -> String {
        let mut output = String::new();
        let labels_str = Self::format_labels(&aggregated.labels);

        // Export multiple statistics as separate metrics
        output.push_str(&format!(
            "{}{}{{stat=\"avg\"}} {}\n",
            aggregated.metric_name, labels_str, aggregated.avg
        ));
        output.push_str(&format!(
            "{}{}{{stat=\"min\"}} {}\n",
            aggregated.metric_name, labels_str, aggregated.min
        ));
        output.push_str(&format!(
            "{}{}{{stat=\"max\"}} {}\n",
            aggregated.metric_name, labels_str, aggregated.max
        ));
        output.push_str(&format!(
            "{}{}{{stat=\"p50\"}} {}\n",
            aggregated.metric_name, labels_str, aggregated.p50
        ));
        output.push_str(&format!(
            "{}{}{{stat=\"p95\"}} {}\n",
            aggregated.metric_name, labels_str, aggregated.p95
        ));
        output.push_str(&format!(
            "{}{}{{stat=\"p99\"}} {}\n",
            aggregated.metric_name, labels_str, aggregated.p99
        ));

        output
    }

    // Helper: Calculate percentile
    fn percentile(sorted_values: &[f64], p: f64) -> f64 {
        if sorted_values.is_empty() {
            return 0.0;
        }

        let n = sorted_values.len();
        let index = (p / 100.0 * (n - 1) as f64).ceil() as usize;
        sorted_values[index.min(n - 1)]
    }

    // Helper: Check if labels match filter
    fn matches_labels(labels: &HashMap<String, String>, filter: &HashMap<String, String>) -> bool {
        filter.iter().all(|(k, v)| labels.get(k) == Some(v))
    }

    // Helper: Aggregate a set of data points
    fn aggregate_points(
        points: &[MetricDataPoint],
        metric_name: &str,
        start_time: u64,
        end_time: u64,
    ) -> Option<AggregatedMetric> {
        if points.is_empty() {
            return None;
        }

        let mut values: Vec<f64> = points.iter().map(|p| p.value).collect();
        values.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let count = values.len();
        let sum: f64 = values.iter().sum();
        let avg = sum / count as f64;
        let min = *values.first().unwrap();
        let max = *values.last().unwrap();

        let p50 = Self::percentile(&values, 50.0);
        let p95 = Self::percentile(&values, 95.0);
        let p99 = Self::percentile(&values, 99.0);

        Some(AggregatedMetric {
            metric_name: metric_name.to_string(),
            start_time,
            end_time,
            count,
            avg,
            min,
            max,
            sum,
            p50,
            p95,
            p99,
            labels: points[0].labels.clone(),
        })
    }

    // Helper: Format labels for Prometheus
    fn format_labels(labels: &HashMap<String, String>) -> String {
        if labels.is_empty() {
            return String::new();
        }

        let label_pairs: Vec<String> = labels
            .iter()
            .map(|(k, v)| format!("{}=\"{}\"", k, v))
            .collect();

        format!("{{{}}}", label_pairs.join(","))
    }
}

// Pre-defined aggregation windows
pub struct AggregationWindows;

impl AggregationWindows {
    pub const LAST_5_MINUTES: u64 = 300;
    pub const LAST_15_MINUTES: u64 = 900;
    pub const LAST_HOUR: u64 = 3600;
    pub const LAST_6_HOURS: u64 = 21600;
    pub const LAST_24_HOURS: u64 = 86400;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::metric_collector::{MetricCollector, MetricType};

    #[test]
    fn test_percentile_calculation() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];

        assert_eq!(MetricAggregator::percentile(&values, 50.0), 5.0);
        assert_eq!(MetricAggregator::percentile(&values, 95.0), 10.0);
        assert_eq!(MetricAggregator::percentile(&values, 99.0), 10.0);
    }

    #[test]
    fn test_aggregation() {
        let collector = std::sync::Arc::new(MetricCollector::new(100, 15));

        collector.register_metric(
            "test_metric".to_string(),
            "Test".to_string(),
            MetricType::Gauge,
            None,
        );

        // Record some test data
        let mut labels = HashMap::new();
        labels.insert("node_id".to_string(), "node-1".to_string());

        for i in 0..10 {
            collector.record_metric("test_metric", (i * 10) as f64, labels.clone());
        }

        let aggregator = MetricAggregator::new(collector);
        let result = aggregator.aggregate("test_metric", 0, u64::MAX, None);

        assert!(result.is_some());
        let agg = result.unwrap();
        assert_eq!(agg.count, 10);
        assert_eq!(agg.min, 0.0);
        assert_eq!(agg.max, 90.0);
        assert_eq!(agg.avg, 45.0);
    }

    #[test]
    fn test_label_filtering() {
        let mut labels1 = HashMap::new();
        labels1.insert("node_id".to_string(), "node-1".to_string());
        labels1.insert("env".to_string(), "prod".to_string());

        let mut labels2 = HashMap::new();
        labels2.insert("node_id".to_string(), "node-2".to_string());

        let mut filter = HashMap::new();
        filter.insert("node_id".to_string(), "node-1".to_string());

        assert!(MetricAggregator::matches_labels(&labels1, &filter));
        assert!(!MetricAggregator::matches_labels(&labels2, &filter));
    }

    #[test]
    fn test_prometheus_export() {
        let labels = HashMap::new();
        let agg = AggregatedMetric {
            metric_name: "test_metric".to_string(),
            start_time: 0,
            end_time: 100,
            count: 10,
            avg: 50.0,
            min: 10.0,
            max: 90.0,
            sum: 500.0,
            p50: 50.0,
            p95: 85.0,
            p99: 89.0,
            labels,
        };

        let collector = std::sync::Arc::new(MetricCollector::new(100, 15));
        let aggregator = MetricAggregator::new(collector);
        let output = aggregator.export_prometheus_format(&agg);

        assert!(output.contains("test_metric{stat=\"avg\"} 50"));
        assert!(output.contains("test_metric{stat=\"p95\"} 85"));
    }
}
