//! Node Reputation System - FUNC-10 Full Implementation
//!
//! Complete reputation system with:
//! - Reputation scoring (base 100 points for new nodes)
//! - Cost of forgery calculation (stake + history based)
//! - Time-based decay (-1% daily inactivity)
//! - Persistence layer for cross-session state
//! - Integration with relay lottery weighting
//!
//! Reputation affects relay selection probability in the network.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::time::{SystemTime, UNIX_EPOCH};

/// Reputation score in points (0-200 range, base 100 for new nodes)
pub type ReputationPoints = i32;

/// Cost of forgery metric (higher = harder to fake reputation)
pub type CostOfForgery = f64;

/// Node reputation record with full tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeReputation {
    pub node_id: String,
    pub score: f64,              // Normalized score (0.0-1.0) for compatibility
    pub reputation: f64,         // Normalized reputation (0.0-1.0)
    pub reputation_points: ReputationPoints, // Raw points (0-200)
    pub stake: u64,              // Node stake amount
    pub metrics: PerformanceMetrics,
    pub history: ReputationHistory,
    pub last_active: u64,        // Unix timestamp of last activity
    pub created_at: u64,         // Unix timestamp of node creation
}

impl NodeReputation {
    /// Create new node with base reputation (100 points)
    pub fn new(node_id: String) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Self {
            node_id,
            score: 0.5,                    // Normalized to 0.5 (middle)
            reputation: 0.5,               // Start at middle reputation
            reputation_points: 100,        // Base 100 points for new nodes
            stake: 0,
            metrics: PerformanceMetrics::default(),
            history: ReputationHistory::default(),
            last_active: now,
            created_at: now,
        }
    }

    /// Create node with specific stake
    pub fn with_stake(node_id: String, stake: u64) -> Self {
        let mut node = Self::new(node_id);
        node.stake = stake;
        node
    }

    /// Update reputation points based on action
    pub fn apply_action(&mut self, action: ReputationAction) {
        let delta = action.points_delta();
        self.reputation_points = (self.reputation_points + delta).clamp(0, 200);

        // Update normalized scores
        self.reputation = self.reputation_points as f64 / 200.0;
        self.score = self.reputation;

        // Track in history
        self.history.record_action(action);
        self.update_last_active();
    }

    /// Apply time-based decay (-1% per day of inactivity)
    pub fn apply_decay(&mut self, days_inactive: u32) {
        if days_inactive == 0 {
            return;
        }

        // Apply 1% decay per day: reputation *= 0.99^days
        let decay_factor = 0.99_f64.powi(days_inactive as i32);
        let new_points = (self.reputation_points as f64 * decay_factor) as i32;

        self.reputation_points = new_points.clamp(0, 200);
        self.reputation = self.reputation_points as f64 / 200.0;
        self.score = self.reputation;

        self.history.decay_events += 1;
    }

    /// Calculate cost of forgery for this node
    pub fn cost_of_forgery(&self) -> CostOfForgery {
        // Cost factors:
        // 1. Stake (economic commitment)
        // 2. Reputation points (history/trust)
        // 3. Age of account (time investment)
        // 4. Success rate (consistent performance)

        let stake_factor = (self.stake as f64).ln().max(1.0);
        let reputation_factor = (self.reputation_points as f64 / 100.0).max(0.1);
        let age_factor = self.account_age_days().min(365.0) / 365.0; // Cap at 1 year
        let success_factor = self.metrics.success_rate();

        // Combined cost: multiply factors
        // Higher values = more expensive to forge
        stake_factor * reputation_factor * (1.0 + age_factor) * (1.0 + success_factor)
    }

    /// Get account age in days
    pub fn account_age_days(&self) -> f64 {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        ((now - self.created_at) as f64) / 86400.0 // seconds to days
    }

    /// Get days since last activity
    pub fn days_since_active(&self) -> u32 {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        ((now - self.last_active) / 86400) as u32
    }

    /// Update last active timestamp
    fn update_last_active(&mut self) {
        self.last_active = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
    }

    /// Check if node meets minimum reputation threshold
    pub fn meets_threshold(&self, min_points: ReputationPoints) -> bool {
        self.reputation_points >= min_points
    }
}

