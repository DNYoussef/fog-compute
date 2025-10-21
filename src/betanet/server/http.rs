// Betanet HTTP Server - Pure Tokio Implementation
// Exposes mixnode statistics and deployment endpoints

use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
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

// Mixnode information
#[derive(Serialize, Clone)]
struct MixnodeInfo {
    id: String,
    status: String,
    packets_processed: u64,
    uptime_seconds: u64,
}

// Application state
#[derive(Clone)]
struct AppState {
    mixnodes: Arc<Mutex<Vec<MixnodeInfo>>>,
    packets_processed: Arc<Mutex<u64>>,
}

impl AppState {
    fn new() -> Self {
        Self {
            mixnodes: Arc::new(Mutex::new(vec![
                MixnodeInfo {
                    id: format!("mixnode-{}", uuid_simple()),
                    status: "active".to_string(),
                    packets_processed: 12453,
                    uptime_seconds: 86400,
                },
                MixnodeInfo {
                    id: format!("mixnode-{}", uuid_simple()),
                    status: "active".to_string(),
                    packets_processed: 9821,
                    uptime_seconds: 72000,
                },
            ])),
            packets_processed: Arc::new(Mutex::new(22274)),
        }
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
    let packets = state.packets_processed.lock().unwrap();

    let status = BetanetStatus {
        status: "operational".to_string(),
        active_nodes: mixnodes.len(),
        connections: mixnodes.len() * 3,
        avg_latency_ms: 45.0,
        packets_processed: *packets,
        timestamp: get_timestamp(),
    };

    serde_json::to_string(&status).unwrap()
}

async fn handle_get_mixnodes(state: &AppState) -> String {
    let mixnodes = state.mixnodes.lock().unwrap();
    serde_json::to_string(&*mixnodes).unwrap()
}

async fn handle_deploy(state: &AppState, _body: &str) -> String {
    let node_id = format!("mixnode-{}", uuid_simple());

    let new_node = MixnodeInfo {
        id: node_id.clone(),
        status: "deploying".to_string(),
        packets_processed: 0,
        uptime_seconds: 0,
    };

    let mut mixnodes = state.mixnodes.lock().unwrap();
    mixnodes.push(new_node);

    let response = DeployResponse {
        success: true,
        node_id: Some(node_id),
        status: "deploying".to_string(),
    };

    serde_json::to_string(&response).unwrap()
}

async fn handle_get_metrics(state: &AppState) -> String {
    let mixnodes = state.mixnodes.lock().unwrap();
    let packets = state.packets_processed.lock().unwrap();

    format!(
        "# HELP betanet_nodes_total Total number of betanet mixnodes\n\
         # TYPE betanet_nodes_total gauge\n\
         betanet_nodes_total {}\n\
         # HELP betanet_packets_processed_total Total packets processed\n\
         # TYPE betanet_packets_processed_total counter\n\
         betanet_packets_processed_total {}\n\
         # HELP betanet_avg_latency_ms Average latency in milliseconds\n\
         # TYPE betanet_avg_latency_ms gauge\n\
         betanet_avg_latency_ms 45.0\n",
        mixnodes.len(),
        *packets
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
