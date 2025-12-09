"""
sdk/api.py — Public API Re-exports

This module provides the stable public interface for the SDK.
All implementation is in engine.py.
"""

# Re-export the main engine and types
from .engine import InvariantEngine
from .types import Block, SearchMode, RefinerStrategy
from .core.reactor import Tank, Reactor, Truth, Edge, Provenance

__all__ = [
    "InvariantEngine",
    "Tank",
    "Reactor",
    "Truth",
    "Edge",
    "Provenance",
    "Block",
    "SearchMode",
    "RefinerStrategy",
]
