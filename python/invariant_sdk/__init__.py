"""
Invariant SDK (Halo-first)
==========================

This repo's production path is the **Halo pipeline**:
  - canonical Merkle hashing (SPEC_V3 / INVARIANTS)
  - v3+ `.crystal` reader (BinaryCrystal + zero-start indexes)
  - HaloClient (Semantic DNS over read-only global crystals)
  - HaloPhysics (Semantic Physics Engine with Bisection Law operations)
  - OverlayGraph (Local σ-facts layered on global α-crystal)

Legacy agent/LLM tooling is archived outside the Halo runtime path.
"""

from .halo import HaloClient, hash8_hex, hash8_hex_merkle
from .crystal import BinaryCrystal, load_crystal
from .merkle import (
    get_token_hash_bytes,
    get_token_hash_hex,
    get_token_hash16_bytes,
    get_token_hash16_hex,
)
from .physics import HaloPhysics, Concept
from .export import to_dot, to_summary
from .overlay import OverlayGraph, find_overlays

__version__ = "34.3.0"
__all__ = [
    # Primary API (HaloPhysics)
    "HaloPhysics",
    "Concept",
    "OverlayGraph",
    "to_dot",
    "to_summary",
    "find_overlays",
    # Lower-level
    "BinaryCrystal",
    "HaloClient",
    "load_crystal",
    # Merkle utilities
    "get_token_hash_bytes",
    "get_token_hash_hex",
    "get_token_hash16_bytes",
    "get_token_hash16_hex",
    "hash8_hex",
    "hash8_hex_merkle",
]

