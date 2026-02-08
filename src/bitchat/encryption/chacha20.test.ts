/**
 * Tests for ChaCha20 (NaCl) encryption (Phase 4).
 *
 * SIN-012: Real authenticated encryption using tweetnacl.
 * SIN-013: No mock peers in BLE discovery.
 * SIN-014: WebRTC configurable ICE/TURN.
 */
import nacl from 'tweetnacl';
import naclUtil from 'tweetnacl-util';
import { ChaCha20Encryption } from './chacha20';

describe('ChaCha20Encryption (SIN-012)', () => {
  let aliceEncryption: ChaCha20Encryption;
  let bobEncryption: ChaCha20Encryption;

  beforeEach(async () => {
    aliceEncryption = new ChaCha20Encryption();
    bobEncryption = new ChaCha20Encryption();
  });

  describe('key generation', () => {
    it('exports a real base64 public key (not mock)', async () => {
      const pubKey = await aliceEncryption.exportPublicKey();

      // Must be valid base64
      expect(() => naclUtil.decodeBase64(pubKey)).not.toThrow();

      // Must be 32 bytes (X25519 public key)
      const decoded = naclUtil.decodeBase64(pubKey);
      expect(decoded.length).toBe(32);

      // Must NOT be mock-public-key-*
      expect(pubKey).not.toContain('mock');
    });

    it('generates different keys each time after rotation', async () => {
      const key1 = await aliceEncryption.exportPublicKey();
      await aliceEncryption.rotateKey();
      const key2 = await aliceEncryption.exportPublicKey();

      expect(key1).not.toBe(key2);
    });
  });

  describe('peer key exchange', () => {
    it('imports and tracks peer public keys', async () => {
      const bobPubKey = await bobEncryption.exportPublicKey();

      await aliceEncryption.importPeerKey('bob', bobPubKey);

      expect(aliceEncryption.hasPeerKey('bob')).toBe(true);
      expect(aliceEncryption.hasPeerKey('unknown')).toBe(false);
    });

    it('rejects invalid key length', async () => {
      await expect(
        aliceEncryption.importPeerKey('bad', naclUtil.encodeBase64(new Uint8Array(16)))
      ).rejects.toThrow('Invalid public key length');
    });
  });

  describe('encrypt/decrypt round trip', () => {
    it('encrypts and decrypts a message correctly', async () => {
      // Exchange keys
      const alicePub = await aliceEncryption.exportPublicKey();
      const bobPub = await bobEncryption.exportPublicKey();

      await aliceEncryption.importPeerKey('bob', bobPub);
      await bobEncryption.importPeerKey('alice', alicePub);

      // Alice encrypts
      const plainMessage = {
        id: 'msg-001',
        sender: 'alice',
        recipient: 'bob',
        content: 'Hello from Alice!',
        timestamp: new Date(),
        type: 'user' as const,
        encrypted: false,
        deliveryStatus: 'sent' as const,
      };

      const encrypted = await aliceEncryption.encryptMessage(plainMessage);

      // Ciphertext should differ from plaintext
      expect(encrypted.encrypted).toBe(true);
      expect(encrypted.content).not.toBe('Hello from Alice!');
      expect(encrypted.content).not.toContain('[ENCRYPTED]');

      // Bob decrypts
      const decrypted = await bobEncryption.decryptMessage(encrypted);

      expect(decrypted.encrypted).toBe(false);
      expect(decrypted.content).toBe('Hello from Alice!');
    });

    it('fails to decrypt with wrong key', async () => {
      const alicePub = await aliceEncryption.exportPublicKey();
      const bobPub = await bobEncryption.exportPublicKey();

      await aliceEncryption.importPeerKey('bob', bobPub);

      // Eve has different keys
      const eveEncryption = new ChaCha20Encryption();
      const evePub = await eveEncryption.exportPublicKey();
      await eveEncryption.importPeerKey('alice', alicePub);

      // Alice encrypts for Bob
      const encrypted = await aliceEncryption.encryptMessage({
        id: 'msg-002',
        sender: 'alice',
        recipient: 'bob',
        content: 'Secret message',
        timestamp: new Date(),
        type: 'user' as const,
        encrypted: false,
        deliveryStatus: 'sent' as const,
      });

      // Eve tries to decrypt (should fail - different shared key)
      // Eve needs to claim message is from alice
      encrypted.sender = 'alice';
      await expect(eveEncryption.decryptMessage(encrypted)).rejects.toThrow(
        'Decryption failed'
      );
    });

    it('requires peer key before encrypting', async () => {
      const message = {
        id: 'msg-003',
        sender: 'alice',
        recipient: 'unknown-peer',
        content: 'test',
        timestamp: new Date(),
        type: 'user' as const,
        encrypted: false,
        deliveryStatus: 'sent' as const,
      };

      await expect(aliceEncryption.encryptMessage(message)).rejects.toThrow(
        'No public key for recipient'
      );
    });
  });

  describe('non-encrypted passthrough', () => {
    it('returns unencrypted messages as-is', async () => {
      const message = {
        id: 'msg-004',
        sender: 'alice',
        recipient: 'bob',
        content: 'plain text',
        timestamp: new Date(),
        type: 'user' as const,
        encrypted: false,
        deliveryStatus: 'sent' as const,
      };

      const result = await aliceEncryption.decryptMessage(message);
      expect(result.content).toBe('plain text');
      expect(result.encrypted).toBe(false);
    });
  });
});
