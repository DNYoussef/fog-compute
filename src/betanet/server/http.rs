// Betanet HTTP Server - Pure Tokio Implementation
// Exposes mixnode statistics and deployment endpoints

use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};

// Statistics structure
#[derive(Serialize, Clone)]
struct BetanetStatus {
    status: String,
    active_nodes: usize,
    connections: usize,
    avg_latency_ms: f64,
    packets_processed: u64,
    timestamp: String,
}

// Node deployment request
#[derive(Deserialize)]
struct DeployRequest {
    #[allow(dead_code)]
    node_type: String,
    #[allow(dead_code)]
    region: Option<String>,
}

// Node deployment response
#[derive(Serialize)]
struct DeployResponse {
    success: bool,
    node_id: Option<String>,
    status: String,
}

// Mixnode information with real-time tracking
#[derive(Clone)]
struct MixnodeInfo {
    id: String,
    status: String,
    packets_processed: u64,
    packets_forwarded: u64,
    packets_dropped: u64,
    start_time: Instant,
    latency_sum_us: u64,
    latency_count: u64,
}

// Serializable version for API responses
#[derive(Serialize)]
struct MixnodeInfoResponse {
    id: String,
    status: String,
    packets_processed: u64,
    packets_forwarded: u64,
    packets_dropped: u64,
    uptime_seconds: u64,
    avg_latency_ms: f64,
}

// Application state with real metrics
#[derive(Clone)]
struct AppState {
    mixnodes: Arc<Mutex<Vec<MixnodeInfo>>>,
    start_time: Instant,
}

impl AppState {
    fn new() -> Self {
        Self {
            mixnodes: Arc::new(Mutex::new(Vec::new())),
            start_time: Instant::now(),
        }
    }

    /// Record packet processing for a mixnode
    #[allow(dead_code)]
    fn record_packet(&self, node_id: &str, processing_time_us: u64, forwarded: bool) {
        let mut mixnodes = self.mixnodes.lock().unwrap();
        if let Some(node) = mixnodes.iter_mut().find(|n| n.id == node_id) {
            node.packets_processed += 1;
            if forwarded {
                node.packets_forwarded += 1;
            } else {
                node.packets_dropped += 1;
            }
            node.latency_sum_us += processing_time_us;
            node.latency_count += 1;
        }
    }

    /// Get total packets processed across all mixnodes
    fn total_packets_processed(&self) -> u64 {
        let mixnodes = self.mixnodes.lock().unwrap();
        mixnodes.iter().map(|n| n.packets_processed).sum()
    }

    /// Get average latency across all mixnodes
    fn avg_latency_ms(&self) -> f64 {
        let mixnodes = self.mixnodes.lock().unwrap();
        let total_latency_us: u64 = mixnodes.iter().map(|n| n.latency_sum_us).sum();
        let total_count: u64 = mixnodes.iter().map(|n| n.latency_count).sum();

        if total_count > 0 {
            (total_latency_us as f64 / total_count as f64) / 1000.0
        } else {
            0.0
        }
    }

    /// Get total active connections (estimated based on active mixnodes)
    fn total_connections(&self) -> usize {
        let mixnodes = self.mixnodes.lock().unwrap();
        mixnodes.iter().filter(|n| n.status == "active").count()
    }
}

// Simple UUID-like generator
fn uuid_simple() -> String {
    use std::time::SystemTime;
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("{:x}", now)
}

// Get current ISO 8601 timestamp
fn get_timestamp() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    format!("{}", now)
}

async fn handle_get_status(state: &AppState) -> String {
    let mixnodes = state.mixnodes.lock().unwrap();

    let status = BetanetStatus {
        status: if mixnodes.is_empty() {
            "idle".to_string()
        } else {
            "operational".to_string()
        },
        active_nodes: mixnodes.iter().filter(|n| n.status == "active").count(),
        connections: state.total_connections(),
        avg_latency_ms: state.avg_latency_ms(),
        packets_processed: state.total_packets_processed(),
        timestamp: get_timestamp(),
    };

    serde_json::to_string(&status).unwrap()
}

async fn handle_get_mixnodes(state: &AppState) -> String {
    let mixnodes = state.mixnodes.lock().unwrap();

    // Convert to response format with calculated fields
    let responses: Vec<MixnodeInfoResponse> = mixnodes
        .iter()
        .map(|node| {
            let avg_latency = if node.latency_count > 0 {
                (node.latency_sum_us as f64 / node.latency_count as f64) / 1000.0
            } else {
                0.0
            };

            MixnodeInfoResponse {
                id: node.id.clone(),
                status: node.status.clone(),
                packets_processed: node.packets_processed,
                packets_forwarded: node.packets_forwarded,
                packets_dropped: node.packets_dropped,
                uptime_seconds: node.start_time.elapsed().as_secs(),
                avg_latency_ms: avg_latency,
            }
        })
        .collect();

    serde_json::to_string(&responses).unwrap()
}

