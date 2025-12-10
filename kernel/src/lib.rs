//! Invariant Kernel - Rust Acceleration Core
//! 
//! Provides high-performance functions for the Invariant SDK:
//! - Merkle hashing (canonical identity)
//! - Crystallization (vector similarity)

pub mod merkle;
mod start_crystal;
mod hnsw_crystal;

#[cfg(feature = "python")]
mod bindings;
