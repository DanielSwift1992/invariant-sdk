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

