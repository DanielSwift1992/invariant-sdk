"""
sdk/types.py — Data Structures for Invariant SDK
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class Relation(Enum):
    """
    Edge Types.
    
    5 fundamental types:
    - IMP: A implies/causes B
    - NOT: A contradicts B
    - EQUALS: A is identical to B
    - GATE: A conditions B
    - OMEGA: Pending classification (for LLM to upgrade)
    """
    IMP = "IMP"
    NOT = "NOT"
    EQUALS = "EQUALS"
    GATE = "GATE"
    OMEGA = "OMEGA"


@dataclass
class Block:
    """A semantic unit of content."""
    id: str
    content: str
    source: str
    embedding: Optional[List[float]] = None
    score: float = 0.0


class SearchMode(Enum):
    """Search strategies."""
    VECTOR = "vector"         # Semantic similarity (embeddings)
    MERKLE = "merkle"         # Structural matching (keywords)
    BINOCULAR = "binocular"   # Both combined (default)
    CRYSTAL = "crystal"       # Pure topological (crystal graph)


