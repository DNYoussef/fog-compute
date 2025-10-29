'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import BitChat components to avoid SSR issues
const BitChatInterface = dynamic(
  () => import('@/components/BitChatWrapper'),
  { ssr: false }
);

export default function BitChatPage() {
  const [userId, setUserId] = useState<string>('');
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    document.title = 'BitChat | Fog Compute';
  }, []);

  useEffect(() => {
    // Generate or retrieve user ID
    const storedUserId = localStorage.getItem('bitchat-user-id');
    if (storedUserId) {
      setUserId(storedUserId);
    } else {
      const newUserId = `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('bitchat-user-id', newUserId);
      setUserId(newUserId);
    }
    setIsInitialized(true);
  }, []);

  if (!isInitialized) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-fog-purple mx-auto mb-4"></div>
          <p className="text-gray-400">Initializing BitChat...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold text-fog-purple">BitChat Mesh Network</h1>
        <p className="text-gray-400 mt-2">
          Secure P2P messaging with end-to-end encryption and mesh networking
        </p>
        <div className="mt-4 flex items-center space-x-4">
          <div className="text-sm">
            <span className="text-gray-400">Your ID: </span>
            <span className="font-mono bg-white/10 px-2 py-1 rounded">{userId}</span>
          </div>
        </div>
      </div>

      {/* BitChat Interface */}
      <div className="glass rounded-xl overflow-hidden" style={{ minHeight: '600px' }}>
        <BitChatInterface userId={userId} />
      </div>

      {/* Features Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass rounded-lg p-4">
          <h3 className="font-semibold text-fog-purple mb-2">End-to-End Encryption</h3>
          <p className="text-sm text-gray-400">
            All messages are encrypted using ChaCha20 with secure key exchange
          </p>
        </div>
        <div className="glass rounded-lg p-4">
          <h3 className="font-semibold text-fog-purple mb-2">Mesh Networking</h3>
          <p className="text-sm text-gray-400">
            Decentralized P2P communication using Bluetooth Low Energy and WebRTC
          </p>
        </div>
        <div className="glass rounded-lg p-4">
          <h3 className="font-semibold text-fog-purple mb-2">Offline Capable</h3>
          <p className="text-sm text-gray-400">
            Messages are queued and delivered when peers reconnect to the mesh
          </p>
        </div>
      </div>
    </div>
  );
}