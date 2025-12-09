//! Invariant Kernel - Rust Acceleration Core
//! 
//! Provides high-performance crystallization (vector similarity) functions
//! for the Invariant SDK.

mod start_crystal;
mod hnsw_crystal;

#[cfg(feature = "python")]
mod bindings;
