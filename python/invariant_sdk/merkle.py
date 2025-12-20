"""
merkle.py — Canonical Topological Merkle Hashing

Single source for token identity in the Python SDK.

Per SPEC_V3 / INVARIANTS.md (Identity):
  - Ω (Origin) and Δ(a,b) (Dyad) define a byte-tree over UTF‑8 strings.
  - Canonical hash = Merkle SHA‑256 over that tree:
        Hash(Ω)       = SHA256(0x00)
        Hash(Δ(a,b))  = SHA256(0x01 || Hash(a) || Hash(b))

L3 projections:
  - `hash16` = first 16 bytes of canonical hash (address / index only)
  - `hash8`  = first 8 bytes of canonical hash (uint64 LE address)

This module mirrors `scripts/merkle.py` and Rust `kernel/src/merkle.rs`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class Node:
    """L0 Dyad node."""
    left: Optional["Node"] = None
    right: Optional["Node"] = None
    _hash: Optional[bytes] = None

    @property
    def is_origin(self) -> bool:
        return self.left is None and self.right is None


# Singleton Origin (Ω)
ORIGIN = Node()


def Dyad(a: Node, b: Node) -> Node:
    return Node(a, b)


def encode_byte(byte_val: int) -> Node:
    """Byte → 8‑depth binary tree (LSB‑first), cons‑listed."""
    chain = ORIGIN
    for i in range(8):
        bit = (byte_val >> i) & 1
        bit_node = ORIGIN if bit == 0 else Dyad(ORIGIN, ORIGIN)
        chain = Dyad(bit_node, chain)
    return chain


def encode_string(s: str) -> Node:
    """UTF‑8 string → chain of byte trees (reversed for cons‑list)."""
    try:
        raw = s.encode("utf-8")
    except UnicodeEncodeError:
        raw = s.encode("utf-8", errors="replace")

    chain = ORIGIN
    for b in reversed(raw):
        chain = Dyad(encode_byte(b), chain)
    return chain


def merkle_hash(node: Node) -> bytes:
    """Recursive Merkle per Identity invariant."""
    if node._hash is not None:
        return node._hash

    if node.is_origin:
        h = hashlib.sha256(b"\x00").digest()
    else:
        lh = merkle_hash(node.left)
        rh = merkle_hash(node.right)
        h = hashlib.sha256(b"\x01" + lh + rh).digest()

    node._hash = h
    return h


from functools import lru_cache

@lru_cache(maxsize=1_000_000)
def get_token_hash_bytes(token: str) -> bytes:
    """Canonical full 32‑byte Merkle identity for a token."""
    return merkle_hash(encode_string(token))


def get_token_hash_hex(token: str) -> str:
    """Canonical full 64‑hex‑char Merkle identity for a token."""
    return get_token_hash_bytes(token).hex()


def get_token_hash16_bytes(token: str) -> bytes:
    """L3 address: first 16 bytes of canonical Merkle hash."""
    return get_token_hash_bytes(token)[:16]


def get_token_hash16_hex(token: str) -> str:
    """L3 address hex: 32 hex chars."""
    return get_token_hash16_bytes(token).hex()


# =============================================================================
# L0.5 MERKLE KERNEL — Canonical Atom Layer
# Per MERKLE_KERNEL_SPEC v0.2
# =============================================================================

from typing import List, Tuple, Dict, Any
import re


def normalize_whitespace(text: str) -> str:
    """
    Whitespace normalization per §3.4:
    - CRLF → LF
    - Trim trailing spaces per line
    - Collapse 3+ blank lines to 2 blank lines
    """
    # CRLF → LF
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Trim trailing spaces per line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Collapse 3+ blank lines to 2
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    
    return text


def segment_blocks(text: str) -> List[str]:
    """
    Segment text into blocks per §3.4:
    - Block = paragraph separated by blank line (exactly 2 consecutive LF)
    - Single LF does NOT create block boundary
    """
    text = normalize_whitespace(text)
    
    # Split by double newline
    blocks = text.split('\n\n')
    
    # Trim each block, filter empty
    blocks = [b.strip() for b in blocks if b.strip()]
    
    return blocks


def encode_l05(tag: str, *children: bytes) -> bytes:
    """
    Domain-separated encoding per §3.0:
    encode = tag || len(child1) || child1 || ...
    """
    result = tag.encode('utf-8')
    for child in children:
        result += len(child).to_bytes(4, 'big') + child
    return result


def H(data: bytes) -> bytes:
    """Hash function (blake2b-256 or sha256)."""
    return hashlib.blake2b(data, digest_size=32).digest()


@dataclass
class MerkleNode:
    """L0.5 Merkle tree node."""
    hash: bytes
    level: int
    start_leaf: int
    end_leaf: int
    tag: str  # "leaf", "dyad1", or "dyad2"
    left: Optional["MerkleNode"] = None
    right: Optional["MerkleNode"] = None
    
    # For leaves only
    token: Optional[str] = None
    anchor_id: Optional[str] = None
    
    @property
    def span(self) -> Tuple[int, int]:
        return (self.start_leaf, self.end_leaf)
    
    @property
    def span_size(self) -> int:
        return self.end_leaf - self.start_leaf + 1


@dataclass
class MerkleTree:
    """L0.5 Merkle tree for a text block."""
    root: MerkleNode
    leaves: List[MerkleNode]
    nodes_by_level: Dict[int, List[MerkleNode]]
    
    @classmethod
    def from_tokens(cls, tokens: List[str], normalize_fn=None) -> "MerkleTree":
        """Build Merkle tree from canonical tokens per §3.1-3.2."""
        if not tokens:
            # Empty tree
            empty_hash = H(encode_l05("leaf", b""))
            root = MerkleNode(
                hash=empty_hash,
                level=0,
                start_leaf=0,
                end_leaf=-1,
                tag="leaf"
            )
            return cls(root=root, leaves=[], nodes_by_level={0: [root]})
        
        # Build leaves
        leaves = []
        for i, token in enumerate(tokens):
            # Normalize token
            if normalize_fn:
                token = normalize_fn(token)
            else:
                token = token.lower()
            
            # Compute hashes
            leaf_token = token.encode('utf-8')
            leaf_hash = H(encode_l05("leaf", leaf_token))
            anchor_id = get_token_hash16_hex("Ġ" + token)[:16]  # hash8
            
            node = MerkleNode(
                hash=leaf_hash,
                level=0,
                start_leaf=i,
                end_leaf=i,
                tag="leaf",
                token=token,
                anchor_id=anchor_id
            )
            leaves.append(node)
        
        # Build tree levels per §3.2
        nodes_by_level = {0: leaves}
        current_level = leaves
        level = 0
        
        while len(current_level) > 1:
            next_level = []
            level += 1
            
            # Dyadic pairing
            j = 0
            while j < len(current_level):
                if j + 1 < len(current_level):
                    # Binary node (dyad2)
                    left = current_level[j]
                    right = current_level[j + 1]
                    parent_hash = H(encode_l05("dyad2", left.hash, right.hash))
                    parent = MerkleNode(
                        hash=parent_hash,
                        level=level,
                        start_leaf=left.start_leaf,
                        end_leaf=right.end_leaf,
                        tag="dyad2",
                        left=left,
                        right=right
                    )
                    j += 2
                else:
                    # Unary node (dyad1) - odd child at end
                    child = current_level[j]
                    parent_hash = H(encode_l05("dyad1", child.hash))
                    parent = MerkleNode(
                        hash=parent_hash,
                        level=level,
                        start_leaf=child.start_leaf,
                        end_leaf=child.end_leaf,
                        tag="dyad1",
                        left=child
                    )
                    j += 1
                
                next_level.append(parent)
            
            nodes_by_level[level] = next_level
            current_level = next_level
        
        root = current_level[0] if current_level else leaves[0]
        return cls(root=root, leaves=leaves, nodes_by_level=nodes_by_level)
    
    def all_nodes(self) -> List[MerkleNode]:
        """All nodes ordered by level, then by span.start_leaf."""
        result = []
        for level in sorted(self.nodes_by_level.keys()):
            nodes = sorted(self.nodes_by_level[level], key=lambda n: n.start_leaf)
            result.extend(nodes)
        return result
    
    def nodes_at_level(self, level: int) -> List[MerkleNode]:
        """Nodes at level ℓ ordered by span.start_leaf per §3.2."""
        nodes = self.nodes_by_level.get(level, [])
        return sorted(nodes, key=lambda n: n.start_leaf)
    
    def get_proof(self, node: MerkleNode) -> List[Tuple[str, Optional[bool], Optional[bytes]]]:
        """
        Generate Merkle proof from node to root per §7.4.
        
        Returns: List of (tag, side, sibling_hash)
        - tag = "dyad1" or "dyad2"
        - side = None for dyad1, True/False for dyad2 (sibling on right/left)
        - sibling_hash = None for dyad1, sibling hash for dyad2
        """
        proof = []
        current = node
        
        # Walk up the tree
        for level in range(node.level, max(self.nodes_by_level.keys())):
            parent_level = self.nodes_by_level.get(level + 1, [])
            
            # Find parent
            parent = None
            for p in parent_level:
                if p.left == current or p.right == current:
                    parent = p
                    break
            
            if parent is None:
                break
            
            if parent.tag == "dyad1":
                # Unary step
                proof.append(("dyad1", None, None))
            else:
                # Binary step
                if parent.left == current:
                    # We're left child, sibling on right
                    proof.append(("dyad2", True, parent.right.hash))
                else:
                    # We're right child, sibling on left
                    proof.append(("dyad2", False, parent.left.hash))
            
            current = parent
        
        return proof
    
    def get_leaves_under(self, node: MerkleNode) -> List[str]:
        """Get token sequence under a node."""
        return [self.leaves[i].token for i in range(node.start_leaf, node.end_leaf + 1)]


def verify_proof(node_hash: bytes, proof: List[Tuple[str, Optional[bool], Optional[bytes]]], root_hash: bytes) -> bool:
    """
    Verify Merkle proof per §7.4.
    """
    current = node_hash
    for (tag, side, sibling) in proof:
        if tag == "dyad1":
            current = H(encode_l05("dyad1", current))
        else:
            if side:  # sibling on right
                current = H(encode_l05("dyad2", current, sibling))
            else:     # sibling on left
                current = H(encode_l05("dyad2", sibling, current))
    return current == root_hash

