import { NextResponse } from 'next/server';

export async function GET() {
  const stats = {
    circuits: {
      active: Math.floor(Math.random() * 60) + 30,
      total: Math.floor(Math.random() * 100) + 80,
      avgLatency: Math.random() * 200 + 100,
      throughput: Math.random() * 30 + 10
    },
    onion: {
      layers: Math.floor(Math.random() * 3) + 3,
      nodes: Math.floor(Math.random() * 200) + 100,
      encryption: ['AES-256', 'ChaCha20'][Math.floor(Math.random() * 2)] as 'AES-256' | 'ChaCha20',
      mixnets: Math.floor(Math.random() * 20) + 10
    },
    vpn: {
      tunnels: Math.floor(Math.random() * 50) + 20,
      bandwidth: Math.random() * 100 + 50,
      connectedUsers: Math.floor(Math.random() * 500) + 200,
      protocols: ['OpenVPN', 'WireGuard', 'IPSec', 'IKEv2']
    },
    privacy: {
      anonymityScore: Math.floor(Math.random() * 20) + 80,
      fingerprintResistance: Math.floor(Math.random() * 20) + 75,
      trafficObfuscation: Math.floor(Math.random() * 15) + 85
    }
  };

  return NextResponse.json(stats);
}