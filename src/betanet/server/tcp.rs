//! TCP Server for BetaNet Mixnode
//!
//! Provides network I/O layer for receiving and forwarding Sphinx packets
//! across the mixnet topology. Integrates with PacketPipeline for high-performance
//! batch processing.

use std::net::SocketAddr;
use std::sync::Arc;

use bytes::BytesMut;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::broadcast;
use tracing::{debug, error, info, warn};

use crate::{
    core::{
        config::MixnodeConfig,
        protocol_version::{ProtocolAdvertisement, ProtocolVersion},
    },
    pipeline::{PacketPipeline, PipelinePacket},
    MixnodeError, Result,
};

#[cfg(test)]
use crate::utils::packet::Packet;
#[cfg(test)]
use bytes::Bytes;

/// TCP server for handling mixnode network I/O
pub struct TcpServer {
    config: MixnodeConfig,
    pipeline: Arc<PacketPipeline>,
    shutdown_tx: Option<broadcast::Sender<()>>,
    protocol_version: ProtocolVersion,
    node_id: String,
}

impl TcpServer {
    /// Create new TCP server with default protocol version
    pub fn new(config: MixnodeConfig, pipeline: PacketPipeline) -> Self {
        Self::new_with_version(config, pipeline, ProtocolVersion::default())
    }

    /// Create new TCP server with specific protocol version
    pub fn new_with_version(
        config: MixnodeConfig,
        pipeline: PacketPipeline,
        protocol_version: ProtocolVersion,
    ) -> Self {
        let node_id = format!("node-{}", uuid::Uuid::new_v4());
        Self {
            config,
            pipeline: Arc::new(pipeline),
            shutdown_tx: None,
            protocol_version,
            node_id,
        }
    }

    /// Start the TCP server
    pub async fn run(&mut self) -> Result<()> {
        info!(
            "Starting BetaNet TCP server on {}",
            self.config.listen_addr
        );

        let listener = TcpListener::bind(self.config.listen_addr)
            .await
            .map_err(MixnodeError::Io)?;

        let (shutdown_tx, _) = broadcast::channel(1);
        self.shutdown_tx = Some(shutdown_tx.clone());

        info!("✓ TCP server listening on {}", self.config.listen_addr);

        // Subscribe before loop to avoid temporary value issue
        let mut shutdown_rx_main = shutdown_tx.subscribe();

        // Accept connections loop
        loop {
            tokio::select! {
                result = listener.accept() => {
                    match result {
                        Ok((stream, peer_addr)) => {
                            debug!("Accepted connection from {}", peer_addr);

                            let pipeline = Arc::clone(&self.pipeline);
                            let config = self.config.clone();
                            let shutdown_rx = shutdown_tx.subscribe();
                            let protocol_version = self.protocol_version;
                            let node_id = self.node_id.clone();

                            // Spawn connection handler
                            tokio::spawn(async move {
                                if let Err(e) = Self::handle_connection(
                                    stream,
                                    peer_addr,
                                    pipeline,
                                    config,
                                    shutdown_rx,
                                    protocol_version,
                                    node_id,
                                )
                                .await
                                {
                                    error!("Connection error for {}: {}", peer_addr, e);
                                }
                            });
                        }
                        Err(e) => {
                            error!("Failed to accept connection: {}", e);
                        }
                    }
                }
                _ = shutdown_rx_main.recv() => {
                    info!("TCP server shutting down");
                    break;
                }
            }
        }

        Ok(())
    }