async fn handle_deploy(state: &AppState, _body: &str) -> String {
    let node_id = format!("mixnode-{}", uuid_simple());

    let new_node = MixnodeInfo {
        id: node_id.clone(),
        status: "active".to_string(),
        packets_processed: 0,
        packets_forwarded: 0,
        packets_dropped: 0,
        start_time: Instant::now(),
        latency_sum_us: 0,
        latency_count: 0,
    };

    let mut mixnodes = state.mixnodes.lock().unwrap();
    mixnodes.push(new_node);

    let response = DeployResponse {
        success: true,
        node_id: Some(node_id.clone()),
        status: "deployed".to_string(),
    };

    serde_json::to_string(&response).unwrap()
}

async fn handle_get_metrics(state: &AppState) -> String {
    let mixnodes = state.mixnodes.lock().unwrap();
    let active_count = mixnodes.iter().filter(|n| n.status == "active").count();

    format!(
        "# HELP betanet_nodes_total Total number of betanet mixnodes\n\
         # TYPE betanet_nodes_total gauge\n\
         betanet_nodes_total {}\n\
         # HELP betanet_nodes_active Number of active betanet mixnodes\n\
         # TYPE betanet_nodes_active gauge\n\
         betanet_nodes_active {}\n\
         # HELP betanet_packets_processed_total Total packets processed\n\
         # TYPE betanet_packets_processed_total counter\n\
         betanet_packets_processed_total {}\n\
         # HELP betanet_packets_forwarded_total Total packets forwarded\n\
         # TYPE betanet_packets_forwarded_total counter\n\
         betanet_packets_forwarded_total {}\n\
         # HELP betanet_packets_dropped_total Total packets dropped\n\
         # TYPE betanet_packets_dropped_total counter\n\
         betanet_packets_dropped_total {}\n\
         # HELP betanet_avg_latency_ms Average packet processing latency in milliseconds\n\
         # TYPE betanet_avg_latency_ms gauge\n\
         betanet_avg_latency_ms {}\n\
         # HELP betanet_uptime_seconds Server uptime in seconds\n\
         # TYPE betanet_uptime_seconds counter\n\
         betanet_uptime_seconds {}\n",
        mixnodes.len(),
        active_count,
        state.total_packets_processed(),
        mixnodes.iter().map(|n| n.packets_forwarded).sum::<u64>(),
        mixnodes.iter().map(|n| n.packets_dropped).sum::<u64>(),
        state.avg_latency_ms(),
        state.start_time.elapsed().as_secs()
    )
}

async fn handle_request(mut stream: TcpStream, state: AppState) {
    let mut buffer = [0; 4096];

    match stream.read(&mut buffer).await {
        Ok(n) if n > 0 => {
            let request = String::from_utf8_lossy(&buffer[..n]);
            let lines: Vec<&str> = request.lines().collect();

            if lines.is_empty() {
                return;
            }

            let request_line = lines[0];
            let parts: Vec<&str> = request_line.split_whitespace().collect();

            if parts.len() < 2 {
                return;
            }

            let method = parts[0];
            let path = parts[1];

            let (status, content_type, body) = match (method, path) {
                ("GET", "/status") => {
                    let body = handle_get_status(&state).await;
                    ("200 OK", "application/json", body)
                }
                ("GET", "/mixnodes") => {
                    let body = handle_get_mixnodes(&state).await;
                    ("200 OK", "application/json", body)
                }
                ("POST", "/deploy") => {
                    // Extract body from request
                    let body_start = request.find("\r\n\r\n").map(|i| i + 4).unwrap_or(n);
                    let req_body = &request[body_start..];
                    let body = handle_deploy(&state, req_body).await;
                    ("200 OK", "application/json", body)
                }
                ("GET", "/metrics") => {
                    let body = handle_get_metrics(&state).await;
                    ("200 OK", "text/plain; version=0.0.4", body)
                }
                _ => {
                    let body = r#"{"error":"Not Found"}"#.to_string();
                    ("404 Not Found", "application/json", body)
                }
            };

            let response = format!(
                "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{}",
                status,
                content_type,
                body.len(),
                body
            );

            let _ = stream.write_all(response.as_bytes()).await;
            let _ = stream.flush().await;
        }
        _ => {}
    }
}

pub async fn run_server() -> std::io::Result<()> {
    println!("🚀 Starting Betanet HTTP Server on 0.0.0.0:9000");

    let listener = TcpListener::bind("0.0.0.0:9000").await?;
    let state = AppState::new();

    println!("✓ Server ready - listening for connections");

    loop {
        match listener.accept().await {
            Ok((stream, _)) => {
                let state_clone = state.clone();
                tokio::spawn(async move {
                    handle_request(stream, state_clone).await;
                });
            }
            Err(e) => {
                eprintln!("Error accepting connection: {}", e);
            }
        }
    }
}
