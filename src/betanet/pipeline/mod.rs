//! Pipeline modules for packet processing
//!
//! Batching and processing pipeline components.

pub mod batching;

pub use batching::{
    AdaptiveBatchProcessor, AdaptiveBatchingConfig, BatchingStrategy, BatchingStats,
};
