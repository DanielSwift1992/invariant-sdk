//! Python Bindings for Invariant Kernel

use pyo3::prelude::*;

// ============================================================================
// MERKLE: Canonical Identity
// ============================================================================

/// Get canonical Merkle hash for a token/string
#[pyfunction]
fn get_token_hash_hex(s: &str) -> String {
    crate::merkle::get_token_hash_hex(s)
}

/// Get edge identity (first 16 chars of SHA256(u:rel:v))
#[pyfunction]
fn bond_id(u: &str, v: &str, rel: &str) -> String {
    crate::merkle::bond_id(u, v, rel)
}

// ============================================================================
// CRYSTALLIZE: Vector Similarity
// ============================================================================

/// Brute-force all-pairs cosine similarity (O(N²))
#[pyfunction]
fn crystallize_all(vectors: Vec<Vec<f32>>, threshold: f32) -> Vec<(usize, usize, f32)> {
    let results = crate::start_crystal::compute_correlations_parallel(&vectors, threshold);
    results.into_iter().map(|r| (r.source_idx, r.target_idx, r.score)).collect()
}

/// HNSW approximate nearest neighbors (O(N log N))
#[pyfunction]
fn crystallize_hnsw(vectors: Vec<Vec<f32>>, threshold: f32, top_k: usize) -> Vec<(usize, usize, f32)> {
    let results = crate::hnsw_crystal::crystallize_hnsw(&vectors, threshold, top_k);
    results.into_iter().map(|r| (r.source_idx, r.target_idx, r.score)).collect()
}

// ============================================================================
// INVARIANT METRICS
// ============================================================================

/// Get invariant metrics for a string: (weight, depth, leaves, shape_hash)
#[pyfunction]
fn get_invariant_metrics(s: &str, atomic: bool) -> (u32, u32, u32, u64) {
    crate::merkle::get_invariant_metrics(s, atomic)
}

// ============================================================================
// MODULE EXPORT
// ============================================================================

#[pymodule]
fn invariant_kernel(_py: Python, m: &PyModule) -> PyResult<()> {
    // Merkle
    m.add_function(wrap_pyfunction!(get_token_hash_hex, m)?)?;
    m.add_function(wrap_pyfunction!(bond_id, m)?)?;
    m.add_function(wrap_pyfunction!(get_invariant_metrics, m)?)?;
    // Crystallize
    m.add_function(wrap_pyfunction!(crystallize_all, m)?)?;
    m.add_function(wrap_pyfunction!(crystallize_hnsw, m)?)?;
    Ok(())
}

