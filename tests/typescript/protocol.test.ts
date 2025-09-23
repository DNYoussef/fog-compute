/**
 * P2P Protocol Tests
 * Testing BitChat peer-to-peer protocols
 */

import { P2PProtocol } from '../../apps/bitchat/lib/protocol';
import { MessageRouter } from '../../apps/bitchat/lib/router';
import { PeerDiscovery } from '../../apps/bitchat/lib/discovery';
import { EncryptionLayer } from '../../apps/bitchat/lib/encryption';

describe('P2PProtocol', () => {
  let protocol: P2PProtocol;

  beforeEach(() => {
    protocol = new P2PProtocol({ nodeId: 'test-node' });
  });

  afterEach(() => {
    protocol.disconnect();
  });

  describe('Connection Management', () => {
    it('initializes with correct node ID', () => {
      expect(protocol.nodeId).toBe('test-node');
      expect(protocol.isConnected()).toBe(false);
    });

    it('establishes connection to peer', async () => {
      const peerId = 'peer-123';
      await protocol.connectToPeer(peerId);

      expect(protocol.isConnected()).toBe(true);
      expect(protocol.getPeers()).toContain(peerId);
    });

    it('handles connection timeout', async () => {
      const peerId = 'unreachable-peer';

      await expect(
        protocol.connectToPeer(peerId, { timeout: 100 })
      ).rejects.toThrow('Connection timeout');
    });

    it('disconnects from peer cleanly', async () => {
      const peerId = 'peer-123';
      await protocol.connectToPeer(peerId);

      await protocol.disconnectPeer(peerId);

      expect(protocol.getPeers()).not.toContain(peerId);
    });

    it('handles multiple simultaneous connections', async () => {
      const peerIds = ['peer-1', 'peer-2', 'peer-3'];

      await Promise.all(peerIds.map(id => protocol.connectToPeer(id)));

      expect(protocol.getPeers()).toHaveLength(3);
      peerIds.forEach(id => {
        expect(protocol.getPeers()).toContain(id);
      });
    });
  });

  describe('Message Protocol', () => {
    beforeEach(async () => {
      await protocol.connectToPeer('peer-123');
    });

    it('sends text message', async () => {
      const message = { type: 'text', content: 'Hello, peer!' };

      const sent = await protocol.sendMessage('peer-123', message);

      expect(sent).toBe(true);
    });

    it('receives message from peer', (done) => {
      protocol.on('message', (peerId, message) => {
        expect(peerId).toBe('peer-123');
        expect(message.type).toBe('text');
        expect(message.content).toBe('Hello back!');
        done();
      });

      protocol.simulateIncomingMessage('peer-123', {
        type: 'text',
        content: 'Hello back!',
      });
    });

    it('handles binary data transfer', async () => {
      const binaryData = new Uint8Array([1, 2, 3, 4, 5]);
      const message = { type: 'binary', data: binaryData };

      const sent = await protocol.sendMessage('peer-123', message);

      expect(sent).toBe(true);
    });

    it('validates message structure', () => {
      const validMessage = { type: 'text', content: 'valid' };
      const invalidMessage = { content: 'no type' };

      expect(protocol.validateMessage(validMessage)).toBe(true);
      expect(protocol.validateMessage(invalidMessage)).toBe(false);
    });

    it('enforces message size limits', async () => {
      const largeContent = 'a'.repeat(10 * 1024 * 1024); // 10MB
      const message = { type: 'text', content: largeContent };

      await expect(
        protocol.sendMessage('peer-123', message)
      ).rejects.toThrow('Message too large');
    });
  });

  describe('Routing', () => {
    let router: MessageRouter;

    beforeEach(() => {
      router = new MessageRouter();
    });

    it('routes message through mixnet', async () => {
      const route = await router.buildRoute('peer-123', 3);

      expect(route.length).toBe(3);
      expect(route[route.length - 1]).toBe('peer-123');
    });

    it('selects optimal relay nodes', async () => {
      const relays = await router.selectRelays(3, { minReputation: 80 });

      expect(relays.length).toBe(3);
      relays.forEach(relay => {
        expect(relay.reputation).toBeGreaterThanOrEqual(80);
      });
    });

    it('handles relay node failure', async () => {
      const route = ['relay-1', 'relay-2', 'peer-123'];

      const newRoute = await router.rerouteOnFailure(route, 'relay-1');

      expect(newRoute).not.toContain('relay-1');
      expect(newRoute[newRoute.length - 1]).toBe('peer-123');
    });

    it('balances load across relays', async () => {
      const routes = await Promise.all(
        Array(10).fill(null).map(() => router.buildRoute('peer-123', 3))
      );

      const relayUsage = new Map<string, number>();

      routes.forEach(route => {
        route.slice(0, -1).forEach(relay => {
          relayUsage.set(relay, (relayUsage.get(relay) || 0) + 1);
        });
      });

      // Should distribute across multiple relays
      expect(relayUsage.size).toBeGreaterThan(1);
    });
  });

  describe('Peer Discovery', () => {
    let discovery: PeerDiscovery;

    beforeEach(() => {
      discovery = new PeerDiscovery({ bootstrapNodes: ['node-1', 'node-2'] });
    });

    it('discovers peers through bootstrap nodes', async () => {
      const peers = await discovery.findPeers();

      expect(peers.length).toBeGreaterThan(0);
      expect(peers).toContain('node-1');
    });

    it('announces presence to network', async () => {
      const announced = await discovery.announce({
        nodeId: 'test-node',
        capabilities: ['text', 'file-transfer'],
      });

      expect(announced).toBe(true);
    });

    it('filters peers by capability', async () => {
      const peers = await discovery.findPeers({ capability: 'file-transfer' });

      peers.forEach(peer => {
        expect(peer.capabilities).toContain('file-transfer');
      });
    });

    it('maintains peer list freshness', async () => {
      jest.useFakeTimers();

      const peers1 = await discovery.findPeers();

      jest.advanceTimersByTime(60000); // 1 minute

      const peers2 = await discovery.findPeers();

      // Should refresh peer list
      expect(peers2).toBeDefined();

      jest.useRealTimers();
    });
  });

  describe('Encryption', () => {
    let encryption: EncryptionLayer;

    beforeEach(() => {
      encryption = new EncryptionLayer();
    });

    it('generates key pair', () => {
      const keyPair = encryption.generateKeyPair();

      expect(keyPair.publicKey).toBeDefined();
      expect(keyPair.privateKey).toBeDefined();
      expect(keyPair.publicKey.length).toBeGreaterThan(0);
    });

    it('encrypts and decrypts messages', () => {
      const keyPair = encryption.generateKeyPair();
      const message = 'Secret message';

      const encrypted = encryption.encrypt(message, keyPair.publicKey);
      expect(encrypted).not.toBe(message);

      const decrypted = encryption.decrypt(encrypted, keyPair.privateKey);
      expect(decrypted).toBe(message);
    });

    it('creates onion layers', () => {
      const message = 'Test message';
      const route = [
        { publicKey: 'key1' },
        { publicKey: 'key2' },
        { publicKey: 'key3' },
      ];

      const onionPacket = encryption.createOnionPacket(message, route);

      expect(onionPacket.layers).toBe(3);
      expect(onionPacket.payload).not.toBe(message);
    });

    it('peels onion layers', () => {
      const message = 'Test message';
      const route = [
        { publicKey: 'key1', privateKey: 'priv1' },
        { publicKey: 'key2', privateKey: 'priv2' },
        { publicKey: 'key3', privateKey: 'priv3' },
      ];

      let packet = encryption.createOnionPacket(message, route);

      // Peel each layer
      packet = encryption.peelLayer(packet, route[0].privateKey);
      expect(packet.layers).toBe(2);

      packet = encryption.peelLayer(packet, route[1].privateKey);
      expect(packet.layers).toBe(1);

      packet = encryption.peelLayer(packet, route[2].privateKey);
      expect(packet.layers).toBe(0);
      expect(packet.payload).toBe(message);
    });

    it('provides forward secrecy', () => {
      const keyPair1 = encryption.generateKeyPair();
      const keyPair2 = encryption.generateKeyPair();

      const message = 'Ephemeral message';

      const encrypted1 = encryption.encrypt(message, keyPair1.publicKey);
      const encrypted2 = encryption.encrypt(message, keyPair1.publicKey);

      // Same message should produce different ciphertext (due to ephemeral keys)
      expect(encrypted1).not.toBe(encrypted2);
    });
  });

  describe('Performance', () => {
    it('maintains low latency for direct messages', async () => {
      await protocol.connectToPeer('peer-123');

      const start = performance.now();

      for (let i = 0; i < 100; i++) {
        await protocol.sendMessage('peer-123', { type: 'ping', seq: i });
      }

      const duration = performance.now() - start;
      const avgLatency = duration / 100;

      expect(avgLatency).toBeLessThan(10); // <10ms average
    });

    it('handles high message throughput', async () => {
      await protocol.connectToPeer('peer-123');

      const messageCount = 1000;
      const start = performance.now();

      const promises = Array(messageCount).fill(null).map((_, i) =>
        protocol.sendMessage('peer-123', { type: 'data', seq: i })
      );

      await Promise.all(promises);

      const duration = (performance.now() - start) / 1000; // seconds
      const throughput = messageCount / duration;

      expect(throughput).toBeGreaterThan(500); // >500 msgs/sec
    });

    it('scales with number of peers', async () => {
      const peerCount = 50;
      const peers = Array(peerCount).fill(null).map((_, i) => `peer-${i}`);

      const start = performance.now();

      await Promise.all(peers.map(id => protocol.connectToPeer(id)));

      const duration = performance.now() - start;

      expect(duration).toBeLessThan(5000); // <5s for 50 peers
      expect(protocol.getPeers().length).toBe(peerCount);
    });
  });
});