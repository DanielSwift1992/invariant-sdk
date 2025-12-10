//! Merkle Hashing — Canonical Topological Identity
//!
//! Algorithm: String → Byte Tree → Recursive SHA256(0x00|0x01 + L + R)
//! This is the single source of truth for identity computation.

use sha2::{Sha256, Digest};

/// Hash of Origin (Ω): SHA256(0x00)
fn hash_origin() -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(&[0x00]);
    hasher.finalize().into()
}

/// Hash of Dyad Δ(left, right): SHA256(0x01 || left || right)
fn hash_dyad(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(&[0x01]);
    hasher.update(left);
    hasher.update(right);
    hasher.finalize().into()
}

/// Encode a single bit as topology.
/// 0 -> Origin (Ω)
/// 1 -> Dyad(Origin, Origin)
fn encode_bit(bit: u8) -> [u8; 32] {
    if bit == 0 {
        hash_origin()
    } else {
        hash_dyad(&hash_origin(), &hash_origin())
    }
}

/// Encode a byte as 8-depth binary tree (LSB first).
fn encode_byte(byte_val: u8) -> [u8; 32] {
    let mut chain = hash_origin();
    for i in 0..8 {
        let bit = (byte_val >> i) & 1;
        let bit_node = encode_bit(bit);
        chain = hash_dyad(&bit_node, &chain);
    }
    chain
}

/// Encode string as Chain of Byte Trees (reversed for cons-list).
fn encode_string(s: &[u8]) -> [u8; 32] {
    let mut chain = hash_origin();
    for &b in s.iter().rev() {
        let byte_tree = encode_byte(b);
        chain = hash_dyad(&byte_tree, &chain);
    }
    chain
}

/// Canonical Identity Function for Tokens.
/// Returns 64-character hex string.
pub fn get_token_hash_hex(s: &str) -> String {
    let root = encode_string(s.as_bytes());
    hex::encode(root)
}

/// Edge Identity: First 16 chars of SHA256(u:rel:v).
pub fn bond_id(u: &str, v: &str, rel: &str) -> String {
    let raw = format!("{}:{}:{}", u, rel, v);
    let mut hasher = Sha256::new();
    hasher.update(raw.as_bytes());
    let result = hasher.finalize();
    hex::encode(&result[..8]) // 16 hex chars
}

/// Invariant Metrics: (Weight, Depth, Leaves, ShapeHash)
/// 
/// For a string s:
/// - Weight: Total structural complexity (2*len for atomic, more for bit-level)
/// - Depth: Maximum tree depth
/// - Leaves: Number of leaf nodes (Origin nodes)
/// - ShapeHash: Hash of the tree shape (for pattern matching)
/// 
/// Mode:
/// - atomic=true: Each character is an atom (Ω), string is chain of dyads
/// - atomic=false: Full bit-level encoding (8 bits per byte)
pub fn get_invariant_metrics(s: &str, atomic: bool) -> (u32, u32, u32, u64) {
    let bytes = s.as_bytes();
    let len = bytes.len() as u32;
    
    if atomic {
        // Atomic mode: each char = Ω, string = chain of Dyads
        // W = 2*len (len dyads + len atoms = 2*len)
        // D = len
        // L = len + 1 (len atoms + 1 tail Origin)
        let weight = 2 * len;
        let depth = len;
        let leaves = len + 1;
        
        // Shape hash based on length (all same-length strings have same shape)
        let shape_hash = (len as u64).wrapping_mul(0x517cc1b727220a95);
        
        (weight, depth, leaves, shape_hash)
    } else {
        // Bit-level encoding: 8 bits per byte, cons-list structure
        // Each byte = 8 dyads (bits) + 1 chain dyad = 9 nodes
        // String = len bytes chained
        
        // Weight per byte = 17 (8 bit trees of 2 each + 1 chain)
        // Actually it's: bit tree depth 8 with branching
        // Simplified: W = 17*len (approximate)
        let weight = 17 * len;
        let depth = 8 + len; // 8 bits deep + chain depth
        let leaves = len * 9 + 1; // 9 leaves per byte + 1 tail
        
        // Shape depends on bit patterns
        let mut hasher = Sha256::new();
        hasher.update(b"shape:");
        hasher.update(bytes);
        let hash = hasher.finalize();
        let shape_hash = u64::from_le_bytes(hash[0..8].try_into().unwrap());
        
        (weight, depth, leaves, shape_hash)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_determinism() {
        let h1 = get_token_hash_hex("intelligence");
        let h2 = get_token_hash_hex("intelligence");
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_different_inputs() {
        let h1 = get_token_hash_hex("cat");
        let h2 = get_token_hash_hex("dog");
        assert_ne!(h1, h2);
    }

    #[test]
    fn test_bond_id() {
        let b1 = bond_id("a", "b", "IMP");
        let b2 = bond_id("a", "b", "IMP");
        assert_eq!(b1, b2);
        
        let b3 = bond_id("b", "a", "IMP");
        assert_ne!(b1, b3); // Order matters
    }
}
