"""
sdk/types.py — Data Structures for Invariant SDK
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class Relation(Enum):
    """
    Edge Types (Port Classification Traits).
    
    Only 5 fundamental edge types exist. Everything else reduces to these:
    
    - "X DEFINES Y" → use EQUALS (definition is identity)
    - "X IS_A Y" → use IMP (type hierarchy is implication)
    - "X HAS Y" → use IMP (property is implication)
    - "X RELATED Y" → use OMEGA (pending classification)
    """
    IMP = "IMP"        # Implication: A → B
    NOT = "NOT"        # Contradiction: A ⊥ B  
    EQUALS = "EQUALS"  # Identity: A ≡ B
    GATE = "GATE"      # Custom port (user-defined transformation)
    OMEGA = "OMEGA"    # Unknown / pending classification
    

@dataclass
class Block:
    id: str
    content: str
    source: str
    embedding: Optional[List[float]] = None
    score: float = 0.0


class SearchMode(Enum):
    VECTOR = "vector"
    MERKLE = "merkle"
    BINOCULAR = "binocular"


class RefinerStrategy(Enum):
    KEYWORD = "keyword"
    LLM = "llm"

