"""
invariant_sdk/tools/agent.py — Structural Agent

L0-Compliant document processor.
Uses LLM as "Blind Surgeon" - returns only indices and labels.
SDK performs all actual operations on text.

Principles:
- LLM returns numbers/labels, not text (no hallucination risk)
- Strict validation (Membrane Law: reject invalid, never save garbage)
- Conservation Law enforced by SDK
- No retry logic (client's responsibility)
"""

from typing import List, Callable
import json
import logging

logger = logging.getLogger("invariant_sdk.agent")

VALID_RELATIONS = frozenset(["IMP", "NOT", "EQUALS", "GATE"])


class IngestionError(Exception):
    """Raised when LLM returns invalid data."""
    pass


class StructuralAgent:
    """
    L0-Compliant document processor.
    
    Usage:
        def my_llm(prompt: str) -> str:
            return openai.chat(...).content
        
        agent = StructuralAgent(engine, llm=my_llm)
        agent.digest("doc1", text)
    
    Raises IngestionError if LLM returns invalid data.
    Retry logic is client's responsibility.
    """
    
    SEGMENT_PROMPT = """Segment text into minimal semantic units.

A semantic unit is the smallest piece with standalone meaning:
- A statement, question, command, or definition
- Keep linking words (but, therefore) inside the unit they belong to

TEXT LENGTH: {text_len}
TEXT:
{text}

Return JSON array of integer positions where new units start.
Exclude 0 and {text_len}. Positions must be ascending.

Example: [45, 120, 200]

Return ONLY the JSON array:"""

    CLASSIFY_PROMPT = """Classify relations between consecutive blocks.

PAIRS:
{pairs}

Relation types:
- IMP: first implies/explains second
- NOT: first contradicts second
- EQUALS: same meaning
- GATE: first conditions second

Return JSON array of relation strings.
Example: ["IMP", "NOT", "IMP"]

Return ONLY the JSON array:"""

    def __init__(self, engine, llm: Callable[[str], str]):
        self.engine = engine
        self.llm = llm
    
    def digest(self, source: str, text: str) -> int:
        """
        Process document: segment → store → classify → link.
        
        Raises:
            IngestionError: If LLM returns invalid data
        """
        # 1. Segment
        cuts = self._segment(text)
        
        # 2. Store (Conservation Law enforced by SDK)
        count = self.engine.ingest(source, text, cuts)
        
        # 3. Get blocks
        blocks = self.engine.block_store.get_by_source(source)
        
        if len(blocks) < 2:
            return count
        
        # 4. Classify
        relations = self._classify(blocks)
        
        # 5. Store edges
        from ..core.reactor import Truth
        
        for i, rel in enumerate(relations):
            self.engine.tank.absorb(
                blocks[i]['id'], blocks[i + 1]['id'],
                rel, 1.0, Truth.SIGMA, "agent:syntax"
            )
        
        # 6. Evolve
        self.engine.evolve()
        self.engine._persist()
        
        return count
    
    def _segment(self, text: str) -> List[int]:
        """Get cut positions from LLM. Raises IngestionError if invalid."""
        prompt = self.SEGMENT_PROMPT.format(
            text_len=len(text),
            text=text[:3000] + ("..." if len(text) > 3000 else "")
        )
        
        response = self.llm(prompt)
        return self._parse_cuts(response, len(text))
    
    def _classify(self, blocks: List[dict]) -> List[str]:
        """Get relation types from LLM. Raises IngestionError if invalid."""
        n_pairs = len(blocks) - 1
        
        pairs_text = "\n".join([
            f"{i}: \"{blocks[i]['content'][:60]}...\" → \"{blocks[i+1]['content'][:60]}...\""
            for i in range(n_pairs)
        ])
        
        prompt = self.CLASSIFY_PROMPT.format(pairs=pairs_text)
        response = self.llm(prompt)
        return self._parse_relations(response, n_pairs)
    
    def _parse_cuts(self, response: str, text_len: int) -> List[int]:
        """Parse and validate cut positions."""
        response = self._clean_json(response)
        
        try:
            cuts = json.loads(response)
        except json.JSONDecodeError as e:
            raise IngestionError(f"Invalid JSON from LLM: {e}")
        
        if not isinstance(cuts, list):
            raise IngestionError(f"Expected list, got {type(cuts).__name__}")
        
        if not cuts:
            return []
        
        if not all(isinstance(c, int) for c in cuts):
            raise IngestionError("All cuts must be integers")
        
        for c in cuts:
            if c <= 0 or c >= text_len:
                raise IngestionError(f"Cut {c} out of bounds (0, {text_len})")
        
        return sorted(set(cuts))
    
    def _parse_relations(self, response: str, expected: int) -> List[str]:
        """Parse and validate relation types."""
        response = self._clean_json(response)
        
        try:
            rels = json.loads(response)
        except json.JSONDecodeError as e:
            raise IngestionError(f"Invalid JSON from LLM: {e}")
        
        if not isinstance(rels, list):
            raise IngestionError(f"Expected list, got {type(rels).__name__}")
        
        if len(rels) != expected:
            raise IngestionError(f"Expected {expected} relations, got {len(rels)}")
        
        result = []
        for i, rel in enumerate(rels):
            if not isinstance(rel, str):
                raise IngestionError(f"Relation {i} must be string")
            
            rel = rel.upper().strip()
            if rel not in VALID_RELATIONS:
                raise IngestionError(f"Invalid relation '{rel}'. Valid: {VALID_RELATIONS}")
            
            result.append(rel)
        
        return result
    
    def _clean_json(self, response: str) -> str:
        """Remove markdown code blocks if present."""
        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) >= 2:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]
        return response.strip()
