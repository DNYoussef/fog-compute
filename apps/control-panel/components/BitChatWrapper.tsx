'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  listPeers,
  sendMessage as sendMessageAPI,
  getConversation,
  type Peer,
  type Message as APIMessage
} from '@/lib/api/bitchat';

// UI-specific interfaces that match the backend types
interface BitChatPeer {
  id: string;
  name: string;
  status: 'online' | 'offline';
  lastSeen: Date;
  peerId: string;
}

interface Message {
  id: string;
  sender: string;
  content: string;
  timestamp: Date;
  encrypted: boolean;
}

interface ErrorState {
  message: string;
  type: 'connection' | 'api' | 'general';
}

export default function BitChatWrapper({ userId }: { userId: string }) {
  const [peers, setPeers] = useState<BitChatPeer[]>([]);
  const [selectedPeer, setSelectedPeer] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageInput, setMessageInput] = useState('');
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);

  // Convert backend Peer to UI BitChatPeer
  const convertPeer = useCallback((peer: Peer): BitChatPeer => {
    return {
      id: peer.id,
      peerId: peer.peer_id,
      name: peer.display_name || peer.peer_id.substring(0, 8),
      status: peer.is_online ? 'online' : 'offline',
      lastSeen: new Date(peer.last_seen),
    };
  }, []);

  // Convert backend Message to UI Message
  const convertMessage = useCallback((msg: APIMessage): Message => {
    return {
      id: msg.id,
      sender: msg.from_peer_id,
      content: msg.content,
      timestamp: new Date(msg.sent_at),
      encrypted: true, // All BitChat messages are encrypted
    };
  }, []);

  // Discover peers from the backend
  const discoverPeers = useCallback(async () => {
    setIsDiscovering(true);
    setError(null);

    try {
      const backendPeers = await listPeers(false); // Get all peers, not just online

      if (backendPeers.length === 0) {
        setError({
          message: 'No peers found in the network. Check if BitChat service is running.',
          type: 'general',
        });
      }

      const uiPeers = backendPeers.map(convertPeer);
      setPeers(uiPeers);
      setBackendAvailable(true);
    } catch (err) {
      console.error('Failed to discover peers:', err);
      setBackendAvailable(false);
      setError({
        message: 'Unable to connect to BitChat backend. Please ensure the backend service is running.',
        type: 'connection',
      });
      setPeers([]);
    } finally {
      setIsDiscovering(false);
    }
  }, [convertPeer]);

  // Load conversation when a peer is selected
  const loadConversation = useCallback(async (peerId: string) => {
    setIsLoadingMessages(true);
    setError(null);

    try {
      const conversation = await getConversation(userId, peerId, 50, 0);
      const uiMessages = conversation.map(convertMessage);
      setMessages(uiMessages);
    } catch (err) {
      console.error('Failed to load conversation:', err);
      setError({
        message: 'Failed to load conversation history.',
        type: 'api',
      });
      setMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [userId, convertMessage]);

  // Handle peer selection
  useEffect(() => {
    if (selectedPeer) {
      loadConversation(selectedPeer);
    } else {
      setMessages([]);
    }
  }, [selectedPeer, loadConversation]);

  // Send message through the API
  const sendMessage = useCallback(async () => {
    if (!messageInput.trim() || !selectedPeer || isSending) return;

    setIsSending(true);
    setError(null);

    // Optimistically add message to UI
    const optimisticMessage: Message = {
      id: `temp-${Date.now()}`,
      sender: userId,
      content: messageInput,
      timestamp: new Date(),
      encrypted: true,
    };

    setMessages(prev => [...prev, optimisticMessage]);
    const messageContent = messageInput;
    setMessageInput('');

    try {
      const sentMessage = await sendMessageAPI({
        from_peer_id: userId,
        to_peer_id: selectedPeer,
        content: messageContent,
        encryption_algorithm: 'AES-256-GCM',
        ttl: 3600,
      });

      // Replace optimistic message with real one
      setMessages(prev =>
        prev.map(msg =>
          msg.id === optimisticMessage.id
            ? convertMessage(sentMessage)
            : msg
        )
      );
    } catch (err) {
      console.error('Failed to send message:', err);

      // Remove optimistic message on failure
      setMessages(prev => prev.filter(msg => msg.id !== optimisticMessage.id));

      setError({
        message: 'Failed to send message. Please try again.',
        type: 'api',
      });

      // Restore message input
      setMessageInput(messageContent);
    } finally {
      setIsSending(false);
    }
  }, [messageInput, selectedPeer, userId, isSending, convertMessage]);

  // Initial peer discovery on mount
  useEffect(() => {
    discoverPeers();
  }, [discoverPeers]);

  return (
    <div className="h-full flex" data-testid="bitchat-wrapper">
      {/* Peer List Sidebar */}
      <div className="w-64 border-r border-white/10 p-4">
        {/* Error Banner */}
        {error && error.type === 'connection' && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg">
            <div className="text-xs font-semibold text-red-400 mb-1">Connection Error</div>
            <div className="text-xs text-red-300">{error.message}</div>
          </div>
        )}

        <div className="mb-4">
          <button
            onClick={discoverPeers}
            disabled={isDiscovering}
            className="w-full bg-fog-purple hover:bg-fog-purple/80 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 disabled:opacity-50"
          >
            {isDiscovering ? 'Scanning...' : 'Discover Peers'}
          </button>
        </div>

        {/* Backend Status Indicator */}
        {backendAvailable !== null && (
          <div className="mb-3 flex items-center space-x-2 text-xs">
            <div className={`w-2 h-2 rounded-full ${backendAvailable ? 'bg-green-400' : 'bg-red-400'}`} />
            <span className="text-gray-400">
              {backendAvailable ? 'Backend Connected' : 'Backend Offline'}
            </span>
          </div>
        )}

        <div className="space-y-2" data-testid="peer-list">
          <h3 className="text-sm font-semibold text-gray-400 mb-2" data-testid="peer-status">Available Peers ({peers.length})</h3>
          {peers.map(peer => (
            <div
              key={peer.id}
              data-testid={`peer-${peer.id}`}
              onClick={() => setSelectedPeer(peer.peerId)}
              className={`p-3 rounded-lg cursor-pointer transition-all ${
                selectedPeer === peer.peerId ? 'bg-fog-purple/20 ring-2 ring-fog-purple' : 'bg-white/5 hover:bg-white/10'
              }`}
            >
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${peer.status === 'online' ? 'bg-green-400' : 'bg-gray-400'}`} />
                <span className="text-sm font-medium">{peer.name}</span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {peer.status === 'online' ? 'Online' : `Last seen ${Math.floor((Date.now() - peer.lastSeen.getTime()) / 60000)}m ago`}
              </div>
            </div>
          ))}

          {peers.length === 0 && !isDiscovering && backendAvailable && (
            <div className="text-center text-gray-400 py-8 text-sm">
              No peers found in network.<br />Register peers in BitChat service.
            </div>
          )}

          {peers.length === 0 && !isDiscovering && !backendAvailable && (
            <div className="text-center text-gray-400 py-8 text-sm">
              Backend unavailable.<br />Please start the BitChat service.
            </div>
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {selectedPeer ? (
          <>
            {/* Chat Header */}
            <div className="border-b border-white/10 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">{peers.find(p => p.peerId === selectedPeer)?.name}</h3>
                  <div className="text-xs text-gray-400 flex items-center space-x-2">
                    <span className="w-2 h-2 bg-green-400 rounded-full"></span>
                    <span>End-to-end encrypted</span>
                  </div>
                </div>
              </div>
            </div>

            {/* API Error Toast */}
            {error && error.type === 'api' && (
              <div className="mx-4 mt-4 p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
                <div className="text-xs font-semibold text-yellow-400 mb-1">API Error</div>
                <div className="text-xs text-yellow-300">{error.message}</div>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {isLoadingMessages ? (
                <div className="text-center text-gray-400 py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-fog-purple mb-2"></div>
                  <div className="text-sm">Loading conversation...</div>
                </div>
              ) : (
                <>
                  {messages.filter(m => m.sender === selectedPeer || m.sender === userId).map(message => (
                    <div
                      key={message.id}
                      className={`flex ${message.sender === userId ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`max-w-xs px-4 py-2 rounded-lg ${
                        message.sender === userId
                          ? 'bg-fog-purple text-white'
                          : 'bg-white/10 text-white'
                      }`}>
                        <div className="text-sm">{message.content}</div>
                        <div className="text-xs opacity-70 mt-1">
                          {message.timestamp.toLocaleTimeString()} {message.encrypted && '[Encrypted]'}
                        </div>
                      </div>
                    </div>
                  ))}

                  {messages.length === 0 && !isLoadingMessages && (
                    <div className="text-center text-gray-400 py-8">
                      No messages yet. Start a conversation!
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Message Input */}
            <div className="border-t border-white/10 p-4">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !isSending && sendMessage()}
                  placeholder="Type a message..."
                  disabled={isSending}
                  className="flex-1 bg-white/10 border border-white/20 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-fog-purple text-white placeholder-gray-400 disabled:opacity-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={!messageInput.trim() || isSending}
                  className="bg-fog-purple hover:bg-fog-purple/80 text-white font-semibold px-6 py-2 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed min-w-[80px]"
                >
                  {isSending ? 'Sending...' : 'Send'}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <div className="text-4xl mb-4">[Chat Icon]</div>
              <h3 className="text-xl font-semibold mb-2">Select a peer to start messaging</h3>
              <p className="text-sm">Discover nearby peers using the &quot;Discover Peers&quot; button</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}