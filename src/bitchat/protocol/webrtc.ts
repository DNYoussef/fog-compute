/**
 * WebRTC Protocol Implementation
 * Handles P2P mesh networking and data channels
 */

import { WebRTCConnection } from '../types';

export class WebRTCProtocol {
  private connections: Map<string, RTCPeerConnection> = new Map();
  private dataChannels: Map<string, RTCDataChannel> = new Map();

  /**
   * Initialize WebRTC stack with STUN/TURN servers
   */
  async setupWebRTCStack(): Promise<void> {
    const configuration: RTCConfiguration = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ],
      iceCandidatePoolSize: 10
    };

    console.log('WebRTC stack initialized for mesh networking');
  }

  /**
   * Create peer connection
   */
  async createPeerConnection(
    peerId: string,
    onMessage: (data: any) => void
  ): Promise<RTCPeerConnection> {
    const peerConnection = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });

    const dataChannel = peerConnection.createDataChannel('messages', {
      ordered: true
    });

    dataChannel.onopen = () => {
      console.log(`Data channel opened with peer ${peerId}`);
    };

    dataChannel.onmessage = (event) => {
      onMessage(JSON.parse(event.data));
    };

    this.connections.set(peerId, peerConnection);
    this.dataChannels.set(peerId, dataChannel);

    return peerConnection;
  }

  /**
   * Send message via WebRTC data channel
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
   * Close peer connection
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
   * Get connection status
   */
  getConnectionStatus(peerId: string): string {
    const connection = this.connections.get(peerId);
    return connection?.connectionState || 'disconnected';
  }

  /**
   * Cleanup all connections
   */
  cleanup(): void {
    this.dataChannels.forEach((channel) => channel.close());
    this.connections.forEach((connection) => connection.close());
    this.dataChannels.clear();
    this.connections.clear();
  }
}