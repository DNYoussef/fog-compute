//! Core mixnode functionality
//!
//! Contains the main mixnode implementation, configuration, and routing logic.

pub mod mixnode;
pub mod config;
pub mod routing;
pub mod protocol_version;
pub mod relay_lottery;
pub mod reputation;
pub mod compatibility;
pub mod versions;

pub use mixnode::StandardMixnode;
pub use config::MixnodeConfig;
pub use routing::RoutingTable;
pub use protocol_version::{ProtocolVersion, NegotiationResult, FeatureFlags, ProtocolAdvertisement};
pub use relay_lottery::{RelayLottery, WeightedRelay, LotteryProof, LotteryStatistics};
pub use reputation::{
    NodeReputation, ReputationManager, PenaltyType, RewardType, PerformanceMetrics,
    ReputationAction, ReputationHistory, ReputationStatistics,
    ReputationPoints, CostOfForgery
};
pub use compatibility::{PacketAdapter, TranslationContext, Feature};
pub use versions::{VersionRegistry, VersionMetadata, DeprecationTimeline};