//! Node Reputation System (Stub for protocol versioning)

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeReputation {
    pub node_id: String,
    pub score: f64,
}

impl NodeReputation {
    pub fn new(node_id: String) -> Self {
        Self { node_id, score: 1.0 }
    }
}

#[derive(Debug, Default)]
pub struct ReputationManager {}

impl ReputationManager {
    pub fn get_reputation(&self, _node_id: &str) -> Option<NodeReputation> {
        None
    }
}

#[derive(Debug, Clone, Copy)]
pub enum PenaltyType {
    DroppedPacket,
}

#[derive(Debug, Clone, Copy)]
pub enum RewardType {
    SuccessfulForward,
}

#[derive(Debug, Clone, Default)]
pub struct PerformanceMetrics {
    pub packets_processed: u64,
    pub packets_forwarded: u64,
    pub packets_dropped: u64,
}
