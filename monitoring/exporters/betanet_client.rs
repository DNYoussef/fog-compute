use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::time::sleep;
use log::{debug, error, warn, info};

// Betanet API response structures
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct BetanetMetricsResponse {
    pub node_count: u64,
    pub active_connections: u64,
    pub throughput_bytes: u64,
    pub latency_ms: f64,
    pub packets_processed: u64,
    pub packets_dropped: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BetanetNodeStatus {
    pub active_nodes: u64,
    pub inactive_nodes: u64,
    pub total_nodes: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BetanetNetworkStats {
    pub bytes_transmitted: u64,
    pub bytes_received: u64,
    pub avg_latency_ms: f64,
    pub peak_throughput: u64,
}

// Circuit breaker states
#[derive(Debug, Clone, PartialEq)]
enum CircuitState {
    Closed,   // Normal operation
    Open,     // Failing, don't try requests
    HalfOpen, // Testing if service recovered
}

// Circuit breaker implementation
struct CircuitBreaker {
    state: CircuitState,
    failure_count: u32,
    last_failure_time: Option<Instant>,
    failure_threshold: u32,
    timeout_duration: Duration,
}

impl CircuitBreaker {
    fn new() -> Self {
        Self {
            state: CircuitState::Closed,
            failure_count: 0,
            last_failure_time: None,
            failure_threshold: 5,
            timeout_duration: Duration::from_secs(30),
        }
    }

    fn record_success(&mut self) {
        if self.state == CircuitState::HalfOpen {
            info!("Circuit breaker: Service recovered, closing circuit");
            self.state = CircuitState::Closed;
        }
        self.failure_count = 0;
        self.last_failure_time = None;
    }

    fn record_failure(&mut self) {
        self.failure_count += 1;
        self.last_failure_time = Some(Instant::now());

        if self.failure_count >= self.failure_threshold {
            if self.state == CircuitState::Closed {
                warn!("Circuit breaker: Opening circuit after {} failures", self.failure_count);
                self.state = CircuitState::Open;
            }
        }
    }

    fn can_attempt(&mut self) -> bool {
        match self.state {
            CircuitState::Closed => true,
            CircuitState::Open => {
                if let Some(last_failure) = self.last_failure_time {
                    if last_failure.elapsed() >= self.timeout_duration {
                        info!("Circuit breaker: Attempting recovery, entering half-open state");
                        self.state = CircuitState::HalfOpen;
                        true
                    } else {
                        false
                    }
                } else {
                    false
                }
            }
            CircuitState::HalfOpen => true,
        }
    }

    fn is_open(&self) -> bool {
        self.state == CircuitState::Open
    }
}

// Metrics cache with TTL
struct MetricsCache {
    data: Option<BetanetMetricsResponse>,
    cached_at: Option<Instant>,
    ttl: Duration,
}

impl MetricsCache {
    fn new(ttl_secs: u64) -> Self {
        Self {
            data: None,
            cached_at: None,
            ttl: Duration::from_secs(ttl_secs),
        }
    }

    fn get(&self) -> Option<BetanetMetricsResponse> {
        if let (Some(data), Some(cached_at)) = (&self.data, self.cached_at) {
            if cached_at.elapsed() < self.ttl {
                debug!("Cache hit: returning cached metrics (age: {}s)", cached_at.elapsed().as_secs());
                return Some(data.clone());
            }
            debug!("Cache expired (age: {}s)", cached_at.elapsed().as_secs());
        }
        None
    }

    fn set(&mut self, data: BetanetMetricsResponse) {
        self.data = Some(data);
        self.cached_at = Some(Instant::now());
        debug!("Cached new metrics");
    }

    fn has_stale_data(&self) -> bool {
        self.data.is_some()
    }

    fn get_stale(&self) -> Option<BetanetMetricsResponse> {
        self.data.clone()
    }
}

// Main Betanet client
pub struct BetanetClient {
    client: Client,
    base_url: String,
    timeout: Duration,
    circuit_breaker: Arc<Mutex<CircuitBreaker>>,
    cache: Arc<Mutex<MetricsCache>>,
}

impl BetanetClient {
    pub fn new(base_url: String) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            base_url,
            timeout: Duration::from_secs(5),
            circuit_breaker: Arc::new(Mutex::new(CircuitBreaker::new())),
            cache: Arc::new(Mutex::new(MetricsCache::new(10))),
        }
    }

    // Fetch aggregated metrics from Betanet
    pub async fn fetch_metrics(&self) -> Result<BetanetMetricsResponse, String> {
        // Check cache first
        if let Some(cached) = self.cache.lock().unwrap().get() {
            return Ok(cached);
        }

        // Check circuit breaker
        {
            let mut breaker = self.circuit_breaker.lock().unwrap();
            if !breaker.can_attempt() {
                warn!("Circuit breaker is open, using stale data if available");
                if let Some(stale) = self.cache.lock().unwrap().get_stale() {
                    return Ok(stale);
                }
                return Err("Circuit breaker open and no cached data available".to_string());
            }
        }

        // Try to fetch fresh metrics with retry
        match self.fetch_with_retry().await {
            Ok(metrics) => {
                self.circuit_breaker.lock().unwrap().record_success();
                self.cache.lock().unwrap().set(metrics.clone());
                Ok(metrics)
            }
            Err(e) => {
                error!("Failed to fetch metrics: {}", e);
                self.circuit_breaker.lock().unwrap().record_failure();

                // Return stale data if available
                if let Some(stale) = self.cache.lock().unwrap().get_stale() {
                    warn!("Using stale cached data due to fetch failure");
                    Ok(stale)
                } else {
                    Err(e)
                }
            }
        }
    }

    // Fetch with exponential backoff retry
    async fn fetch_with_retry(&self) -> Result<BetanetMetricsResponse, String> {
        let retry_delays = vec![
            Duration::from_secs(1),
            Duration::from_secs(2),
            Duration::from_secs(4),
        ];

        for (attempt, delay) in retry_delays.iter().enumerate() {
            match self.fetch_from_betanet().await {
                Ok(metrics) => {
                    if attempt > 0 {
                        info!("Fetch succeeded on attempt {}", attempt + 1);
                    }
                    return Ok(metrics);
                }
                Err(e) => {
                    if attempt < retry_delays.len() - 1 {
                        warn!("Attempt {} failed: {}, retrying in {}s",
                              attempt + 1, e, delay.as_secs());
                        sleep(*delay).await;
                    } else {
                        error!("All retry attempts exhausted");
                        return Err(format!("All retries failed: {}", e));
                    }
                }
            }
        }

        Err("Unexpected retry loop exit".to_string())
    }

    // Actual HTTP requests to Betanet API
    async fn fetch_from_betanet(&self) -> Result<BetanetMetricsResponse, String> {
        // Fetch from all three endpoints in parallel
        let metrics_fut = self.fetch_general_metrics();
        let nodes_fut = self.fetch_node_status();
        let stats_fut = self.fetch_network_stats();

        let (metrics_result, nodes_result, stats_result) =
            tokio::join!(metrics_fut, nodes_fut, stats_fut);

        // Aggregate results, using defaults if endpoints fail
        let node_count = nodes_result.as_ref().map(|n| n.total_nodes).unwrap_or(0);
        let active_connections = nodes_result.map(|n| n.active_nodes).unwrap_or(0);

        let (throughput_bytes, latency_ms) = match stats_result {
            Ok(stats) => (stats.bytes_transmitted, stats.avg_latency_ms),
            Err(_) => (0, 0.0),
        };

        let (packets_processed, packets_dropped) = match metrics_result {
            Ok(m) => (m.packets_processed, m.packets_dropped),
            Err(_) => (0, 0),
        };

        // Return aggregated metrics
        Ok(BetanetMetricsResponse {
            node_count,
            active_connections,
            throughput_bytes,
            latency_ms,
            packets_processed,
            packets_dropped,
        })
    }

    async fn fetch_general_metrics(&self) -> Result<BetanetMetricsResponse, String> {
        let url = format!("{}/api/v1/metrics", self.base_url);
        debug!("Fetching from {}", url);

        self.client
            .get(&url)
            .timeout(self.timeout)
            .send()
            .await
            .map_err(|e| format!("HTTP request failed: {}", e))?
            .json::<BetanetMetricsResponse>()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))
    }

    async fn fetch_node_status(&self) -> Result<BetanetNodeStatus, String> {
        let url = format!("{}/api/v1/nodes/status", self.base_url);
        debug!("Fetching from {}", url);

        self.client
            .get(&url)
            .timeout(self.timeout)
            .send()
            .await
            .map_err(|e| format!("HTTP request failed: {}", e))?
            .json::<BetanetNodeStatus>()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))
    }

    async fn fetch_network_stats(&self) -> Result<BetanetNetworkStats, String> {
        let url = format!("{}/api/v1/network/stats", self.base_url);
        debug!("Fetching from {}", url);

        self.client
            .get(&url)
            .timeout(self.timeout)
            .send()
            .await
            .map_err(|e| format!("HTTP request failed: {}", e))?
            .json::<BetanetNetworkStats>()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))
    }

    pub fn is_circuit_open(&self) -> bool {
        self.circuit_breaker.lock().unwrap().is_open()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circuit_breaker_opens_after_failures() {
        let mut breaker = CircuitBreaker::new();
        assert_eq!(breaker.state, CircuitState::Closed);

        for _ in 0..5 {
            breaker.record_failure();
        }

        assert_eq!(breaker.state, CircuitState::Open);
    }

    #[test]
    fn test_circuit_breaker_recovery() {
        let mut breaker = CircuitBreaker::new();
        breaker.state = CircuitState::HalfOpen;
        breaker.record_success();
        assert_eq!(breaker.state, CircuitState::Closed);
    }

    #[test]
    fn test_metrics_cache_ttl() {
        let mut cache = MetricsCache::new(1);
        let metrics = BetanetMetricsResponse {
            node_count: 5,
            active_connections: 10,
            throughput_bytes: 1000,
            latency_ms: 50.0,
            packets_processed: 5000,
            packets_dropped: 10,
        };

        cache.set(metrics.clone());
        assert!(cache.get().is_some());

        std::thread::sleep(Duration::from_secs(2));
        assert!(cache.get().is_none());
        assert!(cache.has_stale_data());
    }
}
