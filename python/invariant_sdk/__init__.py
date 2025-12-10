"""
Invariant SDK
=============

Deterministic Knowledge Engine - Python SDK

Usage:
    from invariant_sdk import InvariantEngine, SearchMode, get_prompt

    engine = InvariantEngine("./data")
    engine.ingest("doc1", "text...", cuts=[5, 10])
    results = engine.resonate("query")
    
    # For AI agents:
    bot_prompt = get_prompt()  # Full operator prompt
    api_only = get_prompt("api")  # Just API reference
"""

from .engine import InvariantEngine
from .types import SearchMode, Block, Relation
from .prompt import get_prompt

__version__ = "34.1.0"
__all__ = ["InvariantEngine", "SearchMode", "Block", "Relation", "get_prompt"]

