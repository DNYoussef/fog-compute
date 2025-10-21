// Betanet HTTP Server Binary
// Run with: cargo run --bin http_server

use betanet::server::http;

#[tokio::main]
async fn main() -> std::io::Result<()> {
    println!("╔═══════════════════════════════════════════╗");
    println!("║   Betanet Privacy Network HTTP Server    ║");
    println!("║   Port: 9000                              ║");
    println!("╚═══════════════════════════════════════════╝");

    http::run_server().await
}
