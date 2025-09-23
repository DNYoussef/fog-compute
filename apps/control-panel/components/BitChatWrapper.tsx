'use client';

import { useState, useEffect } from 'react';

// Mock BitChat interface since we can't directly import the original
interface BitChatPeer {
  id: string;
  name: string;
  status: 'online' | 'offline';
  lastSeen: Date;
}

interface Message {
  id: string;
  sender: string;
  content: string;
  timestamp: Date;
  encrypted: boolean;
}

export default function BitChatWrapper({ userId }: { userId: string }) {
  const [peers, setPeers] = useState<BitChatPeer[]>([]);
  const [selectedPeer, setSelectedPeer] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageInput, setMessageInput] = useState('');
  const [isDiscovering, setIsDiscovering] = useState(false);

  const discoverPeers = () => {
    setIsDiscovering(true);
    setTimeout(() => {
      // Simulate peer discovery
      const mockPeers: BitChatPeer[] = [
        { id: 'peer-1', name: 'Node Alpha', status: 'online', lastSeen: new Date() },
        { id: 'peer-2', name: 'Node Beta', status: 'online', lastSeen: new Date() },
        { id: 'peer-3', name: 'Node Gamma', status: 'offline', lastSeen: new Date(Date.now() - 300000) },
      ];
      setPeers(mockPeers);
      setIsDiscovering(false);
    }, 1500);
  };

  const sendMessage = () => {
    if (!messageInput.trim() || !selectedPeer) return;

    const newMessage: Message = {
      id: `msg-${Date.now()}`,
      sender: userId,
      content: messageInput,
      timestamp: new Date(),
      encrypted: true,
    };

    setMessages(prev => [...prev, newMessage]);
    setMessageInput('');
  };

  return (
    <div className="h-full flex">
      {/* Peer List Sidebar */}
      <div className="w-64 border-r border-white/10 p-4">
        <div className="mb-4">
          <button
            onClick={discoverPeers}
            disabled={isDiscovering}
            className="w-full bg-fog-purple hover:bg-fog-purple/80 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 disabled:opacity-50"
          >
            {isDiscovering ? 'Scanning...' : 'Discover Peers'}
          </button>
        </div>

        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">Available Peers ({peers.length})</h3>
          {peers.map(peer => (
            <div
              key={peer.id}
              onClick={() => setSelectedPeer(peer.id)}
              className={`p-3 rounded-lg cursor-pointer transition-all ${
                selectedPeer === peer.id ? 'bg-fog-purple/20 ring-2 ring-fog-purple' : 'bg-white/5 hover:bg-white/10'
              }`}
            >
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full status-${peer.status === 'online' ? 'online' : 'offline'}`} />
                <span className="text-sm font-medium">{peer.name}</span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {peer.status === 'online' ? 'Online' : `Last seen ${Math.floor((Date.now() - peer.lastSeen.getTime()) / 60000)}m ago`}
              </div>
            </div>
          ))}

          {peers.length === 0 && (
            <div className="text-center text-gray-400 py-8 text-sm">
              No peers discovered.<br />Click &quot;Discover Peers&quot; to scan.
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
                  <h3 className="font-semibold">{peers.find(p => p.id === selectedPeer)?.name}</h3>
                  <div className="text-xs text-gray-400 flex items-center space-x-2">
                    <span className="w-2 h-2 bg-green-400 rounded-full"></span>
                    <span>End-to-end encrypted</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
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
                      {message.timestamp.toLocaleTimeString()} {message.encrypted && '🔒'}
                    </div>
                  </div>
                </div>
              ))}

              {messages.length === 0 && (
                <div className="text-center text-gray-400 py-8">
                  No messages yet. Start a conversation!
                </div>
              )}
            </div>

            {/* Message Input */}
            <div className="border-t border-white/10 p-4">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder="Type a message..."
                  className="flex-1 bg-white/10 border border-white/20 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-fog-purple text-white placeholder-gray-400"
                />
                <button
                  onClick={sendMessage}
                  disabled={!messageInput.trim()}
                  className="bg-fog-purple hover:bg-fog-purple/80 text-white font-semibold px-6 py-2 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <div className="text-4xl mb-4">💬</div>
              <h3 className="text-xl font-semibold mb-2">Select a peer to start messaging</h3>
              <p className="text-sm">Discover nearby peers using the &quot;Discover Peers&quot; button</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}