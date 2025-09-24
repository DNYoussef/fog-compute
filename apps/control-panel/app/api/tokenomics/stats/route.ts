import { NextResponse } from 'next/server';

export async function GET() {
  const stats = {
    tokens: {
      totalSupply: 1000000000,
      circulatingSupply: 350000000,
      marketCap: 12400000,
      price: 0.0842
    },
    dao: {
      proposals: Math.floor(Math.random() * 20) + 10,
      activeVotes: Math.floor(Math.random() * 10) + 5,
      totalVoters: Math.floor(Math.random() * 5000) + 2000,
      treasuryBalance: Math.random() * 500000 + 200000
    },
    marketplace: {
      activeListings: Math.floor(Math.random() * 100) + 50,
      totalVolume: Math.random() * 500000 + 200000,
      avgPrice: Math.random() * 0.05 + 0.01,
      trades24h: Math.floor(Math.random() * 500) + 200
    },
    rewards: {
      totalEarned: Math.floor(Math.random() * 100000) + 50000,
      computeRewards: Math.floor(Math.random() * 40000) + 20000,
      stakingRewards: Math.floor(Math.random() * 30000) + 15000,
      governanceRewards: Math.floor(Math.random() * 20000) + 10000
    }
  };

  return NextResponse.json(stats);
}