#!/usr/bin/env python3
"""
StructuralAgent — Minimal Streaming Protocol (Pure L0)

ONLY streaming protocol. No search, no single-shot, no batch.

Core: LLM → quotes → blocks → Symbol Nodes → Tank edges
"""

import json
import logging
from typing import Callable, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Valid relation types (L0 Physics)
VALID_RELATIONS = {"IMP", "NOT", "EQUALS", "GATE"}


class IngestionError(Exception):
    """LLM returned invalid data."""


@dataclass
class Concept:
    """Concept mention (Pure Topology)."""
    name: str   # e.g., "inflation"
    type: str   # "DEF" or "REF"


@dataclass
class StreamState:
    """Streaming state (Pure L0: only ephemeral pointer)."""
    last_block_id: Optional[str] = None


class StructuralAgent:
    """
    Minimal Agent for streaming text → Tank.
    
    API:
        digest(source, text) → int  # Process document
    
    Internal:
        - LLM extracts quotes + concepts
        - Python finds positions (Agent-Physics separation)
        - Creates Symbol Nodes + edges
    """
    
    # ========================================================================
    # PROMPT
    # ========================================================================
    
    QUOTES_PROMPT = """Given text, identify semantic blocks using QUOTES.

TEXT:
{text}

{context_section}

Return JSON:
{{
  "blocks": [
    {{
      "start_quote": "First few words of block",
      "end_quote": "last few words of block",
      "logic": "IMP|NOT|EQUALS|GATE|ORIGIN",
      "concepts": [
        {{"name": "concept_name", "type": "DEF"}},
        {{"name": "another", "type": "REF"}}
      ]
    }}
  ]
}}

Rules:
1. start_quote/end_quote MUST be exact text from input
2. logic: REQUIRED for blocks 2+. Use ORIGIN only for first block.
   - IMP: block implies/follows from previous
   - NOT: block contradicts previous
   - EQUALS: block restates previous differently
   - GATE: block is conditional on previous
   - ORIGIN: first block only (no predecessor)
3. concepts: list concepts mentioned with type
4. {known_concepts_hint}

IMPORTANT: Use EXACT text for quotes, not paraphrases!
"""

    def __init__(self, engine, llm: Callable[[str], str]):
        """
        Args:
            engine: InvariantEngine
            llm: Callable(prompt: str) -> response: str
        """
        self.engine = engine
        self.llm = llm
    
    # ========================================================================
    # PURE QUERY METHODS
    # ========================================================================
    
    def _get_known_concepts(self) -> List[str]:
        """Query Tank for Symbol Nodes (Pure Function)."""
        symbols = self.engine.block_store.get_by_source('__symbols__')
        return [s['content'] for s in symbols]
    
    def _find_symbol(self, concept_name: str) -> Optional[str]:
        """Find Symbol Node ID."""
        from invariant_kernel import get_token_hash_hex
        symbol_id = get_token_hash_hex(f"symbol:{concept_name}")
        
        if self.engine.block_store.exists(symbol_id):
            return symbol_id
        return None
    
    # ========================================================================
    # MAIN API
    # ========================================================================
    
    def digest(self, source: str, text: str, chunk_size: int = 8000) -> int:
        """
        Process document with auto-streaming.
        
        Args:
            source: Document identifier
            text: Full text
            chunk_size: Characters per chunk
        
        Returns:
            Total blocks created
        """
        state = StreamState()
        total_blocks = 0
        
        # Split into chunks
        chunks = self._split_text(text, chunk_size)
        
        if len(chunks) > 1:
            logger.info(f"Streaming: {len(chunks)} chunks")
        
        for idx, chunk_info in enumerate(chunks):
            if len(chunks) > 1:
                logger.info(f"Chunk {idx+1}/{len(chunks)}")
            
            # Query Tank for known concepts
            known_concepts = self._get_known_concepts()
            
            # LLM analysis
            structure = self._analyze_quotes(
                chunk_info['text'],
                known_concepts=known_concepts,
                is_continuation=(idx > 0)
            )
            
            # Python extracts positions
            blocks = self._extract_blocks(
                chunk_info['text'],
                structure,
                chunk_info['start_global'],
                source
            )
            
            # Create edges
            self._link_blocks(blocks, structure, state)
            
            total_blocks += len(blocks)
        
        return total_blocks
    
    # ========================================================================
    # LLM INTERACTION
    # ========================================================================
    
    def _analyze_quotes(self, text: str, known_concepts: List[str] = None,
                        is_continuation: bool = False) -> dict:
        """
        LLM extracts structure via quotes.
        
        Returns:
            dict with 'blocks' array
        """
        if known_concepts is None:
            known_concepts = []
        
        # Build context
        if is_continuation and known_concepts:
            context = f"CONTEXT: Continuation. Known concepts: {', '.join(known_concepts[:20])}"
        else:
            context = ""
        
        concepts_hint = f"Known: {', '.join(known_concepts[:20])}" if known_concepts else "No prior concepts"
        
        # Call LLM
        prompt = self.QUOTES_PROMPT.format(
            text=text[:10000],
            context_section=context,
            known_concepts_hint=concepts_hint
        )
        
        response = self.llm(prompt)
        
        # Parse & validate
        try:
            response = self._clean_json(response)
            data = json.loads(response)
            
            if 'blocks' not in data:
                raise IngestionError("Missing 'blocks' field")
            
            # Validate
            for i, block in enumerate(data['blocks']):
                if 'start_quote' not in block:
                    raise IngestionError(f"Block {i}: missing start_quote")
                if 'end_quote' not in block:
                    raise IngestionError(f"Block {i}: missing end_quote")
                
                # Normalize and validate logic
                logic = block.get('logic', '').upper() if block.get('logic') else None
                
                if i == 0:
                    # First block: ORIGIN or null is allowed
                    if logic and logic not in VALID_RELATIONS and logic != 'ORIGIN':
                        raise IngestionError(f"Block 0: invalid logic '{logic}'")
                    block['logic'] = logic if logic != 'ORIGIN' else None  # ORIGIN → null
                else:
                    # Subsequent blocks: logic is REQUIRED
                    if not logic:
                        raise IngestionError(f"Block {i}: logic is REQUIRED (use IMP|NOT|EQUALS|GATE)")
                    if logic not in VALID_RELATIONS:
                        raise IngestionError(f"Block {i}: invalid logic '{logic}'")
                    block['logic'] = logic
            
            return data
        
        except json.JSONDecodeError as e:
            raise IngestionError(f"Invalid JSON: {e}")
    
    def _clean_json(self, response: str) -> str:
        """Remove markdown fences."""
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)
        return response.strip()
    
    # ========================================================================
    # BLOCK EXTRACTION
    # ========================================================================
    
    def _extract_blocks(self, text: str, structure: dict,
                        global_offset: int, source: str) -> List[dict]:
        """
        Python finds positions from quotes.
        
        Returns:
            List of block dicts with IDs
        """
        from invariant_kernel import get_token_hash_hex
        
        blocks = []
        cursor = 0
        
        for i, item in enumerate(structure['blocks']):
            start_q = item['start_quote'].strip()
            end_q = item['end_quote'].strip()
            
            # Find positions
            start_pos = text.find(start_q, cursor)
            if start_pos == -1:
                raise IngestionError(f"Block {i}: start_quote not found")
            
            # Check gap (Conservation Law)
            if start_pos > cursor:
                gap = text[cursor:start_pos].strip()
                if gap and len(gap) > 10:
                    raise IngestionError(f"Block {i}: gap detected (Conservation Law)")
            
            end_pos = text.find(end_q, start_pos)
            if end_pos == -1:
                raise IngestionError(f"Block {i}: end_quote not found")
            
            # Extract content
            block_end = end_pos + len(end_q)
            content = text[start_pos:block_end].strip()
            
            # Create ID
            block_id = get_token_hash_hex(content)
            
            # Skip if exists (deduplication)
            if self.engine.block_store.exists(block_id):
                logger.debug(f"Block {i} already exists")
                cursor = block_end
                continue
            
            # Save to store
            self.engine.block_store.save({
                'id': block_id,
                'source': source,
                'content': content,
                'position': global_offset + start_pos
            })
            
            blocks.append({
                'id': block_id,
                'content': content,
                'logic': item.get('logic'),
                'concepts': item.get('concepts', []),
                'source': source
            })
            
            cursor = block_end
        
        # Final check
        if cursor < len(text):
            remainder = text[cursor:].strip()
            if remainder and len(remainder) > 10:
                raise IngestionError("Uncovered text (Conservation Law)")
        
        return blocks
    
    # ========================================================================
    # GRAPH LINKING
    # ========================================================================
    
    def _link_blocks(self, blocks: List[dict], structure: dict,
                     state: StreamState):
        """
        Create edges: temporal + logical + Symbol Nodes.
        """
        from ..core.reactor import Truth
        
        for i, block in enumerate(blocks):
            bid = block['id']
            
            # Temporal edge (always)
            if state.last_block_id:
                self.engine.tank.add_edge_hash(
                    state.last_block_id, bid, "SEQ",
                    energy=1.0, ring=Truth.SIGMA, source="time"
                )
            
            # Logical edge (required for blocks 2+, validated in _analyze_quotes)
            logic = block.get('logic')
            if logic and state.last_block_id:
                self.engine.tank.add_edge_hash(
                    state.last_block_id, bid, logic,
                    energy=0.9, ring=Truth.ETA, source="llm:logic"
                )
            
            # Concept linking (Pure Topology)
            for concept_data in block.get('concepts', []):
                try:
                    concept = Concept(**concept_data)
                    self.link_concept(bid, concept, state)
                except Exception as e:
                    logger.warning(f"Failed to link concept {concept_data}: {e}")
            
            state.last_block_id = bid
    
    # ========================================================================
    # SYMBOL NODES
    # ========================================================================
    
    def create_symbol_node(self, concept_name: str) -> str:
        """
        Create or get Symbol Node (Pure Topology).
        
        Returns:
            Symbol node ID
        """
        from invariant_kernel import get_token_hash_hex
        
        symbol_id = get_token_hash_hex(f"symbol:{concept_name}")
        
        if self.engine.block_store.exists(symbol_id):
            return symbol_id
        
        # Create virtual node
        self.engine.block_store.save({
            'id': symbol_id,
            'source': '__symbols__',
            'content': concept_name,
            'position': 0,
            'is_symbol': True
        })
        
        if self.engine.verbose:
            logger.info(f"Symbol Node: {concept_name} → {symbol_id[:8]}")
        
        return symbol_id
    
    def link_concept(self, block_id: str, concept: Concept, state: StreamState):
        """
        Create DEF/REF edge to Symbol Node.
        """
        from ..core.reactor import Truth
        
        symbol_id = self.create_symbol_node(concept.name)
        
        relation = "DEF" if concept.type == "DEF" else "REF"
        energy = 1.0 if concept.type == "DEF" else 0.8
        
        self.engine.tank.add_edge_hash(
            block_id, symbol_id, relation,
            energy=energy,
            ring=Truth.SIGMA,
            source=f"concept:{concept.name}"
        )
        
        if self.engine.verbose:
            logger.debug(f"{relation}: {block_id[:8]} → {concept.name}")
    
    # ========================================================================
    # TEXT SPLITTING
    # ========================================================================
    
    def _split_text(self, text: str, chunk_size: int) -> List[dict]:
        """
        Split text by paragraphs.
        
        Returns:
            List of {text, start_global}
        """
        paragraphs = text.split('\n\n')
        chunks = []
        i = 0
        
        while i < len(paragraphs):
            chunk_paras = []
            char_count = 0
            
            while i < len(paragraphs) and char_count < chunk_size:
                chunk_paras.append(paragraphs[i])
                char_count += len(paragraphs[i])
                i += 1
            
            if not chunk_paras:
                break
            
            chunk_text = '\n\n'.join(chunk_paras)
            
            # Calculate offset
            prev_paras = paragraphs[:i - len(chunk_paras)]
            start_global = sum(len(p) + 2 for p in prev_paras)
            
            chunks.append({
                'text': chunk_text,
                'start_global': start_global
            })
        
        return chunks
