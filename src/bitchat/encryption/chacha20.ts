/**
 * Authenticated Encryption for P2P Messages
 *
 * Uses tweetnacl (NaCl) for real authenticated encryption:
 * - X25519 key exchange (Curve25519 Diffie-Hellman)
 * - XSalsa20-Poly1305 authenticated encryption
 *
 * SIN-012: Replaces fake string-prefix "encryption" with real crypto.
 */

import { P2PMessage } from '../types';
import nacl from 'tweetnacl';
import naclUtil from 'tweetnacl-util';

export class ChaCha20Encryption {
  private keyPair: nacl.BoxKeyPair | null = null;
  private peerPublicKeys: Map<string, Uint8Array> = new Map();
  private sharedKeys: Map<string, Uint8Array> = new Map();
  private keyRotationInterval: number;

  constructor(keyRotationInterval: number = 3600000) {
    this.keyRotationInterval = keyRotationInterval;
  }

  /**
   * Encrypt message with X25519-XSalsa20-Poly1305.
   * Requires peer public key to be imported first.
   */
  async encryptMessage(message: P2PMessage): Promise<P2PMessage> {
    if (!this.keyPair) {
      await this.generateKey();
    }

    const recipientKey = this.peerPublicKeys.get(message.recipient);
    if (!recipientKey) {
      throw new Error(
        `No public key for recipient ${message.recipient}. ` +
        'Import peer key before encrypting.'
      );
    }

    // Get or compute shared key for this peer
    let sharedKey = this.sharedKeys.get(message.recipient);
    if (!sharedKey) {
      sharedKey = nacl.box.before(recipientKey, this.keyPair!.secretKey);
      this.sharedKeys.set(message.recipient, sharedKey);
    }

    // Generate random nonce (24 bytes for XSalsa20)
    const nonce = nacl.randomBytes(nacl.box.nonceLength);

    // Encrypt content
    const messageBytes = naclUtil.decodeUTF8(message.content);
    const encrypted = nacl.box.after(messageBytes, nonce, sharedKey);

    if (!encrypted) {
      throw new Error('Encryption failed');
    }

    // Pack nonce + ciphertext as base64
    const packed = new Uint8Array(nonce.length + encrypted.length);
    packed.set(nonce);
    packed.set(encrypted, nonce.length);

    return {
      ...message,
      content: naclUtil.encodeBase64(packed),
      encrypted: true
    };
  }

  /**
   * Decrypt message with X25519-XSalsa20-Poly1305.
   */
  async decryptMessage(message: P2PMessage): Promise<P2PMessage> {
    if (!message.encrypted) {
      return message;
    }

    if (!this.keyPair) {
      throw new Error('No key pair available for decryption');
    }

    const senderKey = this.peerPublicKeys.get(message.sender);
    if (!senderKey) {
      throw new Error(
        `No public key for sender ${message.sender}. ` +
        'Import peer key before decrypting.'
      );
    }

    // Get or compute shared key for this peer
    let sharedKey = this.sharedKeys.get(message.sender);
    if (!sharedKey) {
      sharedKey = nacl.box.before(senderKey, this.keyPair.secretKey);
      this.sharedKeys.set(message.sender, sharedKey);
    }

    // Unpack nonce + ciphertext
    const packed = naclUtil.decodeBase64(message.content);
    const nonce = packed.slice(0, nacl.box.nonceLength);
    const ciphertext = packed.slice(nacl.box.nonceLength);

    // Decrypt and verify
    const decrypted = nacl.box.open.after(ciphertext, nonce, sharedKey);

    if (!decrypted) {
      throw new Error(
        'Decryption failed - message may be tampered or wrong key'
      );
    }

    return {
      ...message,
      content: naclUtil.encodeUTF8(decrypted),
      encrypted: false
    };
  }

  /**
   * Generate X25519 key pair for authenticated encryption.
   */
  private async generateKey(): Promise<void> {
    this.keyPair = nacl.box.keyPair();
    // Clear cached shared keys on rotation
    this.sharedKeys.clear();
  }

  /**
   * Rotate encryption key pair.
   * Clears cached shared keys - peers must re-exchange.
   */
  async rotateKey(): Promise<void> {
    await this.generateKey();
  }

  /**
   * Export public key as base64 for peer exchange.
   */
  async exportPublicKey(): Promise<string> {
    if (!this.keyPair) {
      await this.generateKey();
    }

    return naclUtil.encodeBase64(this.keyPair!.publicKey);
  }

  /**
   * Import a peer's public key (base64 encoded).
   */
  async importPeerKey(peerId: string, publicKeyBase64: string): Promise<void> {
    const publicKey = naclUtil.decodeBase64(publicKeyBase64);

    if (publicKey.length !== nacl.box.publicKeyLength) {
      throw new Error(
        `Invalid public key length: expected ${nacl.box.publicKeyLength}, ` +
        `got ${publicKey.length}`
      );
    }

    this.peerPublicKeys.set(peerId, publicKey);
    // Invalidate cached shared key for this peer
    this.sharedKeys.delete(peerId);
  }

  /**
   * Check if we have a public key for a peer.
   */
  hasPeerKey(peerId: string): boolean {
    return this.peerPublicKeys.has(peerId);
  }
}
