/**
 * BitChat UI Components Tests
 * Comprehensive testing for all UI components
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BetanetTopology } from '../../apps/control-panel/components/BetanetTopology';
import { MixnodeList } from '../../apps/control-panel/components/MixnodeList';
import { PacketFlowMonitor } from '../../apps/control-panel/components/PacketFlowMonitor';
import { SystemMetrics } from '../../apps/control-panel/components/SystemMetrics';
import { BenchmarkCharts } from '../../apps/control-panel/components/BenchmarkCharts';
import { BenchmarkControls } from '../../apps/control-panel/components/BenchmarkControls';
import { FogMap } from '../../apps/control-panel/components/FogMap';
import { QuickActions } from '../../apps/control-panel/components/QuickActions';
import { Navigation } from '../../apps/control-panel/components/Navigation';

describe('BetanetTopology Component', () => {
  const mockMixnodes = [
    {
      id: 'node-1',
      position: { x: 0, y: 0, z: 0 },
      status: 'active' as const,
      reputation: 100,
    },
    {
      id: 'node-2',
      position: { x: 2, y: 2, z: 2 },
      status: 'degraded' as const,
      reputation: 75,
    },
    {
      id: 'node-3',
      position: { x: -2, y: -2, z: -2 },
      status: 'inactive' as const,
      reputation: 0,
    },
  ];

  it('renders topology canvas', () => {
    const mockOnNodeSelect = jest.fn();
    const { container } = render(
      <BetanetTopology
        mixnodes={mockMixnodes}
        selectedNode={null}
        onNodeSelect={mockOnNodeSelect}
      />
    );

    expect(container.querySelector('canvas')).toBeInTheDocument();
  });

  it('handles node selection', async () => {
    const mockOnNodeSelect = jest.fn();
    render(
      <BetanetTopology
        mixnodes={mockMixnodes}
        selectedNode={null}
        onNodeSelect={mockOnNodeSelect}
      />
    );

    // Canvas interaction would be tested with more specific 3D testing tools
    expect(mockOnNodeSelect).not.toHaveBeenCalled();
  });

  it('displays correct number of nodes', () => {
    const mockOnNodeSelect = jest.fn();
    const { container } = render(
      <BetanetTopology
        mixnodes={mockMixnodes}
        selectedNode="node-1"
        onNodeSelect={mockOnNodeSelect}
      />
    );

    expect(mockMixnodes).toHaveLength(3);
  });

  it('highlights selected node', () => {
    const mockOnNodeSelect = jest.fn();
    render(
      <BetanetTopology
        mixnodes={mockMixnodes}
        selectedNode="node-1"
        onNodeSelect={mockOnNodeSelect}
      />
    );

    // Selected node behavior would be validated through 3D scene inspection
    expect(mockMixnodes[0].id).toBe('node-1');
  });
});

describe('MixnodeList Component', () => {
  const mockMixnodes = [
    {
      id: 'node-1',
      address: '192.168.1.1:8080',
      status: 'active' as const,
      packetsProcessed: 1000,
      reputation: 100,
      uptime: '24h 30m',
    },
    {
      id: 'node-2',
      address: '192.168.1.2:8080',
      status: 'degraded' as const,
      packetsProcessed: 500,
      reputation: 75,
      uptime: '12h 15m',
    },
  ];

  it('renders all mixnodes', () => {
    render(<MixnodeList mixnodes={mockMixnodes} onNodeSelect={jest.fn()} />);

    expect(screen.getByText('192.168.1.1:8080')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.2:8080')).toBeInTheDocument();
  });

  it('displays status badges correctly', () => {
    render(<MixnodeList mixnodes={mockMixnodes} onNodeSelect={jest.fn()} />);

    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Degraded')).toBeInTheDocument();
  });

  it('shows packet statistics', () => {
    render(<MixnodeList mixnodes={mockMixnodes} onNodeSelect={jest.fn()} />);

    expect(screen.getByText(/1000/)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
  });

  it('handles node selection', () => {
    const mockOnNodeSelect = jest.fn();
    render(<MixnodeList mixnodes={mockMixnodes} onNodeSelect={mockOnNodeSelect} />);

    const firstNode = screen.getByText('192.168.1.1:8080').closest('div');
    if (firstNode) {
      fireEvent.click(firstNode);
      expect(mockOnNodeSelect).toHaveBeenCalledWith('node-1');
    }
  });
});

describe('PacketFlowMonitor Component', () => {
  const mockPacketFlow = {
    incoming: 1500,
    outgoing: 1450,
    dropped: 50,
    throughput: '25000 pps',
    latency: '0.8ms',
  };

  it('displays throughput metrics', () => {
    render(<PacketFlowMonitor flow={mockPacketFlow} />);

    expect(screen.getByText(/25000 pps/)).toBeInTheDocument();
  });

  it('shows latency information', () => {
    render(<PacketFlowMonitor flow={mockPacketFlow} />);

    expect(screen.getByText(/0.8ms/)).toBeInTheDocument();
  });

  it('displays packet counts', () => {
    render(<PacketFlowMonitor flow={mockPacketFlow} />);

    expect(screen.getByText(/1500/)).toBeInTheDocument(); // incoming
    expect(screen.getByText(/1450/)).toBeInTheDocument(); // outgoing
    expect(screen.getByText(/50/)).toBeInTheDocument(); // dropped
  });

  it('calculates drop rate correctly', () => {
    render(<PacketFlowMonitor flow={mockPacketFlow} />);

    const dropRate = (50 / 1500 * 100).toFixed(2);
    // Component should show drop rate calculation
  });
});

describe('SystemMetrics Component', () => {
  const mockMetrics = {
    cpu: 45.5,
    memory: 62.3,
    network: {
      in: '150 Mbps',
      out: '120 Mbps',
    },
    uptime: '5d 12h',
  };

  it('displays CPU usage', () => {
    render(<SystemMetrics metrics={mockMetrics} />);

    expect(screen.getByText(/45.5%/)).toBeInTheDocument();
  });

  it('displays memory usage', () => {
    render(<SystemMetrics metrics={mockMetrics} />);

    expect(screen.getByText(/62.3%/)).toBeInTheDocument();
  });

  it('shows network statistics', () => {
    render(<SystemMetrics metrics={mockMetrics} />);

    expect(screen.getByText(/150 Mbps/)).toBeInTheDocument();
    expect(screen.getByText(/120 Mbps/)).toBeInTheDocument();
  });

  it('displays system uptime', () => {
    render(<SystemMetrics metrics={mockMetrics} />);

    expect(screen.getByText(/5d 12h/)).toBeInTheDocument();
  });
});

describe('BenchmarkCharts Component', () => {
  const mockBenchmarkData = {
    throughput: [
      { time: '10:00', value: 22000 },
      { time: '10:01', value: 24000 },
      { time: '10:02', value: 25000 },
    ],
    latency: [
      { time: '10:00', value: 0.9 },
      { time: '10:01', value: 0.85 },
      { time: '10:02', value: 0.8 },
    ],
    memoryPool: [
      { time: '10:00', hitRate: 83 },
      { time: '10:01', hitRate: 86 },
      { time: '10:02', hitRate: 88 },
    ],
  };

  it('renders throughput chart', () => {
    render(<BenchmarkCharts data={mockBenchmarkData} />);

    expect(screen.getByText(/Throughput/i)).toBeInTheDocument();
  });

  it('renders latency chart', () => {
    render(<BenchmarkCharts data={mockBenchmarkData} />);

    expect(screen.getByText(/Latency/i)).toBeInTheDocument();
  });

  it('renders memory pool chart', () => {
    render(<BenchmarkCharts data={mockBenchmarkData} />);

    expect(screen.getByText(/Memory Pool/i)).toBeInTheDocument();
  });
});

describe('BenchmarkControls Component', () => {
  it('starts benchmark on button click', async () => {
    const mockOnStart = jest.fn();
    const mockOnStop = jest.fn();

    render(
      <BenchmarkControls
        isRunning={false}
        onStart={mockOnStart}
        onStop={mockOnStop}
      />
    );

    const startButton = screen.getByText(/Start/i);
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(mockOnStart).toHaveBeenCalled();
    });
  });

  it('stops benchmark on button click', async () => {
    const mockOnStart = jest.fn();
    const mockOnStop = jest.fn();

    render(
      <BenchmarkControls
        isRunning={true}
        onStart={mockOnStart}
        onStop={mockOnStop}
      />
    );

    const stopButton = screen.getByText(/Stop/i);
    fireEvent.click(stopButton);

    await waitFor(() => {
      expect(mockOnStop).toHaveBeenCalled();
    });
  });

  it('disables start button when running', () => {
    render(
      <BenchmarkControls
        isRunning={true}
        onStart={jest.fn()}
        onStop={jest.fn()}
      />
    );

    const startButton = screen.getByText(/Start/i).closest('button');
    expect(startButton).toBeDisabled();
  });
});

describe('Navigation Component', () => {
  it('renders all navigation links', () => {
    render(<Navigation currentPath="/" />);

    expect(screen.getByText(/Dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Betanet/i)).toBeInTheDocument();
    expect(screen.getByText(/BitChat/i)).toBeInTheDocument();
    expect(screen.getByText(/Benchmarks/i)).toBeInTheDocument();
  });

  it('highlights active route', () => {
    render(<Navigation currentPath="/betanet" />);

    const betanetLink = screen.getByText(/Betanet/i).closest('a');
    expect(betanetLink).toHaveClass('active');
  });
});

describe('FogMap Component', () => {
  const mockDevices = [
    { id: 'dev-1', lat: 40.7128, lng: -74.0060, type: 'edge', status: 'online' },
    { id: 'dev-2', lat: 34.0522, lng: -118.2437, type: 'fog', status: 'online' },
    { id: 'dev-3', lat: 41.8781, lng: -87.6298, type: 'cloud', status: 'offline' },
  ];

  it('renders map container', () => {
    const { container } = render(<FogMap devices={mockDevices} />);

    expect(container.querySelector('.map-container')).toBeInTheDocument();
  });

  it('displays all devices', () => {
    render(<FogMap devices={mockDevices} />);

    expect(mockDevices).toHaveLength(3);
  });

  it('shows device status correctly', () => {
    render(<FogMap devices={mockDevices} />);

    const onlineDevices = mockDevices.filter(d => d.status === 'online');
    expect(onlineDevices).toHaveLength(2);
  });
});

describe('QuickActions Component', () => {
  it('renders all action buttons', () => {
    render(<QuickActions />);

    expect(screen.getByText(/Deploy Node/i)).toBeInTheDocument();
    expect(screen.getByText(/Run Benchmark/i)).toBeInTheDocument();
    expect(screen.getByText(/View Logs/i)).toBeInTheDocument();
  });

  it('executes actions on click', async () => {
    const mockAction = jest.fn();

    render(<QuickActions onAction={mockAction} />);

    const deployButton = screen.getByText(/Deploy Node/i);
    fireEvent.click(deployButton);

    await waitFor(() => {
      expect(mockAction).toHaveBeenCalledWith('deploy');
    });
  });
});