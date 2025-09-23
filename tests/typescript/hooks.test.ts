/**
 * Custom Hooks Tests
 * Testing React hooks for BitChat and Control Panel
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useBetanetStatus } from '../../apps/control-panel/hooks/useBetanetStatus';
import { useBenchmarkData } from '../../apps/control-panel/hooks/useBenchmarkData';
import { useWebSocket } from '../../apps/control-panel/hooks/useWebSocket';
import { useP2PConnection } from '../../apps/bitchat/hooks/useP2PConnection';
import { useMixnodeMetrics } from '../../apps/control-panel/hooks/useMixnodeMetrics';

// Mock fetch
global.fetch = jest.fn();

describe('useBetanetStatus Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('fetches betanet status on mount', async () => {
    const mockStatus = {
      nodes: 5,
      activeCircuits: 10,
      throughput: '25000 pps',
      health: 'healthy',
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockStatus,
    });

    const { result } = renderHook(() => useBetanetStatus());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.status).toEqual(mockStatus);
    expect(result.current.error).toBeNull();
  });

  it('handles fetch errors', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useBetanetStatus());

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    expect(result.current.status).toBeNull();
  });

  it('refreshes status on interval', async () => {
    jest.useFakeTimers();

    const mockStatus1 = { nodes: 5 };
    const mockStatus2 = { nodes: 6 };

    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => mockStatus1 })
      .mockResolvedValueOnce({ ok: true, json: async () => mockStatus2 });

    const { result } = renderHook(() => useBetanetStatus({ refreshInterval: 1000 }));

    await waitFor(() => expect(result.current.status).toEqual(mockStatus1));

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    await waitFor(() => expect(result.current.status).toEqual(mockStatus2));

    jest.useRealTimers();
  });
});

describe('useBenchmarkData Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('starts benchmark and collects data', async () => {
    const mockData = {
      timestamp: Date.now(),
      throughput: 24000,
      latency: 0.85,
      poolHitRate: 87,
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const { result } = renderHook(() => useBenchmarkData());

    await act(async () => {
      await result.current.startBenchmark();
    });

    expect(result.current.isRunning).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/benchmarks/start'),
      expect.any(Object)
    );
  });

  it('stops benchmark', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const { result } = renderHook(() => useBenchmarkData());

    await act(async () => {
      await result.current.stopBenchmark();
    });

    expect(result.current.isRunning).toBe(false);
  });

  it('collects real-time metrics', async () => {
    jest.useFakeTimers();

    const mockMetrics = [
      { time: '10:00', value: 22000 },
      { time: '10:01', value: 24000 },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ metrics: mockMetrics }),
    });

    const { result } = renderHook(() => useBenchmarkData({ collectInterval: 1000 }));

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    await waitFor(() => {
      expect(result.current.metrics.length).toBeGreaterThan(0);
    });

    jest.useRealTimers();
  });
});

describe('useWebSocket Hook', () => {
  let mockWebSocket: any;

  beforeEach(() => {
    mockWebSocket = {
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      readyState: WebSocket.OPEN,
    };

    (global as any).WebSocket = jest.fn(() => mockWebSocket);
  });

  it('establishes WebSocket connection', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    expect(result.current.connected).toBe(false);

    act(() => {
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )?.[1];
      openHandler?.();
    });

    expect(result.current.connected).toBe(true);
  });

  it('sends messages', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    act(() => {
      result.current.send({ type: 'ping', data: 'test' });
    });

    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'ping', data: 'test' })
    );
  });

  it('receives messages', () => {
    const mockOnMessage = jest.fn();
    const { result } = renderHook(() =>
      useWebSocket('ws://localhost:8080', { onMessage: mockOnMessage })
    );

    const message = { type: 'update', data: { nodes: 5 } };

    act(() => {
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )?.[1];
      messageHandler?.({ data: JSON.stringify(message) });
    });

    expect(mockOnMessage).toHaveBeenCalledWith(message);
  });

  it('handles disconnection', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    act(() => {
      const closeHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'close'
      )?.[1];
      closeHandler?.();
    });

    expect(result.current.connected).toBe(false);
  });

  it('reconnects on connection loss', async () => {
    jest.useFakeTimers();

    const { result } = renderHook(() =>
      useWebSocket('ws://localhost:8080', { reconnect: true, reconnectInterval: 1000 })
    );

    act(() => {
      const closeHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'close'
      )?.[1];
      closeHandler?.();
    });

    expect(result.current.connected).toBe(false);

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(global.WebSocket).toHaveBeenCalledTimes(2);

    jest.useRealTimers();
  });
});

describe('useP2PConnection Hook', () => {
  it('initializes P2P connection', async () => {
    const { result } = renderHook(() => useP2PConnection());

    expect(result.current.peerId).toBeDefined();
    expect(result.current.connected).toBe(false);
  });

  it('connects to peer', async () => {
    const { result } = renderHook(() => useP2PConnection());

    await act(async () => {
      await result.current.connectToPeer('peer-123');
    });

    expect(result.current.peers).toContain('peer-123');
  });

  it('sends message to peer', async () => {
    const { result } = renderHook(() => useP2PConnection());

    await act(async () => {
      await result.current.connectToPeer('peer-123');
    });

    await act(async () => {
      await result.current.sendMessage('peer-123', 'Hello!');
    });

    // Verify message was sent (would need mock P2P library)
    expect(result.current.peers.length).toBeGreaterThan(0);
  });

  it('receives messages from peers', async () => {
    const mockOnMessage = jest.fn();
    const { result } = renderHook(() => useP2PConnection({ onMessage: mockOnMessage }));

    await act(async () => {
      await result.current.connectToPeer('peer-123');
    });

    // Simulate incoming message
    act(() => {
      result.current.simulateIncomingMessage('peer-123', 'Test message');
    });

    expect(mockOnMessage).toHaveBeenCalledWith({
      from: 'peer-123',
      message: 'Test message',
    });
  });

  it('handles peer disconnection', async () => {
    const { result } = renderHook(() => useP2PConnection());

    await act(async () => {
      await result.current.connectToPeer('peer-123');
    });

    expect(result.current.peers).toContain('peer-123');

    await act(async () => {
      await result.current.disconnectPeer('peer-123');
    });

    expect(result.current.peers).not.toContain('peer-123');
  });
});

describe('useMixnodeMetrics Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('fetches mixnode metrics', async () => {
    const mockMetrics = {
      nodeId: 'node-1',
      packetsProcessed: 1000,
      throughput: 25000,
      latency: 0.8,
      memoryPoolHitRate: 87,
      uptime: 86400,
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockMetrics,
    });

    const { result } = renderHook(() => useMixnodeMetrics('node-1'));

    await waitFor(() => {
      expect(result.current.metrics).toEqual(mockMetrics);
    });
  });

  it('updates metrics periodically', async () => {
    jest.useFakeTimers();

    const mockMetrics1 = { packetsProcessed: 1000 };
    const mockMetrics2 = { packetsProcessed: 1500 };

    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => mockMetrics1 })
      .mockResolvedValueOnce({ ok: true, json: async () => mockMetrics2 });

    const { result } = renderHook(() =>
      useMixnodeMetrics('node-1', { updateInterval: 2000 })
    );

    await waitFor(() => expect(result.current.metrics).toEqual(mockMetrics1));

    act(() => {
      jest.advanceTimersByTime(2000);
    });

    await waitFor(() => expect(result.current.metrics).toEqual(mockMetrics2));

    jest.useRealTimers();
  });

  it('calculates derived metrics', async () => {
    const mockMetrics = {
      packetsProcessed: 1000,
      packetsDropped: 10,
      totalMemoryRequests: 1000,
      memoryPoolHits: 870,
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockMetrics,
    });

    const { result } = renderHook(() => useMixnodeMetrics('node-1'));

    await waitFor(() => {
      const dropRate = result.current.derivedMetrics?.dropRate;
      expect(dropRate).toBeCloseTo(1.0, 1);

      const hitRate = result.current.derivedMetrics?.poolHitRate;
      expect(hitRate).toBeCloseTo(87.0, 1);
    });
  });
});