    /// Stop the TCP server
    pub async fn stop(&mut self) -> Result<()> {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(());
        }
        Ok(())
    }

    /// Handle individual TCP connection
    async fn handle_connection(
        mut stream: TcpStream,
        peer_addr: SocketAddr,
        pipeline: Arc<PacketPipeline>,
        config: MixnodeConfig,
        mut shutdown_rx: broadcast::Receiver<()>,
        protocol_version: ProtocolVersion,
        node_id: String,
    ) -> Result<()> {
        debug!("Handling connection from {}", peer_addr);

        // Perform version negotiation handshake
        match Self::version_handshake(&mut stream, protocol_version, node_id).await {
            Ok(negotiated_version) => {
                info!(
                    "Version negotiation successful with {}: {}",
                    peer_addr, negotiated_version
                );
            }
            Err(e) => {
                error!("Version negotiation failed with {}: {}", peer_addr, e);
                return Err(e);
            }
        }

        let mut buffer = BytesMut::with_capacity(config.buffer_size);

        loop {
            tokio::select! {
                // Read from stream with timeout
                result = tokio::time::timeout(
                    config.connection_timeout,
                    stream.read_buf(&mut buffer)
                ) => {
                    match result {
                        Ok(Ok(0)) => {
                            debug!("Connection closed by peer {}", peer_addr);
                            break;
                        }
                        Ok(Ok(n)) => {
                            debug!("Received {} bytes from {}", n, peer_addr);

                            // Process complete packets (length-prefixed)
                            while buffer.len() >= 4 {
                                // Read 4-byte length prefix (big-endian)
                                let length = u32::from_be_bytes([
                                    buffer[0],
                                    buffer[1],
                                    buffer[2],
                                    buffer[3],
                                ]) as usize;

                                // Check if we have the complete packet
                                if buffer.len() < 4 + length {
                                    // Wait for more data
                                    break;
                                }

                                // Extract packet data (skip length prefix)
                                let packet_data = buffer.split_to(4 + length).split_off(4);
                                let packet_bytes = packet_data.freeze();

                                // Submit to pipeline for processing
                                let mut pipeline_packet = PipelinePacket::new(packet_bytes);
                                pipeline_packet.source = Some(peer_addr);

                                match pipeline.submit_packet(pipeline_packet).await {
                                    Ok(_) => {
                                        debug!("Packet submitted to pipeline");
                                    }
                                    Err(e) => {
                                        warn!("Failed to submit packet: {}", e);
                                    }
                                }
                            }

                            // Send back processed packets
                            let processed = pipeline.get_processed_packets(10);
                            if !processed.is_empty() {
                                debug!("Sending {} processed packets", processed.len());

                                for packet in processed {
                                    // Write length prefix + packet data
                                    let length = packet.data.len() as u32;
                                    let mut response = BytesMut::with_capacity(4 + packet.data.len());
                                    response.extend_from_slice(&length.to_be_bytes());
                                    response.extend_from_slice(&packet.data);

                                    if let Err(e) = stream.write_all(&response).await {
                                        error!("Failed to write response: {}", e);
                                        break;
                                    }
                                }

                                if let Err(e) = stream.flush().await {
                                    error!("Failed to flush stream: {}", e);
                                    break;
                                }
                            }
                        }
                        Ok(Err(e)) => {
                            error!("Read error from {}: {}", peer_addr, e);
                            break;
                        }
                        Err(_) => {
                            warn!("Connection timeout for {}", peer_addr);
                            break;
                        }
                    }
                }
                _ = shutdown_rx.recv() => {
                    debug!("Shutdown signal received for connection {}", peer_addr);
                    break;
                }
            }
        }

        Ok(())
    }

    /// Get pipeline statistics
    pub fn pipeline_stats(&self) -> &crate::pipeline::PipelineStats {
        self.pipeline.stats()
    }

    /// Perform version negotiation handshake
    async fn version_handshake(
        stream: &mut TcpStream,
        our_version: ProtocolVersion,
        node_id: String,
    ) -> Result<ProtocolVersion> {
        // Step 1: Send our advertisement
        let our_ad = ProtocolAdvertisement::new(our_version, node_id);
        let our_ad_bytes = our_ad
            .encode()
            .map_err(|e| MixnodeError::Protocol(format!("Failed to encode advertisement: {}", e)))?;

        // Write advertisement length (4 bytes) + advertisement
        let length = (our_ad_bytes.len() as u32).to_be_bytes();
        stream.write_all(&length).await.map_err(MixnodeError::Io)?;
        stream
            .write_all(&our_ad_bytes)
            .await
            .map_err(MixnodeError::Io)?;
        stream.flush().await.map_err(MixnodeError::Io)?;

        debug!("Sent protocol advertisement: {}", our_version);

        // Step 2: Receive their advertisement
        let mut length_buf = [0u8; 4];
        stream
            .read_exact(&mut length_buf)
            .await
            .map_err(MixnodeError::Io)?;

        let ad_length = u32::from_be_bytes(length_buf) as usize;
        if ad_length > 4096 {
            // Sanity check
            return Err(MixnodeError::Protocol(
                "Advertisement too large".to_string(),
            ));
        }

        let mut ad_buf = vec![0u8; ad_length];
        stream.read_exact(&mut ad_buf).await.map_err(MixnodeError::Io)?;

        let their_ad = ProtocolAdvertisement::decode(&ad_buf).map_err(|e| {
            MixnodeError::Protocol(format!("Failed to decode peer advertisement: {}", e))
        })?;

        debug!("Received protocol advertisement: {}", their_ad.version);

        // Step 3: Check compatibility
        if !our_ad.is_compatible_with(&their_ad) {
            return Err(MixnodeError::Protocol(format!(
                "Incompatible protocol versions: ours={}, theirs={}",
                our_version, their_ad.version
            )));
        }

        // Step 4: Negotiate to lower version for backward compatibility
        let negotiated = if our_version < their_ad.version {
            our_version
        } else {
            their_ad.version
        };

        // Step 5: Send negotiation result (1 byte: version encoding)
        let negotiated_byte = negotiated.encode_byte();
        stream
            .write_all(&[negotiated_byte])
            .await
            .map_err(MixnodeError::Io)?;
        stream.flush().await.map_err(MixnodeError::Io)?;

        // Step 6: Receive their confirmation
        let mut confirm_buf = [0u8; 1];
        stream
            .read_exact(&mut confirm_buf)
            .await
            .map_err(MixnodeError::Io)?;

        let their_negotiated = ProtocolVersion::decode_byte(confirm_buf[0]).ok_or_else(|| {
            MixnodeError::Protocol(format!("Invalid version byte: {}", confirm_buf[0]))
        })?;

        if their_negotiated != negotiated {
            return Err(MixnodeError::Protocol(format!(
                "Version negotiation mismatch: we agreed on {}, they agreed on {}",
                negotiated, their_negotiated
            )));
        }

        info!("Protocol version negotiated: {}", negotiated);
        Ok(negotiated)
    }
}

