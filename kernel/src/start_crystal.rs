//! Brute-force crystallization (O(N²))

use rayon::prelude::*;

pub struct EdgeResult {
    pub source_idx: usize,
    pub target_idx: usize,
    pub score: f32,
}

/// Compute all-pairs cosine similarity in parallel.
pub fn compute_correlations_parallel(
    vectors: &[Vec<f32>], 
    threshold: f32
) -> Vec<EdgeResult> {
    if vectors.is_empty() { return vec![]; }
    
    vectors.par_iter().enumerate().flat_map(|(i, v1)| {
        vectors.iter().enumerate().skip(i + 1).filter_map(|(j, v2)| {
            let dot: f32 = v1.iter().zip(v2.iter()).map(|(a, b)| a * b).sum();
            if dot > threshold {
                Some(EdgeResult { source_idx: i, target_idx: j, score: dot })
            } else {
                None
            }
        }).collect::<Vec<_>>()
    }).collect()
}
