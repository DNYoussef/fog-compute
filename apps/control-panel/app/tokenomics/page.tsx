'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { TokenChart } from '@/components/TokenChart';

interface TokenomicsStats {
  tokens: {
    totalSupply: number;
    circulatingSupply: number;
    marketCap: number;
    price: number;
  };
  dao: {
    proposals: number;
    activeVotes: number;
    totalVoters: number;
    treasuryBalance: number;
  };
  marketplace: {
    activeListings: number;
    totalVolume: number;
    avgPrice: number;
    trades24h: number;
  };
  rewards: {
    totalEarned: number;
    computeRewards: number;
    stakingRewards: number;
    governanceRewards: number;
  };
}

export default function TokenomicsPage() {
  const [stats, setStats] = useState<TokenomicsStats | null>(null);
  const [userBalance, setUserBalance] = useState(0);

  useEffect(() => {
    document.title = 'Tokenomics | Fog Compute';
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [statsRes, balanceRes] = await Promise.all([
          fetch('/api/tokenomics/stats'),
          fetch('/api/tokenomics/balance'),
        ]);
        const statsData = await statsRes.json();
        const balanceData = await balanceRes.json();
        setStats(statsData);
        setUserBalance(balanceData.balance);
      } catch (error) {
        console.error('Failed to fetch tokenomics stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent">
          Tokenomics & Marketplace
        </h1>
        <p className="text-gray-400 mt-2">
          DAO governance, token rewards, and decentralized compute marketplace
        </p>
      </div>

      {/* User Balance */}
      <div className="glass rounded-xl p-8 border-2 border-yellow-400">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-400">Your Token Balance</div>
            <div className="text-5xl font-bold text-yellow-400 mt-2">
              {userBalance.toLocaleString()} FOG
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">USD Value</div>
            <div className="text-3xl font-bold mt-2">
              ${(userBalance * (stats?.tokens.price || 0)).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Token Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card title="Token Price" className="border-l-4 border-yellow-400">
          <div className="text-3xl font-bold text-yellow-400">
            ${stats?.tokens.price?.toFixed(4) || 0}
          </div>
          <div className="text-green-400 text-sm mt-2">+12.5% 24h</div>
        </Card>

        <Card title="Market Cap" className="border-l-4 border-orange-400">
          <div className="text-3xl font-bold text-orange-400">
            ${(stats?.tokens.marketCap / 1_000_000).toFixed(2) || 0}M
          </div>
          <div className="text-gray-400 text-sm mt-2">Total Value Locked</div>
        </Card>

        <Card title="Circulating Supply" className="border-l-4 border-fog-cyan">
          <div className="text-3xl font-bold text-fog-cyan">
            {(stats?.tokens.circulatingSupply / 1_000_000).toFixed(2) || 0}M
          </div>
          <div className="text-gray-400 text-sm mt-2">
            of {(stats?.tokens.totalSupply / 1_000_000).toFixed(2) || 0}M total
          </div>
        </Card>

        <Card title="24h Volume" className="border-l-4 border-green-400">
          <div className="text-3xl font-bold text-green-400">
            ${(stats?.marketplace.totalVolume / 1_000).toFixed(1) || 0}K
          </div>
          <div className="text-gray-400 text-sm mt-2">
            {stats?.marketplace.trades24h || 0} trades
          </div>
        </Card>
      </div>

      {/* Token Price Chart */}
      <Card title="Token Price History (7 Days)" className="min-h-[400px]">
        <TokenChart />
      </Card>

      {/* DAO Governance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="DAO Governance">
          <div className="space-y-4">
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <div>
                <div className="text-sm text-gray-400">Active Proposals</div>
                <div className="text-2xl font-bold text-fog-purple">
                  {stats?.dao.proposals || 0}
                </div>
              </div>
              <button className="px-4 py-2 bg-fog-purple rounded-lg hover:bg-opacity-80 transition">
                View All
              </button>
            </div>
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <div>
                <div className="text-sm text-gray-400">Active Votes</div>
                <div className="text-2xl font-bold text-fog-cyan">
                  {stats?.dao.activeVotes || 0}
                </div>
              </div>
              <button className="px-4 py-2 bg-fog-cyan text-dark-bg rounded-lg hover:bg-opacity-80 transition">
                Cast Vote
              </button>
            </div>
            <div className="p-4 glass rounded-lg">
              <div className="flex justify-between mb-2">
                <span className="text-gray-400">Treasury Balance</span>
                <span className="text-2xl font-bold text-yellow-400">
                  ${(stats?.dao.treasuryBalance / 1_000).toFixed(1) || 0}K
                </span>
              </div>
              <div className="text-sm text-gray-400">
                {stats?.dao.totalVoters || 0} total voters
              </div>
            </div>
          </div>
        </Card>

        <Card title="Compute Marketplace">
          <div className="space-y-4">
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <div>
                <div className="text-sm text-gray-400">Active Listings</div>
                <div className="text-2xl font-bold text-green-400">
                  {stats?.marketplace.activeListings || 0}
                </div>
              </div>
              <button className="px-4 py-2 bg-green-400 text-dark-bg rounded-lg hover:bg-opacity-80 transition">
                Browse
              </button>
            </div>
            <div className="flex justify-between items-center p-4 glass rounded-lg">
              <div>
                <div className="text-sm text-gray-400">Avg Price per Hour</div>
                <div className="text-2xl font-bold text-yellow-400">
                  {stats?.marketplace.avgPrice?.toFixed(4) || 0} FOG
                </div>
              </div>
              <button className="px-4 py-2 bg-yellow-400 text-dark-bg rounded-lg hover:bg-opacity-80 transition">
                List Compute
              </button>
            </div>
            <div className="p-4 bg-gradient-to-r from-green-400/10 to-yellow-400/10 rounded-lg border border-green-400/20">
              <div className="font-semibold mb-2">Market Activity</div>
              <div className="text-sm text-gray-400">
                High demand for GPU compute - prices up 8% this week
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Rewards Dashboard */}
      <Card title="Rewards Breakdown">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-yellow-400">
              {stats?.rewards.totalEarned?.toLocaleString() || 0}
            </div>
            <div className="text-gray-400 mt-2">Total Earned</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-green-400">
              {stats?.rewards.computeRewards?.toLocaleString() || 0}
            </div>
            <div className="text-gray-400 mt-2">Compute Rewards</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-fog-cyan">
              {stats?.rewards.stakingRewards?.toLocaleString() || 0}
            </div>
            <div className="text-gray-400 mt-2">Staking Rewards</div>
          </div>
          <div className="text-center p-6 glass rounded-lg">
            <div className="text-4xl font-bold text-fog-purple">
              {stats?.rewards.governanceRewards?.toLocaleString() || 0}
            </div>
            <div className="text-gray-400 mt-2">Governance Rewards</div>
          </div>
        </div>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button className="btn-primary p-6 rounded-lg text-left">
          <div className="text-xl font-semibold">Stake Tokens</div>
          <p className="text-sm text-gray-400 mt-2">
            Earn 12% APY by staking FOG tokens
          </p>
        </button>
        <button className="btn-secondary p-6 rounded-lg text-left">
          <div className="text-xl font-semibold">Buy Compute</div>
          <p className="text-sm text-gray-400 mt-2">
            Purchase compute hours from the marketplace
          </p>
        </button>
        <button className="glass p-6 rounded-lg text-left hover:border-yellow-400 transition border-2 border-transparent">
          <div className="text-xl font-semibold">Claim Rewards</div>
          <p className="text-sm text-gray-400 mt-2">
            Claim your pending compute and staking rewards
          </p>
        </button>
      </div>

      {/* Recent Proposals */}
      <Card title="Recent DAO Proposals">
        <div className="space-y-3">
          {[
            { id: 1, title: 'Increase compute rewards by 20%', votes: 1250, status: 'active' },
            { id: 2, title: 'Add support for ARM processors', votes: 890, status: 'active' },
            { id: 3, title: 'Reduce marketplace fees to 1%', votes: 2100, status: 'passed' },
          ].map((proposal) => (
            <div key={proposal.id} className="p-4 glass rounded-lg flex items-center justify-between">
              <div>
                <div className="font-semibold">{proposal.title}</div>
                <div className="text-sm text-gray-400 mt-1">{proposal.votes} votes</div>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-sm font-semibold ${
                  proposal.status === 'active'
                    ? 'bg-green-400/20 text-green-400'
                    : 'bg-fog-cyan/20 text-fog-cyan'
                }`}
              >
                {proposal.status}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}