/**
 * Tests for WebRTC protocol (Phase 4).
 *
 * SIN-014: WebRTC must support configurable TURN servers
 * and use shared configuration.
 */
import { WebRTCProtocol, WebRTCConfig } from './webrtc';

describe('WebRTCProtocol (SIN-014)', () => {
  describe('TURN server configuration', () => {
    it('accepts TURN server config', () => {
      const config: Partial<WebRTCConfig> = {
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          {
            urls: 'turn:turn.example.com:3478',
            username: 'user',
            credential: 'pass'
          }
        ]
      };

      const protocol = new WebRTCProtocol(config);
      expect(protocol.hasTurnServers()).toBe(true);
    });

    it('reports no TURN when only STUN configured', () => {
      const protocol = new WebRTCProtocol();
      expect(protocol.hasTurnServers()).toBe(false);
    });

    it('returns configured ICE servers', () => {
      const config: Partial<WebRTCConfig> = {
        iceServers: [
          { urls: 'stun:stun.example.com:3478' },
          {
            urls: ['turn:turn.example.com:3478', 'turns:turn.example.com:5349'],
            username: 'user',
            credential: 'pass'
          }
        ]
      };

      const protocol = new WebRTCProtocol(config);
      const servers = protocol.getIceServerConfig();
      expect(servers).toHaveLength(2);
      expect(protocol.hasTurnServers()).toBe(true);
    });
  });

  describe('signaling server configuration', () => {
    it('accepts signaling server URL', () => {
      const config: Partial<WebRTCConfig> = {
        signalingServerUrl: 'wss://signal.example.com/ws'
      };

      const protocol = new WebRTCProtocol(config);
      // Should not throw - signaling configured but not connected yet
      expect(protocol).toBeTruthy();
    });

    it('defaults to no signaling server', () => {
      const protocol = new WebRTCProtocol();
      // Default has no signaling - should be fine
      expect(protocol).toBeTruthy();
    });
  });

  describe('shared configuration', () => {
    it('source uses getRTCConfiguration for all connections', () => {
      const fs = require('fs');
      const path = require('path');
      const source = fs.readFileSync(
        path.join(__dirname, 'webrtc.ts'),
        'utf8'
      );

      // createPeerConnection should use shared config method
      expect(source).toContain('this.getRTCConfiguration()');

      // Should NOT have inline STUN-only config in createPeerConnection
      // (the old pattern was: new RTCPeerConnection({ iceServers: [{ urls: 'stun:...' }] }))
      const createPeerFn = source.split('createPeerConnection')[1]?.split('closePeerConnection')[0];
      if (createPeerFn) {
        // The connection should use getRTCConfiguration, not inline iceServers
        expect(createPeerFn).toContain('getRTCConfiguration');
      }
    });
  });

  describe('cleanup', () => {
    it('cleanup does not throw', () => {
      const protocol = new WebRTCProtocol();
      expect(() => protocol.cleanup()).not.toThrow();
    });

    it('reports disconnected for unknown peer', () => {
      const protocol = new WebRTCProtocol();
      expect(protocol.getConnectionStatus('unknown')).toBe('disconnected');
    });
  });
});
