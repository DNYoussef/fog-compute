/**
 * Bluetooth Low Energy Discovery Protocol
 * Handles nearby peer discovery using BLE mesh networking
 *
 * SIN-013: Replaces mock peer discovery with real BLE scan
 * and empty array fallback when unavailable.
 */

import { BitChatPeer } from '../types';

/** Whether the Web Bluetooth API is available in this environment. */
export const BLUETOOTH_AVAILABLE =
  typeof navigator !== 'undefined' && !!navigator.bluetooth;

export class BluetoothProtocol {
  private bluetoothDevice: BluetoothDevice | null = null;
  private discoveredDevices: Map<string, BluetoothDevice> = new Map();

  /**
   * Initialize Bluetooth LE discovery.
   * Returns false if BLE is not available on this platform.
   */
  async initializeBluetoothLEDiscovery(): Promise<boolean> {
    if (!BLUETOOTH_AVAILABLE) {
      console.warn(
        'Bluetooth API not available on this platform. ' +
        'BLE discovery disabled - WebRTC only.'
      );
      return false;
    }

    try {
      const device = await navigator.bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: ['battery_service', 'device_information']
      });

      this.bluetoothDevice = device;
      return true;
    } catch (error) {
      console.warn('Bluetooth LE initialization failed:', error);
      return false;
    }
  }

  /**
   * Discover nearby peers via Bluetooth LE.
   *
   * SIN-013: Returns empty array when BLE unavailable (no mock data).
   * Only returns real discovered devices.
   */
  async discoverPeers(): Promise<BitChatPeer[]> {
    if (!BLUETOOTH_AVAILABLE) {
      // No mock peers - return empty for honest API
      return [];
    }

    try {
      // Request BLE device scan
      const device = await navigator.bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: ['battery_service']
      });

      if (device && device.id) {
        this.discoveredDevices.set(device.id, device);
      }

      // Convert discovered devices to BitChatPeer format
      const peers: BitChatPeer[] = [];
      for (const [id, dev] of this.discoveredDevices) {
        peers.push({
          id,
          name: dev.name || `BLE-Device-${id.slice(0, 8)}`,
          status: 'online',
          lastSeen: new Date(),
          // Real public key exchange happens after discovery
          publicKey: ''
        });
      }

      return peers;
    } catch (error) {
      // User cancelled or BLE scan failed
      console.warn('BLE peer discovery failed:', error);
      return [];
    }
  }

  /**
   * Check if Bluetooth is available on this platform.
   */
  isBluetoothAvailable(): boolean {
    return BLUETOOTH_AVAILABLE;
  }

  /**
   * Get connected Bluetooth device info.
   */
  getDeviceInfo(): { name: string | undefined; id: string | undefined } | null {
    if (!this.bluetoothDevice) {
      return null;
    }

    return {
      name: this.bluetoothDevice.name,
      id: this.bluetoothDevice.id
    };
  }

  /**
   * Get count of discovered devices.
   */
  getDiscoveredDeviceCount(): number {
    return this.discoveredDevices.size;
  }
}
