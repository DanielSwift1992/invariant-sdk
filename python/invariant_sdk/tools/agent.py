#!/usr/bin/env python3
"""
StructuralAgent — Clean L0-Compliant Implementation

Key Physics:
1. Conservation Law: Every token preserved, Agent returns indices/labels only
2. Single-Shot Phase 1: One LLM call for cuts + relations
3. k-Sigma Phase 2: Threshold from statistics, not hardcoded
4. Batch Classification: One LLM call for all inter-doc pairs
5. Separation: Agent proposes (η), Physics validates (σ/λ/α)
"""

import json
import logging
from typing import Callable, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Valid relation types (from L0 Physics)
VALID_RELATIONS = {"IMP", "NOT", "EQUALS", "GATE"}


class IngestionError(Exception):
    """Raised when LLM returns invalid data that violates Conservation Law."""
    pass


@dataclass
class Symbol:
    """Symbol definition or reference (backward linking)."""
    block_idx: int           # Which block this applies to
    defines: Optional[str] = None    # Concept defined here (e.g., "var_transmission")
    refers_to: Optional[str] = None  # Concept referenced here


@dataclass
class DocumentStructure:
    """Result of single-shot structure analysis.
    
    Triple Validation:
        - cuts: exact positions (numbers)
        - validation_quotes: text snippets (quotes) 
        - symbols: logical structure (backward links)
    
    All three required to detect LLM hallucinations.
    """
    cuts: List[int]              # Segment boundaries (numbers)
    validation_quotes: List[str]  # Quote from end of each segment (text)
    relations: List[str]          # Relations between consecutive segments  
    symbols: List[Symbol]         # Backward links (projection recovery)