/// Reputation action types with point deltas
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ReputationAction {
    /// Successful task completion (+10 points)
    SuccessfulTask,
    /// Uptime milestone reached (+5 points)
    UptimeMilestone,
    /// High-quality service provided (+20 points)
    HighQualityService,
    /// Task failure (-15 points)
    TaskFailure,
    /// Dropped connection (-25 points)
    DroppedConnection,
    /// Malicious behavior detected (-50 points)
    MaliciousBehavior,
    /// Custom action with specific delta
    Custom(i32),
}

impl ReputationAction {
    /// Get point delta for this action
    pub fn points_delta(&self) -> i32 {
        match self {
            ReputationAction::SuccessfulTask => 10,
            ReputationAction::UptimeMilestone => 5,
            ReputationAction::HighQualityService => 20,
            ReputationAction::TaskFailure => -15,
            ReputationAction::DroppedConnection => -25,
            ReputationAction::MaliciousBehavior => -50,
            ReputationAction::Custom(delta) => *delta,
        }
    }
}

/// Historical reputation tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReputationHistory {
    pub successful_tasks: u32,
    pub failed_tasks: u32,
    pub uptime_milestones: u32,
    pub quality_bonuses: u32,
    pub dropped_connections: u32,
    pub malicious_events: u32,
    pub decay_events: u32,
    pub total_actions: u32,
}

impl Default for ReputationHistory {
    fn default() -> Self {
        Self {
            successful_tasks: 0,
            failed_tasks: 0,
            uptime_milestones: 0,
            quality_bonuses: 0,
            dropped_connections: 0,
            malicious_events: 0,
            decay_events: 0,
            total_actions: 0,
        }
    }
}

impl ReputationHistory {
    /// Record an action in history
    fn record_action(&mut self, action: ReputationAction) {
        match action {
            ReputationAction::SuccessfulTask => self.successful_tasks += 1,
            ReputationAction::UptimeMilestone => self.uptime_milestones += 1,
            ReputationAction::HighQualityService => self.quality_bonuses += 1,
            ReputationAction::TaskFailure => self.failed_tasks += 1,
            ReputationAction::DroppedConnection => self.dropped_connections += 1,
            ReputationAction::MaliciousBehavior => self.malicious_events += 1,
            ReputationAction::Custom(_) => {}
        }
        self.total_actions += 1;
    }

    /// Calculate success rate
    pub fn success_rate(&self) -> f64 {
        let total = self.successful_tasks + self.failed_tasks;
        if total == 0 {
            return 1.0;
        }
        self.successful_tasks as f64 / total as f64
    }
}

/// Reputation manager for all network nodes
#[derive(Debug, Default)]
pub struct ReputationManager {
    reputations: HashMap<String, NodeReputation>,
    decay_rate: f64,
    min_reputation_threshold: ReputationPoints,
}

impl ReputationManager {
    /// Create new reputation manager
    pub fn new() -> Self {
        Self {
            reputations: HashMap::new(),
            decay_rate: 0.99,  // 1% decay per day
            min_reputation_threshold: 50, // Minimum 50 points to participate
        }
    }

    /// Create with custom threshold
    pub fn with_threshold(min_threshold: ReputationPoints) -> Self {
        Self {
            reputations: HashMap::new(),
            decay_rate: 0.99,
            min_reputation_threshold: min_threshold,
        }
    }

    /// Add new node with stake
    pub fn add_node(&mut self, addr: SocketAddr, stake: u64) {
        let node_id = addr.to_string();
        let rep = NodeReputation::with_stake(node_id, stake);
        self.reputations.insert(addr.to_string(), rep);
    }

    /// Get node reputation
    pub fn get_reputation(&self, addr: &SocketAddr) -> Option<NodeReputation> {
        self.reputations.get(&addr.to_string()).cloned()
    }

    /// Get reputation score (0.0-1.0)
    pub fn get_reputation_score(&self, addr: &SocketAddr) -> f64 {
        self.get_reputation(addr)
            .map(|r| r.reputation)
            .unwrap_or(0.5) // Default to middle reputation for unknown nodes
    }

    /// Get reputation points
    pub fn get_reputation_points(&self, addr: &SocketAddr) -> ReputationPoints {
        self.get_reputation(addr)
            .map(|r| r.reputation_points)
            .unwrap_or(100) // Default to base points for unknown nodes
    }

