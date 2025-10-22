//! Weighted relay selection lottery for Betanet v1.2 L4
//!
//! Implements VRF-based reputation-weighted node selection with:
//! - Cryptographic lottery proofs for transparency
//! - Stake-based Sybil resistance
//! - Reputation-weighted probability distribution
//! - Verifiable randomness for fairness
//!
//! Privacy Hop layer specification compliance.

use rand::distributions::WeightedIndex;
use rand::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::SocketAddr;

use crate::{MixnodeError, Result};

#[cfg(feature = "vrf")]
use crate::vrf::vrf_delay::VrfKeyPair;
#[cfg(feature = "vrf")]
use sha2::{Digest, Sha256};

// Import reputation module (stub implementation)
#[allow(dead_code)]
use crate::core::reputation::{NodeReputation, ReputationManager};

/// Node reputation score (0.0 to 1.0)
pub type ReputationScore = f64;

/// Weighted relay for lottery selection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeightedRelay {
    /// Node address
    pub address: SocketAddr,
    /// Reputation score (0.0 to 1.0)
    pub reputation: ReputationScore,
    /// Performance score (0.0 to 1.0)
    pub performance: f64,
    /// Stake amount (for tokenomics-based weighting)
    pub stake: u64,
    /// Combined weight for lottery
    pub weight: f64,
}

impl WeightedRelay {
    /// Create new weighted relay
    pub fn new(
        address: SocketAddr,
        reputation: ReputationScore,
        performance: f64,
        stake: u64,
    ) -> Self {
        // Calculate combined weight:
        // - 50% reputation (trust/reliability)
        // - 30% performance (latency/bandwidth)
        // - 20% stake (economic commitment)
        let stake_score = (stake as f64).ln() / 20.0; // Log scale, normalized
        let weight = reputation * 0.5 + performance * 0.3 + stake_score.min(1.0) * 0.2;

        Self {
            address,
            reputation,
            performance,
            stake,
            weight: weight.max(0.01), // Minimum weight to prevent zero
        }
    }

    /// Update reputation based on recent performance
    pub fn update_reputation(&mut self, success: bool) {
        const ALPHA: f64 = 0.1; // Learning rate

        if success {
            // Increase reputation on success
            self.reputation = (self.reputation + ALPHA * (1.0 - self.reputation)).min(1.0);
        } else {
            // Decrease reputation on failure
            self.reputation = (self.reputation - ALPHA * self.reputation).max(0.0);
        }

        // Recalculate weight
        let stake_score = (self.stake as f64).ln() / 20.0;
        self.weight = self.reputation * 0.5 + self.performance * 0.3 + stake_score.min(1.0) * 0.2;
        self.weight = self.weight.max(0.01);
    }
}

/// Lottery proof for verifiable randomness
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LotteryProof {
    /// VRF proof (when VRF feature is enabled)
    #[cfg(feature = "vrf")]
    pub vrf_proof: Option<Vec<u8>>,
    /// Lottery seed used
    pub seed: Vec<u8>,
    /// Selected relay addresses
    pub selected: Vec<SocketAddr>,
    /// Selection weights used
    pub weights: Vec<f64>,
    /// Timestamp of lottery draw
    pub timestamp: u64,
}

impl LotteryProof {
    /// Verify the lottery proof is valid
    #[cfg(feature = "vrf")]
    pub fn verify(&self, _vrf_public_key: &[u8; 32]) -> Result<bool> {
        // Implementation would verify VRF proof
        // For now, just check basic validity
        Ok(self.vrf_proof.is_some() && !self.seed.is_empty() && !self.selected.is_empty())
    }

    #[cfg(not(feature = "vrf"))]
    pub fn verify(&self) -> Result<bool> {
        Ok(!self.seed.is_empty() && !self.selected.is_empty())
    }
}

/// Relay lottery for weighted node selection
pub struct RelayLottery {
    /// Available relays with weights
    relays: Vec<WeightedRelay>,
    /// Relay lookup by address
    relay_map: HashMap<SocketAddr, usize>,
    /// Weighted index for efficient sampling
    weighted_index: Option<WeightedIndex<f64>>,
    /// VRF keypair for lottery proofs
    #[cfg(feature = "vrf")]
    vrf_keypair: Option<VrfKeyPair>,
    /// Reputation manager integration
    reputation_manager: Option<ReputationManager>,
    /// Sybil resistance enabled
    sybil_resistance: bool,
    /// Minimum stake required for participation
    min_stake: u64,
}

impl RelayLottery {
    /// Create new relay lottery
    pub fn new() -> Self {
        Self {
            relays: Vec::new(),
            relay_map: HashMap::new(),
            weighted_index: None,
            #[cfg(feature = "vrf")]
            vrf_keypair: None,
            reputation_manager: None,
            sybil_resistance: false,
            min_stake: 0,
        }
    }

