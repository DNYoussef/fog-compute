//! Node Reputation System
//!
//! Minimal working implementation for Week 6 testing.
//! Full implementation planned for Week 7-8.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::SocketAddr;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeReputation {
    pub node_id: String,
    pub score: f64,
    pub reputation: f64,  // Main reputation score (0.0-1.0)
    pub stake: u64,       // Node stake amount
    pub metrics: PerformanceMetrics,
}

impl NodeReputation {
    pub fn new(node_id: String) -> Self {
        Self {
            node_id,
            score: 1.0,
            reputation: 1.0,
            stake: 0,
            metrics: PerformanceMetrics::default(),
        }
    }
}

#[derive(Debug, Default)]
pub struct ReputationManager {
    reputations: HashMap<String, NodeReputation>,
    decay_rate: f64,
}

impl ReputationManager {
    pub fn new() -> Self {
        Self {
            reputations: HashMap::new(),
            decay_rate: 0.99,  // 1% decay per period
        }
    }

    pub fn add_node(&mut self, addr: SocketAddr, stake: u64) {
        let node_id = addr.to_string();
        let mut rep = NodeReputation::new(node_id);
        rep.stake = stake;
        self.reputations.insert(addr.to_string(), rep);
    }

    pub fn get_reputation(&self, addr: &SocketAddr) -> Option<NodeReputation> {
        self.reputations.get(&addr.to_string()).cloned()
    }

    pub fn apply_penalty(&mut self, addr: &SocketAddr, _penalty: PenaltyType) -> Result<(), String> {
        let node_id = addr.to_string();
        let reputation = self.reputations
            .entry(node_id.clone())
            .or_insert_with(|| NodeReputation::new(node_id));

        // Reduce reputation by 10% for penalty
        reputation.reputation = (reputation.reputation * 0.9).max(0.0);
        reputation.score = reputation.reputation;
        Ok(())
    }

    pub fn apply_reward(&mut self, addr: &SocketAddr, _reward: RewardType) -> Result<(), String> {
        let node_id = addr.to_string();
        let reputation = self.reputations
            .entry(node_id.clone())
            .or_insert_with(|| NodeReputation::new(node_id));

        // Increase reputation by 5%
        reputation.reputation = (reputation.reputation * 1.05).min(1.0);
        reputation.score = reputation.reputation;
        Ok(())
    }

    pub fn apply_decay_all(&mut self) {
        for reputation in self.reputations.values_mut() {
            reputation.reputation *= self.decay_rate;
            reputation.score = reputation.reputation;
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum PenaltyType {
    DroppedPacket,
    PacketDrop,  // Alias for compatibility
    HighLatency,
    FailedConnection,
}

#[derive(Debug, Clone, Copy)]
pub enum RewardType {
    SuccessfulForward,
    HighUptime,  // High uptime reward
    LowLatency,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    pub packets_processed: u64,
    pub packets_forwarded: u64,
    pub packets_dropped: u64,
    pub uptime_percent: f64,
    pub avg_latency_ms: f64,
}

impl PerformanceMetrics {
    pub fn latency_score(&self) -> f64 {
        // Better (lower) latency = higher score
        // 0ms = 1.0, 100ms = 0.5, 200ms+ = 0.0
        (1.0 - (self.avg_latency_ms / 200.0)).max(0.0)
    }

    pub fn success_rate(&self) -> f64 {
        if self.packets_processed == 0 {
            return 1.0;
        }
        self.packets_forwarded as f64 / self.packets_processed as f64
    }
}
