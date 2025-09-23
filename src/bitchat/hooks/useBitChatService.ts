/**
 * BitChat Service Hook
 * P2P Messaging with Bluetooth Low Energy and WebRTC
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { BitChatPeer, P2PMessage, MessagingState, BitChatServiceHook, EncryptionStatus, MeshStatus } from '../types';
import { WebRTCProtocol } from '../protocol/webrtc';
import { BluetoothProtocol } from '../protocol/bluetooth';
import { ChaCha20Encryption } from '../encryption/chacha20';

export const useBitChatService = (userId: string): BitChatServiceHook => {
  const [messagingState, setMessagingState] = useState<MessagingState>({
    peers: [],
    conversations: {},
    activeChat: undefined,
    isDiscovering: false
  });

  const [meshStatus, setMeshStatus] = useState<MeshStatus>({
    health: 'poor',
    connectivity: 0,
    latency: 0,
    redundancy: 0
  });

  const [encryptionStatus, setEncryptionStatus] = useState<EncryptionStatus>({
    enabled: true,
    protocol: 'ChaCha20-Poly1305',
    keyRotationInterval: 3600000
  });

  const [isInitialized, setIsInitialized] = useState(false);

  const webrtcProtocol = useRef<WebRTCProtocol>(new WebRTCProtocol());
  const bluetoothProtocol = useRef<BluetoothProtocol>(new BluetoothProtocol());
  const encryption = useRef<ChaCha20Encryption>(new ChaCha20Encryption());
  const discoveryInterval = useRef<NodeJS.Timeout | null>(null);

  // Initialize BitChat service
  useEffect(() => {
    const initializeBitChat = async () => {
      try {
        await webrtcProtocol.current.setupWebRTCStack();
        await bluetoothProtocol.current.initializeBluetoothLEDiscovery();
        setIsInitialized(true);
        startPeerDiscovery();
      } catch (error) {
        console.error('Failed to initialize BitChat service:', error);
      }
    };

    initializeBitChat();

    return () => {
      cleanup();
    };
  }, [userId]);

  const startPeerDiscovery = (): void => {
    if (discoveryInterval.current) {
      clearInterval(discoveryInterval.current);
    }

    discoveryInterval.current = setInterval(() => {
      discoverPeers();
    }, 30000);
  };

  const discoverPeers = useCallback(async (): Promise<void> => {
    if (messagingState.isDiscovering) return;

    setMessagingState(prev => ({ ...prev, isDiscovering: true }));

    try {
      const discoveredPeers = await bluetoothProtocol.current.discoverPeers();
      await new Promise(resolve => setTimeout(resolve, 2000));

      setMessagingState(prev => ({
        ...prev,
        peers: [
          ...prev.peers,
          ...discoveredPeers.filter(p => !prev.peers.find(existing => existing.id === p.id))
        ],
        isDiscovering: false
      }));

      updateMeshStatus();
    } catch (error) {
      console.error('Peer discovery failed:', error);
      setMessagingState(prev => ({ ...prev, isDiscovering: false }));
    }
  }, [messagingState.isDiscovering]);

  const connectToPeer = useCallback(async (peerId: string): Promise<boolean> => {
    try {
      const peer = messagingState.peers.find(p => p.id === peerId);
      if (!peer) return false;

      await webrtcProtocol.current.createPeerConnection(
        peerId,
        handleIncomingMessage
      );

      setMessagingState(prev => ({
        ...prev,
        peers: prev.peers.map(p =>
          p.id === peerId ? { ...p, status: 'online' } : p
        )
      }));

      updateMeshStatus();
      return true;
    } catch (error) {
      console.error(`Failed to connect to peer ${peerId}:`, error);
      return false;
    }
  }, [messagingState.peers]);

  const disconnectFromPeer = useCallback(async (peerId: string): Promise<boolean> => {
    try {
      await webrtcProtocol.current.closePeerConnection(peerId);

      setMessagingState(prev => ({
        ...prev,
        peers: prev.peers.map(p =>
          p.id === peerId ? { ...p, status: 'offline' } : p
        )
      }));

      updateMeshStatus();
      return true;
    } catch (error) {
      console.error(`Failed to disconnect from peer ${peerId}:`, error);
      return false;
    }
  }, []);

  const sendMessage = useCallback(async (message: P2PMessage): Promise<boolean> => {
    try {
      let messageData = message;

      if (encryptionStatus.enabled) {
        messageData = await encryption.current.encryptMessage(message);
      }

      const success = await webrtcProtocol.current.sendMessage(
        message.recipient,
        messageData
      );

      if (success) {
        setMessagingState(prev => ({
          ...prev,
          conversations: {
            ...prev.conversations,
            [message.recipient]: [
              ...(prev.conversations[message.recipient] || []),
              { ...message, deliveryStatus: 'sent' }
            ]
          }
        }));
      }

      return success;
    } catch (error) {
      console.error('Failed to send message:', error);
      return false;
    }
  }, [encryptionStatus.enabled]);

  const handleIncomingMessage = useCallback((message: P2PMessage) => {
    setMessagingState(prev => ({
      ...prev,
      conversations: {
        ...prev.conversations,
        [message.sender]: [
          ...(prev.conversations[message.sender] || []),
          { ...message, deliveryStatus: 'delivered' }
        ]
      }
    }));
  }, []);

  const updateMeshStatus = (): void => {
    const connectedPeers = messagingState.peers.filter(p => p.status === 'online');
    const connectivity = connectedPeers.length / Math.max(messagingState.peers.length, 1);

    setMeshStatus({
      health: connectivity > 0.7 ? 'good' : connectivity > 0.3 ? 'fair' : 'poor',
      connectivity: connectivity * 100,
      latency: Math.random() * 100 + 50,
      redundancy: Math.min(connectedPeers.length, 3)
    });
  };

  const cleanup = (): void => {
    if (discoveryInterval.current) {
      clearInterval(discoveryInterval.current);
    }
    webrtcProtocol.current.cleanup();
  };

  return {
    messagingState,
    sendMessage,
    discoverPeers,
    connectToPeer,
    disconnectFromPeer,
    meshStatus,
    encryptionStatus,
    isInitialized
  };
};