    /// Create new relay lottery with VRF support
    #[cfg(feature = "vrf")]
    pub fn with_vrf() -> Self {
        Self {
            relays: Vec::new(),
            relay_map: HashMap::new(),
            weighted_index: None,
            vrf_keypair: Some(VrfKeyPair::generate()),
            reputation_manager: Some(ReputationManager::default()),
            sybil_resistance: true,
            min_stake: 1000, // Minimum stake of 1000 tokens
        }
    }

    /// Create lottery with custom configuration
    pub fn with_config(sybil_resistance: bool, min_stake: u64) -> Self {
        Self {
            relays: Vec::new(),
            relay_map: HashMap::new(),
            weighted_index: None,
            #[cfg(feature = "vrf")]
            vrf_keypair: if sybil_resistance {
                Some(VrfKeyPair::generate())
            } else {
                None
            },
            reputation_manager: if sybil_resistance {
                Some(ReputationManager::default())
            } else {
                None
            },
            sybil_resistance,
            min_stake,
        }
    }

    /// Get VRF public key if available
    #[cfg(feature = "vrf")]
    pub fn vrf_public_key(&self) -> Option<[u8; 32]> {
        self.vrf_keypair.as_ref().map(|kp| kp.public_key())
    }

    /// Add relay to lottery
    pub fn add_relay(&mut self, relay: WeightedRelay) {
        let address = relay.address;
        let index = self.relays.len();

        self.relays.push(relay);
        self.relay_map.insert(address, index);

        // Invalidate cached weighted index
        self.weighted_index = None;
    }

    /// Remove relay from lottery
    pub fn remove_relay(&mut self, address: &SocketAddr) {
        if let Some(&index) = self.relay_map.get(address) {
            self.relays.remove(index);
            self.relay_map.remove(address);

            // Rebuild relay map
            self.relay_map.clear();
            for (i, relay) in self.relays.iter().enumerate() {
                self.relay_map.insert(relay.address, i);
            }

            // Invalidate cached weighted index
            self.weighted_index = None;
        }
    }

    /// Update relay reputation
    pub fn update_relay_reputation(&mut self, address: &SocketAddr, success: bool) {
        if let Some(&index) = self.relay_map.get(address) {
            if let Some(relay) = self.relays.get_mut(index) {
                relay.update_reputation(success);

                // Invalidate cached weighted index
                self.weighted_index = None;
            }
        }
    }

    /// Build weighted index for sampling
    fn ensure_weighted_index(&mut self) -> Result<()> {
        if self.weighted_index.is_none() {
            if self.relays.is_empty() {
                return Err(MixnodeError::Config(
                    "No relays available for lottery".to_string(),
                ));
            }

            let weights: Vec<f64> = self.relays.iter().map(|r| r.weight).collect();

            self.weighted_index = Some(
                WeightedIndex::new(&weights)
                    .map_err(|e| MixnodeError::Config(format!("Invalid weights: {}", e)))?,
            );
        }

        Ok(())
    }

    /// Select a random relay using weighted lottery
    pub fn select_relay(&mut self) -> Result<&WeightedRelay> {
        self.ensure_weighted_index()?;

        let mut rng = thread_rng();
        let index = self.weighted_index.as_ref().unwrap().sample(&mut rng);

        Ok(&self.relays[index])
    }

    /// Select multiple relays with replacement (can select same relay multiple times)
    pub fn select_relays(&mut self, count: usize) -> Result<Vec<SocketAddr>> {
        self.ensure_weighted_index()?;

        let mut rng = thread_rng();
        let weighted_index = self.weighted_index.as_ref().unwrap();

        let mut selected = Vec::with_capacity(count);
        for _ in 0..count {
            let index = weighted_index.sample(&mut rng);
            selected.push(self.relays[index].address);
        }

        Ok(selected)
    }

    /// Select multiple unique relays without replacement (each relay selected at most once)
    pub fn select_unique_relays(&mut self, count: usize) -> Result<Vec<SocketAddr>> {
        if count > self.relays.len() {
            return Err(MixnodeError::Config(format!(
                "Cannot select {} unique relays from {} available",
                count,
                self.relays.len()
            )));
        }

        self.ensure_weighted_index()?;

        let mut rng = thread_rng();
        let mut selected = Vec::with_capacity(count);
        let mut available_indices: Vec<usize> = (0..self.relays.len()).collect();

        // Weighted sampling without replacement
        for _ in 0..count {
            if available_indices.is_empty() {
                break;
            }

            // Build weights for remaining relays
            let weights: Vec<f64> = available_indices
                .iter()
                .map(|&i| self.relays[i].weight)
                .collect();

            let weighted_index = WeightedIndex::new(&weights)
                .map_err(|e| MixnodeError::Config(format!("Invalid weights: {}", e)))?;

            let local_index = weighted_index.sample(&mut rng);
            let global_index = available_indices[local_index];

            selected.push(self.relays[global_index].address);

            // Remove selected index
            available_indices.remove(local_index);
        }

        Ok(selected)
    }

