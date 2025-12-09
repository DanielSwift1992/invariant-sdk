//! Python Bindings for Invariant Kernel

use pyo3::prelude::*;

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

#[pymodule]
fn invariant_kernel(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(crystallize_all, m)?)?;
    m.add_function(wrap_pyfunction!(crystallize_hnsw, m)?)?;
    Ok(())
}