class StructuralAgent:
    """
    LLM-powered Agent for text structure analysis.
    
    Adheres to L0 Physics:
    - Blind Surgeon: Returns positions/labels, not text
    - Conservation Law: All tokens preserved
    - Separation: Agent proposes, Physics validates
    
    Phase 1 (Intra-Document):
        - Single-shot: cuts + relations in one LLM call
        - Creates temporal + logical edges within document
    
    Phase 2 (Inter-Document):
        - k-sigma: Adaptive threshold from score distribution
        - Batch: One LLM call for all candidate pairs
        - Creates logical edges between documents
    """
    
    # ========================================================================
    # PROMPTS
    # ========================================================================
    
    STRUCTURE_PROMPT = """Analyze text structure with TRIPLE VALIDATION.

TEXT ({text_len} chars):
{text}

Output JSON with FOUR REQUIRED fields:

1. "cuts": [int] - exact position where each block ENDS
   - Ascending order, last = {text_len}
   - Example: [45, 120, 200]

2. "validation_quotes": [string] - last 3-5 words of each block (EXACT quote)
   - Used to verify "cuts" are correct
   - Must match text exactly
   - Length MUST equal len(cuts)
   - Example: ["...overheated.", "...broken.", "...completely."]

3. "relations": [string] - relation from block[i] to block[i+1]
   - Length MUST equal len(cuts)
   - Types: IMP, NOT, EQUALS, GATE

4. "symbols": [object] - backward links (optional but encouraged)
   - {{"block": idx, "defines": "concept_name"}}
   - {{"block": idx, "refers_to": "concept_name"}}

Example:
{{
  "cuts": [29, 42, 67],
  "validation_quotes": ["overheated.", "boiling.", "completely."],
  "relations": ["IMP", "IMP"],
  "symbols": [
    {{"block": 0, "defines": "transmission_issue"}},
    {{"block": 2, "refers_to": "transmission_issue"}}
  ]
}}

Return ONLY the JSON object:"""

    BATCH_CLASSIFY_PROMPT = """Classify relations for {count} pairs from DIFFERENT documents.

{pairs_text}

Relation types:
- IMP: one implies/explains the other
- NOT: contradiction
- EQUALS: same meaning, different wording
- GATE: one conditions the other
- NONE: no meaningful relation

Return JSON array of {count} strings: ["rel1", "rel2", ...]
Return ONLY the JSON array:"""

    SEARCH_PROMPT = """Decompose query into atomic sub-queries.

QUERY: {query}

Rules:
- Split distinct concepts
- Keep simple: 1-3 sub-queries
- If already atomic, return list with 1 item

Return JSON list: ["concept A", "concept B"]
Return ONLY the JSON array:"""

    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def __init__(self, engine, llm: Callable[[str], str], k_sigma: float = 3.0):
        """
        Initialize Agent.
        
        Args:
            engine: InvariantEngine instance
            llm: Callable that takes prompt (str) and returns response (str)
            k_sigma: Sigma multiplier for k-sigma threshold (default: 3.0)
                    Higher = more conservative (fewer false positives)
        """
        self.engine = engine
        self.llm = llm
        self.k_sigma = k_sigma
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def digest(self, source: str, text: str) -> int:
        """
        Process document: analyze → store → link → integrate.
        
        Phase 1 (Intra-Document):
            1. LLM analyzes structure (cuts + relations + symbols) — ONE call
            2. Physics stores blocks
            3. Physics creates edges (temporal + logical + backward links)
        
        Phase 2 (Inter-Document):
            4. Physics finds candidates (resonate + k-sigma)
            5. LLM classifies pairs (batch) — ONE call for all
            6. Physics stores inter-doc edges
        
        Phase 3 (Inference):
            7. Physics derives new knowledge (evolve)
        
        Args:
            source: Document identifier
            text: Full text content
        
        Returns:
            Number of blocks created
        
        Raises:
            IngestionError: If LLM returns invalid data
        """
        # --- PHASE 1: SINGLE-SHOT ARCHITECT ---
        structure = self._analyze_structure(text)
        
        # Store blocks (Physics enforces Conservation Law)
        count = self.engine.ingest(source, text, structure.cuts)
        
        # Get created blocks
        blocks = self.engine.block_store.get_by_source(source)
        if not blocks:
            return count
        
        # Store intra-document edges (temporal + logical)
        self._store_intra_edges(blocks, structure.relations)
        
        # Apply symbols (backward links via symbol table)
        self._apply_symbols(blocks, structure.symbols)
        
        # --- PHASE 2: INTER-DOCUMENT INTEGRATION ---
        inter_edges = self._integrate(blocks)
        if self.engine.verbose and inter_edges > 0:
            logger.info(f"Phase 2: Created {inter_edges} inter-document edges")
        
        # --- PHASE 3: LOGICAL INFERENCE ---
        self.engine.evolve()
        self.engine._persist()
        
        return count
    
    def search(self, query: str, limit: int = 10) -> List:
        """
        Smart search with query decomposition.
        
        1. Decomposes query into sub-queries via LLM
        2. Executes resonate() for each
        3. Aggregates (blocks matching multiple concepts rank higher)
        
        Args:
            query: Search query
            limit: Max results
        
        Returns:
            List of Block objects, ranked by relevance
        """
        # 1. Decompose
        sub_queries = self._decompose_query(query)
        if not sub_queries:
            return []
        
        # 2. Search each
        candidates = {}  # block_id -> {block, count}
        
        for sub_q in sub_queries:
            results = self.engine.resonate(sub_q, top_k=limit * 2)
            for block in results:
                bid = block.id
                if bid not in candidates:
                    candidates[bid] = {"block": block, "count": 0}
                candidates[bid]["count"] += 1
        
        # 3. Aggregate (intersection logic)
        ranked = sorted(
            candidates.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        
        return [item["block"] for item in ranked[:limit]]
    
    # ========================================================================
    # PHASE 1: INTRA-DOCUMENT ANALYSIS
    # ========================================================================
    
    def _analyze_structure(self, text: str) -> DocumentStructure:
        """
        Single-shot structure analysis: cuts + relations + symbols in ONE LLM call.
        
        Returns:
            DocumentStructure with cuts, relations, and symbols
        
        Raises:
            IngestionError: If LLM returns invalid data
        """
        text_len = len(text)
        prompt = self.STRUCTURE_PROMPT.format(
            text=text,
            text_len=text_len
        )
        
        response = self.llm(prompt)
        
        # Parse JSON
        try:
            response = self._clean_json(response)
            data = json.loads(response)
            
            cuts = data.get("cuts", [])
            validation_quotes = data.get("validation_quotes", [])
            relations = data.get("relations", [])
            symbols_data = data.get("symbols", [])
            
            # Validate cuts
            if not isinstance(cuts, list):
                raise IngestionError("cuts must be array")
            
            # Validate: ascending order
            for i in range(len(cuts) - 1):
                if cuts[i] >= cuts[i + 1]:
                    raise IngestionError(f"Cuts not ascending: {cuts}")
            
            # Validate: within bounds
            for pos in cuts:
                if not (0 < pos <= text_len):
                    raise IngestionError(f"Cut {pos} out of bounds [1, {text_len}]")
            
            # Validate validation_quotes (LEVEL 1: Text validation)
            if not isinstance(validation_quotes, list):
                raise IngestionError("validation_quotes must be array")
            
            if len(validation_quotes) != len(cuts):
                raise IngestionError(
                    f"validation_quotes length ({len(validation_quotes)}) "
                    f"must equal cuts length ({len(cuts)})"
                )
            
            # TRIPLE VALIDATION: Verify quotes match cuts
            for i, (cut_pos, quote) in enumerate(zip(cuts, validation_quotes)):
                quote = quote.strip()
                if not quote:
                    continue  # Empty quote - skip validation
                
                # Extract text around cut position
                window_start = max(0, cut_pos - len(quote) - 10)
                window_end = min(text_len, cut_pos + 5)
                window = text[window_start:window_end]
                
                # Check if quote appears in window
                if quote not in window:
                    # Try fuzzy match (quote might have minor differences)
                    quote_lower = quote.lower().strip('.,!? ')
                    window_lower = window.lower()
                    
                    if quote_lower not in window_lower:
                        raise IngestionError(
                            f"Validation quote #{i} not found near cut {cut_pos}.\n"
                            f"Quote: '{quote}'\n"
                            f"Window: '{window}'\n"
                            f"LLM hallucination detected!"
                        )
            
            # Validate relations (LEVEL 2: Structure validation)
            if not isinstance(relations, list):
                raise IngestionError("relations must be array")
            
            expected_rels = len(cuts)
            if len(relations) != expected_rels:
                raise IngestionError(
                    f"Expected {expected_rels} relations, got {len(relations)}"
                )
            
            # Validate relation types
            for rel in relations:
                if rel.upper() not in VALID_RELATIONS:
                    raise IngestionError(f"Invalid relation: {rel}")
            
            # Parse symbols
            symbols = []
            if not isinstance(symbols_data, list):
                logger.warning(f"symbols must be list, got {type(symbols_data)}")
            else:
                for sym_item in symbols_data:
                    if not isinstance(sym_item, dict):
                        continue
                    
                    block_idx = sym_item.get("block")
                    defines = sym_item.get("defines")
                    refers_to = sym_item.get("refers_to")
                    
                    # Validate block index
                    if block_idx is None or not (0 <= block_idx < len(cuts)):
                        logger.warning(f"Invalid symbol block index: {block_idx}")
                        continue
                    
                    # Validate: either defines OR refers_to (not both)
                    if defines and refers_to:
                        logger.warning(f"Symbol has both defines and refers_to: {sym_item}")
                        continue
                    
                    if not defines and not refers_to:
                        logger.warning(f"Symbol has neither defines nor refers_to: {sym_item}")
                        continue
                    
                    symbols.append(Symbol(
                        block_idx=block_idx,
                        defines=defines,
                        refers_to=refers_to
                    ))
            
            return DocumentStructure(
                cuts=cuts,
                validation_quotes=validation_quotes,
                relations=[r.upper() for r in relations],
                symbols=symbols
            )
            
        except json.JSONDecodeError as e:
            raise IngestionError(f"Invalid JSON: {e}")
        except KeyError as e:
            raise IngestionError(f"Missing field: {e}")
    
    def _store_intra_edges(self, blocks: List[dict], relations: List[str]):
        """
        Store intra-document edges (temporal + logical).
        
        Args:
            blocks: List of block dicts from block_store
            relations: Relations between consecutive blocks
        """
        from ..core.reactor import Truth
        
        for i in range(len(blocks) - 1):
            # Temporal edge (Layer 0)
            self.engine.tank.absorb(
                blocks[i]['id'], blocks[i + 1]['id'],
                "TEMP", 1.0, Truth.SIGMA, f"seq:{blocks[i]['source']}"
            )
            
            # Logical edge (Layer 1)
            if  i < len(relations):
                self.engine.tank.absorb(
                    blocks[i]['id'], blocks[i + 1]['id'],
                    relations[i], 1.0, Truth.SIGMA, "agent:structure"
                )
    
    def _apply_symbols(self, blocks: List[dict], symbols: List[Symbol]):
        """
        Apply symbol table resolution to create backward edges.
        
        Projection Theory:
            Text linearizes graph → backward edges become invisible.
            Symbols explicitly encode these lost edges.
        
        Algorithm:
            1. Build symbol table: name → block_id (for "defines")
            2. Resolve references: "refers_to" → lookup in table
            3. Create edges: referring_block → defining_block
        
        Args:
            blocks: List of block dicts from block_store
            symbols: List of Symbol objects from LLM
        """
        from ..core.reactor import Truth
        
        # Step 1: Build symbol table
        symbol_table = {}  # name → block_id
        
        for sym in symbols:
            if sym.defines:
                block_id = blocks[sym.block_idx]['id']
                symbol_table[sym.defines] = block_id
                
                if self.engine.verbose:
                    logger.debug(f"Symbol defined: '{sym.defines}' → Block {block_id}")
        
        # Step 2: Resolve references and create backward edges
        edge_count = 0
        for sym in symbols:
            if sym.refers_to:
                target_id = symbol_table.get(sym.refers_to)
                
                if target_id is None:
                    logger.warning(
                        f"Undefined symbol reference: '{sym.refers_to}' "
                        f"in block {sym.block_idx}"
                    )
                    continue
                
                source_id = blocks[sym.block_idx]['id']
                
                # Validate: backward link only (refers_to earlier block)
                if source_id == target_id:
                    logger.warning(f"Self-reference ignored: {sym.refers_to}")
                    continue
                
                # Create backward edge (REF type)
                self.engine.tank.absorb(
                    source_id, target_id,
                    "REF", 1.0, Truth.SIGMA, f"symbol:{sym.refers_to}"
                )
                edge_count += 1
                
                if self.engine.verbose:
                    logger.debug(
                        f"Backward edge: Block {source_id} → {target_id} "
                        f"(symbol: {sym.refers_to})"
                    )
        
        if self.engine.verbose and edge_count > 0:
            logger.info(f"Phase 1: Created {edge_count} backward edges via symbols")
    
    # ========================================================================
    # PHASE 2: INTER-DOCUMENT INTEGRATION
    # ========================================================================
    
    def _integrate(self, new_blocks: List[dict]) -> int:
        """
        Phase 2: Link new blocks to existing knowledge.
        
        Strategy (L0 Physics compliant):
        1. For each block, resonate() to find candidates (cheap vector search)
        2. Compute k-sigma threshold from score distribution
        3. Filter candidates above threshold (Ice vs Water)
        4. Batch classify all pairs (ONE LLM call)
        5. Store validated edges
        
        Args:
            new_blocks: List of newly created blocks
        
        Returns:
            Number of inter-document edges created
        """
        if not new_blocks:
            return 0
        
        new_source = new_blocks[0]['source']
        
        # Step 1: Collect all candidates (Physics proposes)
        all_scores = []
        candidate_pairs = []  # (block, candidate_block)
        
        for block in new_blocks:
            # Skip short blocks (noise filter)
            if len(block['content']) < 30:
                continue
            
            try:
                # Resonate: find similar blocks (cheap!)
                results = self.engine.resonate(block['content'], top_k=10)
                
                # Collect scores for k-sigma calculation
                external_results = [
                    r for r in results 
                    if r.source != new_source
                ]
                
                for r in external_results:
                    all_scores.append(r.score)
                    candidate_pairs.append((block, r))
                    
            except Exception as e:
                logger.warning(f"Resonate failed for block {block['id']}: {e}")
                continue
        
        if not all_scores:
            return 0  # No external candidates found
        
        # Step 2: k-Sigma Calibration (Physics determines threshold)
        threshold = self._compute_ksigma_threshold(all_scores)
        
        # Step 3: Filter by threshold (Ice vs Water)
        hot_pairs = [
            (block, cand) for block, cand in candidate_pairs
            if cand.score > threshold
        ]
        
        if not hot_pairs:
            return 0  # All candidates below threshold (Water phase)
        
        # Step 4: Batch Classification (Agent evaluates, ONE call)
        relations = self._classify_batch(hot_pairs)
        
        # Step 5: Store validated edges (Physics accepts)
        from ..core.reactor import Truth
        edge_count = 0
        
        for (block, cand), rel in zip(hot_pairs, relations):
            if rel != "NONE":
                self.engine.tank.absorb(
                    block['id'], cand.id,
                    rel, cand.score, Truth.SIGMA, "agent:integration"
                )
                edge_count += 1
        
        return edge_count
    
    def _compute_ksigma_threshold(self, scores: List[float]) -> float:
        """
        Compute k-sigma threshold for Ice↔Water phase transition.
        
        From TEXT_TOPOLOGY_SPEC.md Section 9:
        "k-sigma threshold is empirical proxy for Ice↔Water transition"
        
        Args:
            scores: List of similarity scores
        
        Returns:
            Threshold value: μ + k*σ
        """
        if len(scores) < 2:
            return 0.5  # Fallback for insufficient data
        
        # Statistics
        mu = sum(scores) / len(scores)
        variance = sum((s - mu) ** 2 for s in scores) / len(scores)
        sigma = variance ** 0.5
        
        # Threshold = μ + k*σ (Ice ↔ Water boundary)
        threshold = mu + self.k_sigma * sigma
        
        if self.engine.verbose:
            logger.debug(
                f"k-sigma calibration: μ={mu:.3f}, σ={sigma:.3f}, "
                f"threshold={threshold:.3f} (k={self.k_sigma})"
            )
        
        return threshold
    
    def _classify_batch(self, pairs: List[tuple]) -> List[str]:
        """
        Classify multiple pairs in ONE LLM call (batch optimization).
        
        MDL Law: One call for N pairs < N calls for N pairs
        
        Args:
            pairs: List of (block_dict, Block) tuples
        
        Returns:
            List of relation strings (same length as pairs)
        """
        if not pairs:
            return []
        
        # Format pairs for prompt
        pairs_text = "\n\n".join([
            f"PAIR {i+1}:\n"
            f"  A (from {block['source']}): {block['content'][:100]}...\n"
            f"  B (from {cand.source}): {cand.content[:100]}..."
            for i, (block, cand) in enumerate(pairs)
        ])
        
        prompt = self.BATCH_CLASSIFY_PROMPT.format(
            count=len(pairs),
            pairs_text=pairs_text
        )
        
        response = self.llm(prompt)
        
        # Parse JSON
        try:
            response = self._clean_json(response)
            relations = json.loads(response)
            
            if not isinstance(relations, list):
                logger.warning(f"Batch classify returned non-list: {relations}")
                return ["NONE"] * len(pairs)
            
            if len(relations) != len(pairs):
                logger.warning(
                    f"Batch classify length mismatch: expected {len(pairs)}, "
                    f"got {len(relations)}"
                )
                # Pad or truncate
                if len(relations) < len(pairs):
                    relations.extend(["NONE"] * (len(pairs) - len(relations)))
                else:
                    relations = relations[:len(pairs)]
            
            # Validate and normalize
            valid_rels = []
            for rel in relations:
                rel_upper = str(rel).upper()
                if rel_upper in VALID_RELATIONS or rel_upper == "NONE":
                    valid_rels.append(rel_upper)
                else:
                    # Invalid relation → NONE (safe fallback)
                    logger.warning(f"Invalid relation '{rel}' → NONE")
                    valid_rels.append("NONE")
            
            return valid_rels
            
        except json.JSONDecodeError as e:
            logger.warning(f"Batch classify JSON parse error: {e}")
            return ["NONE"] * len(pairs)
    
    # ========================================================================
    # SEARCH HELPERS
    # ========================================================================
    
    def _decompose_query(self, query: str) -> List[str]:
        """Decompose complex query into atomic sub-queries."""
        prompt = self.SEARCH_PROMPT.format(query=query)
        response = self.llm(prompt)
        
        try:
            response = self._clean_json(response)
            sub_queries = json.loads(response)
            
            if not isinstance(sub_queries, list):
                return [query]  # Fallback: treat as atomic
            
            return [str(q) for q in sub_queries if q]
            
        except json.JSONDecodeError:
            return [query]  # Fallback: treat as atomic
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def _clean_json(self, response: str) -> str:
        """Remove markdown code fences if present."""
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)
        return response.strip()
