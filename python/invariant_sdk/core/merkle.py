#!/usr/bin/env python3
"""
merkle.py — Canonical Topological Merkle Hash

The single source of truth for identity computation.

Algorithm: String → Byte Tree → Recursive SHA256(0x00|0x01 + L + R)
"""

import hashlib


class Node:
    """The Topological Primordial Particle (Dyad)."""
    def __init__(self, left=None, right=None):
        self.left = left
        self.right = right

    @property
    def is_origin(self):
        return self.left is None and self.right is None


ORIGIN = Node()  # The Void (Ω)


def Dyad(a, b):
    return Node(a, b)


def encode_byte(byte_val: int) -> Node:
    """Byte → 8-depth Binary Tree (LSB first)."""
    chain = ORIGIN
    for i in range(8):
        bit = (byte_val >> i) & 1
        bit_node = ORIGIN if bit == 0 else Dyad(ORIGIN, ORIGIN)
        chain = Dyad(bit_node, chain)
    return chain


def encode_string(s: str) -> Node:
    """String → Chain of Byte Trees (reversed for cons-list)."""
    chain = ORIGIN
    for b in reversed(s.encode('utf-8')):
        byte_tree = encode_byte(b)
        chain = Dyad(byte_tree, chain)
    return chain


def merkle_hash(node: Node) -> bytes:
    """Recursive Topological Hash."""
    if node.is_origin:
        return hashlib.sha256(b'\x00').digest()
    else:
        lh = merkle_hash(node.left)
        rh = merkle_hash(node.right)
        return hashlib.sha256(b'\x01' + lh + rh).digest()


def get_token_hash_hex(s: str) -> str:
    """Canonical Identity Function for Tokens."""
    root = encode_string(s)
    return merkle_hash(root).hex()


def get_neuron_hash_hex(layer: int, component: str, idx: int) -> str:
    """Canonical Identity for Neurons."""
    canonical = f"L{layer}.{component}.N{idx}"
    return get_token_hash_hex(canonical)


def bond_id(u: str, v: str, rel: str) -> str:
    """Edge Identity: First 16 chars of SHA256(u:rel:v)."""
    raw = f"{u}:{rel}:{v}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