    /// Calculate cost of forgery for a node
    pub fn calculate_cost_of_forgery(&self, addr: &SocketAddr) -> CostOfForgery {
        self.get_reputation(addr)
            .map(|r| r.cost_of_forgery())
            .unwrap_or(1.0) // Low cost for unknown nodes
    }

    /// Update reputation based on action
    pub fn update_reputation(&mut self, addr: &SocketAddr, action: ReputationAction) -> Result<(), String> {
        let node_id = addr.to_string();
        let reputation = self.reputations
            .entry(node_id.clone())
            .or_insert_with(|| NodeReputation::new(node_id));

        reputation.apply_action(action);
        Ok(())
    }

    /// Apply penalty (legacy compatibility)
    pub fn apply_penalty(&mut self, addr: &SocketAddr, penalty: PenaltyType) -> Result<(), String> {
        let action = match penalty {
            PenaltyType::DroppedPacket | PenaltyType::PacketDrop => ReputationAction::DroppedConnection,
            PenaltyType::HighLatency => ReputationAction::TaskFailure,
            PenaltyType::FailedConnection => ReputationAction::DroppedConnection,
        };
        self.update_reputation(addr, action)
    }

    /// Apply reward (legacy compatibility)
    pub fn apply_reward(&mut self, addr: &SocketAddr, reward: RewardType) -> Result<(), String> {
        let action = match reward {
            RewardType::SuccessfulForward => ReputationAction::SuccessfulTask,
            RewardType::HighUptime => ReputationAction::UptimeMilestone,
            RewardType::LowLatency => ReputationAction::HighQualityService,
        };
        self.update_reputation(addr, action)
    }

    /// Apply decay to all nodes based on inactivity
    pub fn apply_decay_all(&mut self) {
        for reputation in self.reputations.values_mut() {
            let days_inactive = reputation.days_since_active();
            if days_inactive > 0 {
                // Use decay_rate from manager configuration
                let decay_factor = self.decay_rate.powi(days_inactive as i32);
                let new_points = (reputation.reputation_points as f64 * decay_factor) as i32;

                reputation.reputation_points = new_points.clamp(0, 200);
                reputation.reputation = reputation.reputation_points as f64 / 200.0;
                reputation.score = reputation.reputation;
                reputation.history.decay_events += 1;
            }
        }
    }

    /// Get weighted relay candidates above threshold
    pub fn get_weighted_relay_candidates(&self, min_reputation: ReputationPoints) -> Vec<(SocketAddr, f64)> {
        self.reputations
            .iter()
            .filter(|(_, rep)| rep.reputation_points >= min_reputation)
            .filter_map(|(addr_str, rep)| {
                addr_str.parse::<SocketAddr>().ok().map(|addr| (addr, rep.reputation))
            })
            .collect()
    }

    /// Check if node meets minimum threshold
    pub fn meets_threshold(&self, addr: &SocketAddr) -> bool {
        self.get_reputation(addr)
            .map(|r| r.meets_threshold(self.min_reputation_threshold))
            .unwrap_or(true) // Allow new nodes by default
    }

    /// Get total number of tracked nodes
    pub fn node_count(&self) -> usize {
        self.reputations.len()
    }

    /// Get statistics
    pub fn statistics(&self) -> ReputationStatistics {
        if self.reputations.is_empty() {
            return ReputationStatistics::default();
        }

        let total_nodes = self.reputations.len();
        let avg_reputation = self.reputations.values()
            .map(|r| r.reputation)
            .sum::<f64>() / total_nodes as f64;

        let avg_points = self.reputations.values()
            .map(|r| r.reputation_points)
            .sum::<i32>() / total_nodes as i32;

        let avg_cost_of_forgery = self.reputations.values()
            .map(|r| r.cost_of_forgery())
            .sum::<f64>() / total_nodes as f64;

        let above_threshold = self.reputations.values()
            .filter(|r| r.reputation_points >= self.min_reputation_threshold)
            .count();

        ReputationStatistics {
            total_nodes,
            avg_reputation,
            avg_points,
            avg_cost_of_forgery,
            nodes_above_threshold: above_threshold,
            min_threshold: self.min_reputation_threshold,
        }
    }