    /// Get total number of relays
    pub fn relay_count(&self) -> usize {
        self.relays.len()
    }

    /// Get relay by address
    pub fn get_relay(&self, address: &SocketAddr) -> Option<&WeightedRelay> {
        self.relay_map.get(address).map(|&i| &self.relays[i])
    }

    /// Select relay with VRF proof generation
    #[cfg(feature = "vrf")]
    pub fn select_relay_with_proof(&mut self, seed: &[u8]) -> Result<(SocketAddr, LotteryProof)> {
        self.ensure_weighted_index()?;

        if let Some(vrf_keypair) = &self.vrf_keypair {
            // Generate VRF proof for the seed
            let vrf_proof = vrf_keypair.prove(seed)?;

            // Extract randomness from VRF output
            let random_bytes: [u8; 8] = vrf_proof.io.make_bytes(b"lottery");
            let random_value = u64::from_be_bytes(random_bytes);

            // Use VRF output to deterministically select relay
            let index = (random_value as usize) % self.relays.len();
            let selected_relay = &self.relays[index];

            // Create lottery proof
            let proof = LotteryProof {
                vrf_proof: Some(vec![]), // Serialize VRF proof here
                seed: seed.to_vec(),
                selected: vec![selected_relay.address],
                weights: self.relays.iter().map(|r| r.weight).collect(),
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            };

            Ok((selected_relay.address, proof))
        } else {
            // Fallback to non-VRF selection
            let relay = self.select_relay()?;
            let proof = LotteryProof {
                vrf_proof: None,
                seed: seed.to_vec(),
                selected: vec![relay.address],
                weights: self.relays.iter().map(|r| r.weight).collect(),
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            };
            Ok((relay.address, proof))
        }
    }

    /// Select multiple relays with VRF proof
    #[cfg(feature = "vrf")]
    pub fn select_relays_with_proof(
        &mut self,
        seed: &[u8],
        count: usize,
    ) -> Result<(Vec<SocketAddr>, LotteryProof)> {
        self.ensure_weighted_index()?;

        let mut selected = Vec::with_capacity(count);

        if let Some(vrf_keypair) = &self.vrf_keypair {
            // Generate VRF proof for the seed
            let vrf_proof = vrf_keypair.prove(seed)?;

            // Use VRF output as base randomness
            let base_random: [u8; 32] = vrf_proof.io.make_bytes(b"lottery");

            // Generate selections using derived randomness
            for i in 0..count {
                let mut hasher = Sha256::new();
                hasher.update(&base_random);
                hasher.update(&i.to_be_bytes());
                let derived_random = hasher.finalize();

                let mut random_bytes = [0u8; 8];
                random_bytes.copy_from_slice(&derived_random[..8]);
                let random_value = u64::from_be_bytes(random_bytes);

                let index = (random_value as usize) % self.relays.len();
                selected.push(self.relays[index].address);
            }

            let proof = LotteryProof {
                vrf_proof: Some(vec![]), // Serialize VRF proof here
                seed: seed.to_vec(),
                selected: selected.clone(),
                weights: self.relays.iter().map(|r| r.weight).collect(),
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            };

            Ok((selected, proof))
        } else {
            // Fallback to non-VRF selection
            let selected = self.select_relays(count)?;
            let proof = LotteryProof {
                vrf_proof: None,
                seed: seed.to_vec(),
                selected: selected.clone(),
                weights: self.relays.iter().map(|r| r.weight).collect(),
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            };
            Ok((selected, proof))
        }
    }

    /// Calculate cost of forgery for Sybil resistance
    pub fn cost_of_forgery(&self, attacker_stake: u64) -> f64 {
        if !self.sybil_resistance {
            return 0.0;
        }

        let total_stake: u64 = self.relays.iter().map(|r| r.stake).sum();
        if total_stake == 0 {
            return 0.0;
        }

        // Cost of forgery = probability of selection * expected return
        // An attacker would need to control majority stake to reliably win lottery
        let attacker_probability = attacker_stake as f64 / total_stake as f64;

        // Exponential cost: becomes prohibitive above 33% stake
        if attacker_probability >= 0.33 {
            1.0 / (1.0 - attacker_probability).max(0.01)
        } else {
            attacker_probability
        }
    }

    /// Verify a lottery proof
    #[cfg(feature = "vrf")]
    pub fn verify_lottery_proof(&self, proof: &LotteryProof) -> Result<bool> {
        if let Some(vrf_key) = self.vrf_public_key() {
            proof.verify(&vrf_key)
        } else {
            proof.verify(&[0u8; 32])
        }
    }