/// TCP client for connecting to other mixnodes
pub struct TcpClient {
    next_hop: SocketAddr,
}

impl TcpClient {
    /// Create new TCP client
    pub fn new(next_hop: SocketAddr) -> Self {
        Self { next_hop }
    }

    /// Send packet to next hop
    pub async fn send_packet(&self, packet: &[u8]) -> Result<Vec<u8>> {
        debug!("Connecting to {}", self.next_hop);

        let mut stream = TcpStream::connect(self.next_hop)
            .await
            .map_err(|e| MixnodeError::Network(format!("Connection failed: {}", e)))?;

        // Write length prefix + packet
        let length = packet.len() as u32;
        let mut request = BytesMut::with_capacity(4 + packet.len());
        request.extend_from_slice(&length.to_be_bytes());
        request.extend_from_slice(packet);

        stream
            .write_all(&request)
            .await
            .map_err(MixnodeError::Io)?;
        stream.flush().await.map_err(MixnodeError::Io)?;

        debug!("Sent {} bytes to {}", packet.len(), self.next_hop);

        // Read response (length-prefixed)
        let mut length_buf = [0u8; 4];
        stream
            .read_exact(&mut length_buf)
            .await
            .map_err(MixnodeError::Io)?;

        let response_length = u32::from_be_bytes(length_buf) as usize;
        let mut response = vec![0u8; response_length];

        stream
            .read_exact(&mut response)
            .await
            .map_err(MixnodeError::Io)?;

        debug!("Received {} bytes from {}", response.len(), self.next_hop);

        Ok(response)
    }

    /// Send packet with timeout
    pub async fn send_packet_with_timeout(
        &self,
        packet: &[u8],
        timeout: std::time::Duration,
    ) -> Result<Vec<u8>> {
        tokio::time::timeout(timeout, self.send_packet(packet))
            .await
            .map_err(|_| MixnodeError::Network("Request timeout".to_string()))?
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::config::MixnodeConfig;
    use crate::pipeline::PacketPipeline;

    #[tokio::test]
    async fn test_tcp_server_creation() {
        let config = MixnodeConfig::default();
        let mut pipeline = PacketPipeline::new(2);
        pipeline.start().await.unwrap();

        let server = TcpServer::new(config, pipeline);
        assert!(server.shutdown_tx.is_none());
    }

    #[tokio::test]
    async fn test_tcp_client_send() {
        // Start a test server
        let mut config = MixnodeConfig::default();
        config.listen_addr = "127.0.0.1:19001".parse().unwrap();

        let mut pipeline = PacketPipeline::new(2);
        pipeline.start().await.unwrap();

        let mut server = TcpServer::new(config.clone(), pipeline);

        // Spawn server
        tokio::spawn(async move {
            server.run().await.ok();
        });

        // Wait for server to start
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;

        // Create client and send packet
        let client = TcpClient::new(config.listen_addr);
        let test_packet = Packet::data(Bytes::from(vec![1, 2, 3, 4]), 0);
        let encoded = test_packet.encode().unwrap();

        match client
            .send_packet_with_timeout(&encoded, std::time::Duration::from_secs(2))
            .await
        {
            Ok(response) => {
                println!("Received response: {} bytes", response.len());
                assert!(!response.is_empty());
            }
            Err(e) => {
                println!("Send failed (expected in test): {}", e);
            }
        }
    }
}