    /// Persist reputation data to JSON (for cross-session storage)
    pub fn save_to_json(&self) -> Result<String, String> {
        serde_json::to_string_pretty(&self.reputations)
            .map_err(|e| format!("Failed to serialize reputation data: {}", e))
    }

    /// Load reputation data from JSON
    pub fn load_from_json(&mut self, json_data: &str) -> Result<(), String> {
        let reputations: HashMap<String, NodeReputation> = serde_json::from_str(json_data)
            .map_err(|e| format!("Failed to deserialize reputation data: {}", e))?;

        self.reputations = reputations;
        Ok(())
    }
}

/// Reputation statistics for the network
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReputationStatistics {
    pub total_nodes: usize,
    pub avg_reputation: f64,
    pub avg_points: ReputationPoints,
    pub avg_cost_of_forgery: CostOfForgery,
    pub nodes_above_threshold: usize,
    pub min_threshold: ReputationPoints,
}

impl Default for ReputationStatistics {
    fn default() -> Self {
        Self {
            total_nodes: 0,
            avg_reputation: 0.5,
            avg_points: 100,
            avg_cost_of_forgery: 1.0,
            nodes_above_threshold: 0,
            min_threshold: 50,
        }
    }
}

/// Penalty types (legacy compatibility)
#[derive(Debug, Clone, Copy)]
pub enum PenaltyType {
    DroppedPacket,
    PacketDrop,  // Alias for compatibility
    HighLatency,
    FailedConnection,
}

/// Reward types (legacy compatibility)
#[derive(Debug, Clone, Copy)]
pub enum RewardType {
    SuccessfulForward,
    HighUptime,  // High uptime reward
    LowLatency,
}

/// Performance metrics for node evaluation
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    pub packets_processed: u64,
    pub packets_forwarded: u64,
    pub packets_dropped: u64,
    pub uptime_percent: f64,
    pub avg_latency_ms: f64,
}

impl PerformanceMetrics {
    /// Calculate latency score (0.0-1.0)
    pub fn latency_score(&self) -> f64 {
        // Better (lower) latency = higher score
        // 0ms = 1.0, 100ms = 0.5, 200ms+ = 0.0
        (1.0 - (self.avg_latency_ms / 200.0)).max(0.0)
    }

    /// Calculate success rate (0.0-1.0)
    pub fn success_rate(&self) -> f64 {
        if self.packets_processed == 0 {
            return 1.0;
        }
        self.packets_forwarded as f64 / self.packets_processed as f64
    }

    /// Update metrics with new packet
    pub fn record_packet(&mut self, forwarded: bool) {
        self.packets_processed += 1;
        if forwarded {
            self.packets_forwarded += 1;
        } else {
            self.packets_dropped += 1;
        }
    }

