//! HNSW crystallization (O(N log N))

use rayon::prelude::*;
use hnsw_rs::hnsw::Hnsw;
use hnsw_rs::dist::DistCosine;

pub struct EdgeResult {
    pub source_idx: usize,
    pub target_idx: usize,
    pub score: f32,
}

/// Crystallize using HNSW Index (Approximate Nearest Neighbors).
pub fn crystallize_hnsw(
    vectors: &[Vec<f32>], 
    threshold: f32,
    top_k: usize
) -> Vec<EdgeResult> {
    if vectors.is_empty() { return vec![]; }
    let nb_elem = vectors.len();
    
    let max_nb_connection = 16;
    let nb_layer = 16.min((nb_elem as f32).ln().ceil() as usize);
    let ef_construction = 200;
    
    let hnsw: Hnsw<f32, DistCosine> = Hnsw::new(
        max_nb_connection, nb_elem, nb_layer, ef_construction, DistCosine {},
    );
    
    let data_for_insert: Vec<(&Vec<f32>, usize)> = vectors.iter()
        .enumerate()
        .map(|(i, v)| (v, i))
        .collect();
    
    hnsw.parallel_insert(&data_for_insert);
    
    let ef_search = 32.max(top_k);
    let search_k = top_k + 1;
    
    vectors.par_iter().enumerate().flat_map(|(i, query_vec)| {
        hnsw.search(query_vec, search_k, ef_search)
            .into_iter()
            .filter_map(|neighbor| {
                let j = neighbor.d_id;
                let sim = 1.0 - neighbor.distance;
                if i != j && sim > threshold {
                    Some(EdgeResult { source_idx: i, target_idx: j, score: sim })
                } else {
                    None
                }
            })
            .collect::<Vec<_>>()
    }).collect()
}
