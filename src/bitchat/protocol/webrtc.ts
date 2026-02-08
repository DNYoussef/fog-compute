/**
 * WebRTC Protocol Implementation
 * Handles P2P mesh networking and data channels
 *
 * SIN-014: Adds configurable ICE/TURN servers, signaling server URL,
 * and shared configuration across all connections.
 */

import { WebRTCConnection } from '../types';

export interface WebRTCConfig {
  /** ICE servers (STUN and TURN) */
  iceServers: RTCIceServer[];
  /** ICE candidate pool size */
  iceCandidatePoolSize: number;
  /** Signaling server WebSocket URL (null = no signaling) */
  signalingServerUrl: string | null;
}

/** Default configuration with public STUN only (no TURN). */
const DEFAULT_CONFIG: WebRTCConfig = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' }
  ],
  iceCandidatePoolSize: 10,
  signalingServerUrl: null
};

export class WebRTCProtocol {
  private connections: Map<string, RTCPeerConnection> = new Map();
  private dataChannels: Map<string, RTCDataChannel> = new Map();
  private config: WebRTCConfig;
  private signalingSocket: WebSocket | null = null;
  private onMessageCallback: ((peerId: string, data: any) => void) | null = null;

  constructor(config?: Partial<WebRTCConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Get the current ICE configuration for connections.
   */
  private getRTCConfiguration(): RTCConfiguration {
    return {
      iceServers: this.config.iceServers,
      iceCandidatePoolSize: this.config.iceCandidatePoolSize
    };
  }

  /**
   * Check if TURN servers are configured.
   */
  hasTurnServers(): boolean {
    return this.config.iceServers.some(server => {
      const urls = Array.isArray(server.urls) ? server.urls : [server.urls];
      return urls.some(url => url.startsWith('turn:') || url.startsWith('turns:'));
    });
  }

  /**
   * Initialize WebRTC stack and optional signaling connection.
   */
  async setupWebRTCStack(): Promise<void> {
    // Warn if no TURN servers configured (NAT traversal will be limited)
    if (!this.hasTurnServers()) {
      console.warn(
        'WebRTC: No TURN servers configured. ' +
        'Connections may fail behind symmetric NAT.'
      );
    }

    // Connect to signaling server if configured
    if (this.config.signalingServerUrl) {
      await this.connectSignalingServer();
    }
  }

  /**
   * Connect to WebSocket signaling server.
   */
  private async connectSignalingServer(): Promise<void> {
    if (!this.config.signalingServerUrl) {
      return;
    }

    return new Promise<void>((resolve, reject) => {
      try {
        this.signalingSocket = new WebSocket(this.config.signalingServerUrl!);

        this.signalingSocket.onopen = () => {
          console.log('Signaling server connected');
          resolve();
        };

        this.signalingSocket.onerror = (event) => {
          console.error('Signaling server error:', event);
          reject(new Error('Signaling server connection failed'));
        };

        this.signalingSocket.onmessage = (event) => {
          this.handleSignalingMessage(JSON.parse(event.data));
        };

        this.signalingSocket.onclose = () => {
          console.log('Signaling server disconnected');
          this.signalingSocket = null;
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Handle signaling messages (offer/answer/ICE candidates).
   */
  private async handleSignalingMessage(message: any): Promise<void> {
    const { type, peerId, data } = message;

    switch (type) {
      case 'offer': {
        const connection = await this.handleIncomingOffer(peerId, data);
        if (connection) {
          this.connections.set(peerId, connection);
        }
        break;
      }
      case 'answer': {
        const conn = this.connections.get(peerId);
        if (conn) {
          await conn.setRemoteDescription(new RTCSessionDescription(data));
        }
        break;
      }
      case 'ice-candidate': {
        const conn = this.connections.get(peerId);
        if (conn && data) {
          await conn.addIceCandidate(new RTCIceCandidate(data));
        }
        break;
      }
    }
  }

  /**
   * Handle incoming WebRTC offer from a peer.
   */
  private async handleIncomingOffer(
    peerId: string,
    offer: RTCSessionDescriptionInit
  ): Promise<RTCPeerConnection | null> {
    try {
      const connection = new RTCPeerConnection(this.getRTCConfiguration());

      connection.ondatachannel = (event) => {
        const channel = event.channel;
        this.dataChannels.set(peerId, channel);

        channel.onmessage = (msgEvent) => {
          if (this.onMessageCallback) {
            this.onMessageCallback(peerId, JSON.parse(msgEvent.data));
          }
        };
      };

      this.setupIceCandidateForwarding(connection, peerId);

      await connection.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await connection.createAnswer();
      await connection.setLocalDescription(answer);

      this.sendSignalingMessage({
        type: 'answer',
        peerId,
        data: answer
      });

      return connection;
    } catch (error) {
      console.error('Failed to handle incoming offer:', error);
      return null;
    }
  }

  /**
   * Create peer connection using shared configuration.
   *
   * SIN-014: Uses stored config (with TURN if configured)
   * instead of inline STUN-only config.
   */
  async createPeerConnection(
    peerId: string,
    onMessage: (data: any) => void
  ): Promise<RTCPeerConnection> {
    // Use shared configuration with TURN support
    const peerConnection = new RTCPeerConnection(this.getRTCConfiguration());

    const dataChannel = peerConnection.createDataChannel('messages', {
      ordered: true
    });

    dataChannel.onopen = () => {
      console.log(`Data channel opened with peer ${peerId}`);
    };

    dataChannel.onclose = () => {
      console.log(`Data channel closed with peer ${peerId}`);
    };

    dataChannel.onmessage = (event) => {
      onMessage(JSON.parse(event.data));
    };

    // Forward ICE candidates via signaling server
    this.setupIceCandidateForwarding(peerConnection, peerId);

    // Track connection state changes
    peerConnection.onconnectionstatechange = () => {
      console.log(
        `Peer ${peerId} connection state: ${peerConnection.connectionState}`
      );
      if (peerConnection.connectionState === 'failed') {
        console.error(`Connection to ${peerId} failed`);
      }
    };

    this.connections.set(peerId, peerConnection);
    this.dataChannels.set(peerId, dataChannel);

    // Create and send offer via signaling if available
    if (this.signalingSocket?.readyState === WebSocket.OPEN) {
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      this.sendSignalingMessage({
        type: 'offer',
        peerId,
        data: offer
      });
    }

    return peerConnection;
  }

  /**
   * Set up ICE candidate forwarding for a connection.
   */
  private setupIceCandidateForwarding(
    connection: RTCPeerConnection,
    peerId: string
  ): void {
    connection.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignalingMessage({
          type: 'ice-candidate',
          peerId,
          data: event.candidate
        });
      }
    };
  }

  /**
   * Send message via signaling server WebSocket.
   */
  private sendSignalingMessage(message: any): void {
    if (this.signalingSocket?.readyState === WebSocket.OPEN) {
      this.signalingSocket.send(JSON.stringify(message));
    }
  }

  /**
   * Send message via WebRTC data channel.
   */
  async sendMessage(peerId: string, data: any): Promise<boolean> {
    const dataChannel = this.dataChannels.get(peerId);

    if (!dataChannel || dataChannel.readyState !== 'open') {
      console.error('Data channel not available for peer:', peerId);
      return false;
    }

    try {
      dataChannel.send(JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Failed to send message:', error);
      return false;
    }
  }

  /**
   * Close peer connection.
   */
  async closePeerConnection(peerId: string): Promise<void> {
    const connection = this.connections.get(peerId);
    const dataChannel = this.dataChannels.get(peerId);

    if (dataChannel) {
      dataChannel.close();
      this.dataChannels.delete(peerId);
    }

    if (connection) {
      connection.close();
      this.connections.delete(peerId);
    }
  }

  /**
   * Get connection status.
   */
  getConnectionStatus(peerId: string): string {
    const connection = this.connections.get(peerId);
    return connection?.connectionState || 'disconnected';
  }

  /**
   * Get current ICE server configuration (for diagnostics).
   */
  getIceServerConfig(): RTCIceServer[] {
    return [...this.config.iceServers];
  }

  /**
   * Cleanup all connections and signaling.
   */
  cleanup(): void {
    this.dataChannels.forEach((channel) => channel.close());
    this.connections.forEach((connection) => connection.close());
    this.dataChannels.clear();
    this.connections.clear();

    if (this.signalingSocket) {
      this.signalingSocket.close();
      this.signalingSocket = null;
    }
  }
}
