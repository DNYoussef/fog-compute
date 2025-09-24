import { NextResponse } from 'next/server';

export async function GET() {
  const stats = {
    bitchat: {
      bleConnections: Math.floor(Math.random() * 50) + 20,
      offlinePeers: Math.floor(Math.random() * 30) + 10,
      meshTopology: ['star', 'mesh', 'hybrid'][Math.floor(Math.random() * 3)]
    },
    betanet: {
      htxCircuits: Math.floor(Math.random() * 100) + 50,
      onlineNodes: Math.floor(Math.random() * 200) + 100,
      throughput: Math.random() * 50 + 10
    },
    unified: {
      totalPeers: Math.floor(Math.random() * 300) + 150,
      protocolDistribution: {
        ble: Math.floor(Math.random() * 100) + 50,
        htx: Math.floor(Math.random() * 150) + 75,
        mesh: Math.floor(Math.random() * 80) + 40
      },
      messageQueue: Math.floor(Math.random() * 500),
      activeRoutes: Math.floor(Math.random() * 150) + 50
    }
  };

  return NextResponse.json(stats);
}