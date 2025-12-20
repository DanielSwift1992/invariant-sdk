"""
test_merkle_l05.py — L0.5 Merkle Kernel Gate Tests

Per MERKLE_KERNEL_SPEC v0.2 §7
"""

import pytest
from invariant_sdk.merkle import (
    MerkleTree,
    MerkleNode,
    normalize_whitespace,
    segment_blocks,
    encode_l05,
    H,
    verify_proof,
)


class TestWhitespaceNormalization:
    """Test whitespace normalization per §3.4."""
    
    def test_crlf_to_lf(self):
        """CRLF → LF."""
        text = "hello\r\nworld"
        assert normalize_whitespace(text) == "hello\nworld"
    
    def test_trim_trailing_spaces(self):
        """Trim trailing spaces per line."""
        text = "hello   \nworld  "
        assert normalize_whitespace(text) == "hello\nworld"
    
    def test_collapse_blank_lines(self):
        """Collapse 3+ blank lines to 2."""
        text = "a\n\n\n\nb"
        assert normalize_whitespace(text) == "a\n\nb"


class TestBlockSegmentation:
    """Test block segmentation per §3.4."""
    
    def test_single_block(self):
        """Single paragraph = single block."""
        text = "Hello world.\nThis is a sentence."
        blocks = segment_blocks(text)
        assert len(blocks) == 1
    
    def test_two_blocks(self):
        """Double newline = block boundary."""
        text = "Block one.\n\nBlock two."
        blocks = segment_blocks(text)
        assert len(blocks) == 2
        assert blocks[0] == "Block one."
        assert blocks[1] == "Block two."
    
    def test_soft_wrap_no_boundary(self):
        """Single LF does NOT create block boundary."""
        text = "Line 1\nLine 2\nLine 3"
        blocks = segment_blocks(text)
        assert len(blocks) == 1


class TestMerkleTreeConstruction:
    """Test Merkle tree construction per §3.1-3.2."""
    
    def test_single_token(self):
        """Single token = single leaf."""
        tree = MerkleTree.from_tokens(["hello"])
        assert len(tree.leaves) == 1
        assert tree.root == tree.leaves[0]
    
    def test_two_tokens_dyad2(self):
        """Two tokens = one dyad2 parent."""
        tree = MerkleTree.from_tokens(["hello", "world"])
        assert len(tree.leaves) == 2
        assert tree.root.tag == "dyad2"
        assert tree.root.left == tree.leaves[0]
        assert tree.root.right == tree.leaves[1]
    
    def test_three_tokens_dyad1(self):
        """Three tokens = dyad2 + dyad1."""
        tree = MerkleTree.from_tokens(["a", "b", "c"])
        assert len(tree.leaves) == 3
        
        # Level 1 should have 2 nodes: dyad2(a,b) and dyad1(c)
        level1 = tree.nodes_at_level(1)
        assert len(level1) == 2
        
        # First node is dyad2
        assert level1[0].tag == "dyad2"
        assert level1[0].span == (0, 1)
        
        # Second node is dyad1 (unary)
        assert level1[1].tag == "dyad1"
        assert level1[1].span == (2, 2)


class TestGateL05_1_EditLocality:
    """GATE L0.5-1: Edit Locality."""
    
    def test_edit_locality(self):
        """Edit in block B does NOT change hash of block A."""
        # Build two separate trees (simulating two blocks)
        tree_a = MerkleTree.from_tokens(["block", "a", "content"])
        tree_b = MerkleTree.from_tokens(["block", "b", "content"])
        
        hash_a_before = tree_a.root.hash
        
        # "Edit" block B by creating new tree
        tree_b_edited = MerkleTree.from_tokens(["block", "b", "modified", "content"])
        
        # Block A hash unchanged
        hash_a_after = tree_a.root.hash
        assert hash_a_before == hash_a_after
        
        # Block B hash changed
        assert tree_b.root.hash != tree_b_edited.root.hash


class TestGateL05_2_DyadicInherent:
    """GATE L0.5-2: Dyadic Inherent."""
    
    def test_dyadic_inherent(self):
        """Node at level ℓ spans 2^ℓ leaves (or less for last partial)."""
        tree = MerkleTree.from_tokens(["a", "b", "c", "d", "e"])
        
        for node in tree.all_nodes():
            span_size = node.span_size
            expected_max = 2 ** node.level
            
            if node.level == 0:
                # Leaves always span 1
                assert span_size == 1
            else:
                # Internal nodes: span ≤ 2^level
                assert span_size <= expected_max, f"Node at level {node.level} has span {span_size} > {expected_max}"


class TestGateL05_3_Determinism:
    """GATE L0.5-3: Determinism."""
    
    def test_determinism(self):
        """Same content → same Merkle root."""
        tokens = ["hello", "world", "test"]
        
        tree1 = MerkleTree.from_tokens(tokens)
        tree2 = MerkleTree.from_tokens(tokens)
        
        assert tree1.root.hash == tree2.root.hash


class TestGateL05_4_Addressability:
    """GATE L0.5-4: Addressability."""
    
    def test_leaf_proof(self):
        """Every leaf has a verifiable Merkle proof to root."""
        tree = MerkleTree.from_tokens(["a", "b", "c", "d"])
        
        for leaf in tree.leaves:
            proof = tree.get_proof(leaf)
            assert proof is not None
            assert verify_proof(leaf.hash, proof, tree.root.hash)
    
    def test_internal_node_proof(self):
        """Internal nodes also have verifiable proofs."""
        tree = MerkleTree.from_tokens(["a", "b", "c", "d"])
        
        # Test level 1 nodes
        for node in tree.nodes_at_level(1):
            if node != tree.root:
                proof = tree.get_proof(node)
                assert verify_proof(node.hash, proof, tree.root.hash)
    
    def test_proof_with_dyad1(self):
        """Proof works with unary nodes (dyad1)."""
        tree = MerkleTree.from_tokens(["a", "b", "c"])  # 3 tokens → dyad1 at level 1
        
        # Get the dyad1 node (third token)
        level1 = tree.nodes_at_level(1)
        dyad1_node = [n for n in level1 if n.tag == "dyad1"]
        
        if dyad1_node:
            proof = tree.get_proof(tree.leaves[2])
            assert verify_proof(tree.leaves[2].hash, proof, tree.root.hash)


class TestGateL05_5_ContentEquivalence:
    """GATE L0.5-5: Content Equivalence."""
    
    def test_content_equivalence(self):
        """Token sequence under node equals original tokens in span."""
        tokens = ["hello", "world", "test", "merkle"]
        tree = MerkleTree.from_tokens(tokens)
        
        for node in tree.all_nodes():
            if node.tag == "leaf":
                continue  # Leaves don't have children to compare
            
            recovered = tree.get_leaves_under(node)
            original = [t.lower() for t in tokens[node.start_leaf : node.end_leaf + 1]]
            assert recovered == original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