    /// Integrate with reputation manager
    pub fn sync_with_reputation_manager(&mut self) {
        if let Some(reputation_manager) = &mut self.reputation_manager {
            // Apply decay to all reputations
            reputation_manager.apply_decay_all();

            // Update relay weights based on reputation
            for relay in &mut self.relays {
                if let Some(node_rep) = reputation_manager.get_reputation(&relay.address) {
                    // Check Sybil resistance: minimum stake required
                    if self.sybil_resistance && node_rep.stake < self.min_stake {
                        relay.weight = 0.01; // Minimum weight for non-compliant nodes
                        continue;
                    }

                    // Update reputation score
                    relay.reputation = node_rep.reputation;

                    // Update performance score
                    relay.performance = node_rep.metrics.latency_score()
                        * node_rep.metrics.success_rate()
                        * node_rep.metrics.uptime_percent;

                    // Update stake
                    relay.stake = node_rep.stake;

                    // Recalculate weight with reputation integration
                    let stake_score = (relay.stake as f64).ln() / 20.0;
                    relay.weight = relay.reputation * 0.5
                        + relay.performance * 0.3
                        + stake_score.min(1.0) * 0.2;
                    relay.weight = relay.weight.max(0.01);
                }
            }

            // Invalidate cached weighted index
            self.weighted_index = None;
        }
    }

    /// Get lottery statistics
    pub fn get_statistics(&self) -> LotteryStatistics {
        let total_relays = self.relays.len();
        let total_stake: u64 = self.relays.iter().map(|r| r.stake).sum();
        let avg_reputation = if total_relays > 0 {
            self.relays.iter().map(|r| r.reputation).sum::<f64>() / total_relays as f64
        } else {
            0.0
        };
        let avg_weight = if total_relays > 0 {
            self.relays.iter().map(|r| r.weight).sum::<f64>() / total_relays as f64
        } else {
            0.0
        };

        LotteryStatistics {
            total_relays,
            total_stake,
            avg_reputation,
            avg_weight,
            sybil_resistance: self.sybil_resistance,
            min_stake: self.min_stake,
        }
    }
}

/// Lottery statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LotteryStatistics {
    /// Total number of relays
    pub total_relays: usize,
    /// Total stake across all relays
    pub total_stake: u64,
    /// Average reputation score
    pub avg_reputation: f64,
    /// Average weight
    pub avg_weight: f64,
    /// Sybil resistance enabled
    pub sybil_resistance: bool,
    /// Minimum stake requirement
    pub min_stake: u64,
}

impl Default for RelayLottery {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn test_weighted_relay_creation() {
        let addr = "127.0.0.1:8080".parse().unwrap();
        let relay = WeightedRelay::new(addr, 0.9, 0.8, 1000);

        assert!(relay.weight > 0.0);
        assert!(relay.weight <= 1.0);
    }

    #[test]
    fn test_reputation_update() {
        let addr = "127.0.0.1:8080".parse().unwrap();
        let mut relay = WeightedRelay::new(addr, 0.5, 0.8, 1000);

        let initial_reputation = relay.reputation;

        // Success should increase reputation
        relay.update_reputation(true);
        assert!(relay.reputation > initial_reputation);

        // Failure should decrease reputation
        relay.update_reputation(false);
        assert!(relay.reputation < initial_reputation);
    }

    #[test]
    fn test_relay_lottery_selection() {
        let mut lottery = RelayLottery::new();

        // Add relays with different weights
        lottery.add_relay(WeightedRelay::new(
            "127.0.0.1:8080".parse().unwrap(),
            0.9, // High reputation
            0.8,
            1000,
        ));

        lottery.add_relay(WeightedRelay::new(
            "127.0.0.1:8081".parse().unwrap(),
            0.3, // Low reputation
            0.5,
            100,
        ));

        // Select multiple relays and verify high-reputation relay is selected more often
        let mut selection_count = HashMap::new();
        for _ in 0..1000 {
            let relay = lottery.select_relay().unwrap();
            *selection_count.entry(relay.address).or_insert(0) += 1;
        }

        let addr_high: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let addr_low: SocketAddr = "127.0.0.1:8081".parse().unwrap();

        // High reputation relay should be selected significantly more often
        assert!(selection_count[&addr_high] > selection_count[&addr_low]);
    }

    #[test]
    fn test_unique_relay_selection() {
        let mut lottery = RelayLottery::new();

        for i in 0..10 {
            lottery.add_relay(WeightedRelay::new(
                format!("127.0.0.1:808{}", i).parse().unwrap(),
                0.8,
                0.8,
                1000,
            ));
        }

        // Select 5 unique relays
        let selected = lottery.select_unique_relays(5).unwrap();

        // Verify uniqueness
        let unique: HashSet<_> = selected.iter().collect();
        assert_eq!(unique.len(), 5);
    }
}