    /// Update latency metric (exponential moving average)
    pub fn update_latency(&mut self, latency_ms: f64) {
        const ALPHA: f64 = 0.1; // Smoothing factor
        if self.avg_latency_ms == 0.0 {
            self.avg_latency_ms = latency_ms;
        } else {
            self.avg_latency_ms = ALPHA * latency_ms + (1.0 - ALPHA) * self.avg_latency_ms;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_node_base_reputation() {
        let node = NodeReputation::new("test-node".to_string());
        assert_eq!(node.reputation_points, 100);
        assert_eq!(node.reputation, 0.5);
        assert_eq!(node.score, 0.5);
    }

    #[test]
    fn test_reputation_action_points() {
        assert_eq!(ReputationAction::SuccessfulTask.points_delta(), 10);
        assert_eq!(ReputationAction::UptimeMilestone.points_delta(), 5);
        assert_eq!(ReputationAction::HighQualityService.points_delta(), 20);
        assert_eq!(ReputationAction::TaskFailure.points_delta(), -15);
        assert_eq!(ReputationAction::DroppedConnection.points_delta(), -25);
        assert_eq!(ReputationAction::MaliciousBehavior.points_delta(), -50);
    }

    #[test]
    fn test_apply_action() {
        let mut node = NodeReputation::new("test".to_string());

        // Success increases reputation
        node.apply_action(ReputationAction::SuccessfulTask);
        assert_eq!(node.reputation_points, 110);

        // Failure decreases reputation
        node.apply_action(ReputationAction::TaskFailure);
        assert_eq!(node.reputation_points, 95);
    }

    #[test]
    fn test_reputation_bounds() {
        let mut node = NodeReputation::new("test".to_string());

        // Cannot go below 0
        for _ in 0..10 {
            node.apply_action(ReputationAction::MaliciousBehavior);
        }
        assert_eq!(node.reputation_points, 0);

        // Cannot go above 200
        let mut node2 = NodeReputation::new("test2".to_string());
        for _ in 0..20 {
            node2.apply_action(ReputationAction::HighQualityService);
        }
        assert_eq!(node2.reputation_points, 200);
    }

    #[test]
    fn test_decay_mechanism() {
        let mut node = NodeReputation::new("test".to_string());
        node.reputation_points = 100;

        // Apply 1 day decay
        node.apply_decay(1);
        assert_eq!(node.reputation_points, 99); // 100 * 0.99 = 99

        // Apply 10 days decay
        node.reputation_points = 100;
        node.apply_decay(10);
        assert_eq!(node.reputation_points, 90); // 100 * 0.99^10 ≈ 90
    }

    #[test]
    fn test_cost_of_forgery() {
        let mut node = NodeReputation::with_stake("test".to_string(), 10000);
        node.reputation_points = 150;

        let cost = node.cost_of_forgery();
        assert!(cost > 1.0, "High reputation + stake should have high cost");

        let mut low_node = NodeReputation::with_stake("low".to_string(), 100);
        low_node.reputation_points = 50;

        let low_cost = low_node.cost_of_forgery();
        assert!(cost > low_cost, "Higher reputation should cost more to forge");
    }

    #[test]
    fn test_reputation_manager_basic() {
        let mut manager = ReputationManager::new();
        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();

        manager.add_node(addr, 5000);
        assert_eq!(manager.node_count(), 1);

        let rep = manager.get_reputation(&addr).unwrap();
        assert_eq!(rep.reputation_points, 100);
        assert_eq!(rep.stake, 5000);
    }

    #[test]
    fn test_reputation_manager_updates() {
        let mut manager = ReputationManager::new();
        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();

        manager.add_node(addr, 1000);

        // Apply successful task
        manager.update_reputation(&addr, ReputationAction::SuccessfulTask).unwrap();
        assert_eq!(manager.get_reputation_points(&addr), 110);

        // Apply failure
        manager.update_reputation(&addr, ReputationAction::TaskFailure).unwrap();
        assert_eq!(manager.get_reputation_points(&addr), 95);
    }

    #[test]
    fn test_weighted_candidates() {
        let mut manager = ReputationManager::new();

        let addr1: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let addr2: SocketAddr = "127.0.0.1:8081".parse().unwrap();
        let addr3: SocketAddr = "127.0.0.1:8082".parse().unwrap();

        manager.add_node(addr1, 5000);
        manager.add_node(addr2, 3000);
        manager.add_node(addr3, 1000);

        // Boost addr1 reputation
        manager.update_reputation(&addr1, ReputationAction::HighQualityService).unwrap();
        manager.update_reputation(&addr1, ReputationAction::SuccessfulTask).unwrap();

        // All nodes start with 100 points, addr1 now has 130 points
        // Get candidates with >= 100 points (all 3 nodes qualify)
        let candidates = manager.get_weighted_relay_candidates(100);
        assert_eq!(candidates.len(), 3); // addr1, addr2, and addr3 all have >= 100 points

        // Get candidates with > 100 points (only addr1)
        let high_candidates = manager.get_weighted_relay_candidates(101);
        assert_eq!(high_candidates.len(), 1); // Only addr1 has > 100 points
    }

    #[test]
    fn test_persistence() {
        let mut manager = ReputationManager::new();
        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();

        manager.add_node(addr, 5000);
        manager.update_reputation(&addr, ReputationAction::SuccessfulTask).unwrap();

        // Save to JSON
        let json = manager.save_to_json().unwrap();

        // Load into new manager
        let mut manager2 = ReputationManager::new();
        manager2.load_from_json(&json).unwrap();

        assert_eq!(manager2.get_reputation_points(&addr), 110);
    }
}
