/**
 * Tests for Bluetooth protocol (Phase 4).
 *
 * SIN-013: BLE discovery must not return mock peers.
 */
import { BluetoothProtocol, BLUETOOTH_AVAILABLE } from './bluetooth';

describe('BluetoothProtocol (SIN-013)', () => {
  let protocol: BluetoothProtocol;

  beforeEach(() => {
    protocol = new BluetoothProtocol();
  });

  describe('no mock data', () => {
    it('discoverPeers returns empty array when BLE unavailable', async () => {
      // jsdom has no navigator.bluetooth, so BLUETOOTH_AVAILABLE = false
      const peers = await protocol.discoverPeers();

      expect(peers).toEqual([]);
      // Must NOT contain mock Alice/Bob peers
      expect(peers.length).toBe(0);
    });

    it('does not have getMockPeers method exposed', () => {
      // getMockPeers should not exist at all
      expect((protocol as any).getMockPeers).toBeUndefined();
    });

    it('source code does not contain mock peer data', () => {
      // The module source should not define mock peers
      const fs = require('fs');
      const path = require('path');
      const source = fs.readFileSync(
        path.join(__dirname, 'bluetooth.ts'),
        'utf8'
      );

      expect(source).not.toContain("'Alice Mobile'");
      expect(source).not.toContain("'Bob Laptop'");
      expect(source).not.toContain('getMockPeers');
      expect(source).not.toContain('mock-public-key');
    });
  });

  describe('platform detection', () => {
    it('reports BLE unavailable in jsdom', () => {
      expect(protocol.isBluetoothAvailable()).toBe(false);
      expect(BLUETOOTH_AVAILABLE).toBe(false);
    });

    it('returns null device info when not initialized', () => {
      expect(protocol.getDeviceInfo()).toBeNull();
    });

    it('reports zero discovered devices initially', () => {
      expect(protocol.getDiscoveredDeviceCount()).toBe(0);
    });
  });

  describe('initialization', () => {
    it('returns false when BLE not available', async () => {
      const result = await protocol.initializeBluetoothLEDiscovery();
      expect(result).toBe(false);
    });
  });
});
