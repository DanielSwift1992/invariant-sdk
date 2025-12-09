"""
sdk/engine.py — The Python Implementation of InvariantEngine.
Acts as a bridge between the clean API and the underlying logic components.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

# ============================================================================
# IMPORTS
# ============================================================================

from .core.reactor import Tank, Reactor, Truth, get_token_hash_hex
from .storage import BlockStore, VectorStore, get_embedder, cosine_similarity
from .types import Block, SearchMode, Relation
import logging

# Configure logger
logger = logging.getLogger("invariant_sdk")


class InvariantEngine:
    """
    The Invariant Engine — Deterministic Knowledge Processing.
    
    API:
    - observe(source, text): Ingest documents
    - resonate(query): Search with semantic interference
    - crystallize(): Auto-link similar content
    - evolve(): Run logical inference
    - forget(source): Delete documents
    """

    def __init__(self, data_dir: str = "./data", verbose: bool = False):
        """
        Initialize the engine.
        
        Args:
            data_dir: Directory for persistent storage (blocks.db, vectors.pkl, knowledge.tank)
            verbose: If True, print debug information
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        # Initialize Core Components
        self.tank = Tank()
        
        # Load axioms if present
        axioms_path = self.data_dir / "core_axioms.json"
        if axioms_path.exists():
            self.tank.load_from_file(axioms_path)
        
        # Load knowledge Tank
        tank_path = self.data_dir / "knowledge.tank"
        if hasattr(self.tank, 'load_from_file') and tank_path.exists():
            self.tank.load_from_file(tank_path)
            
        self.block_store = BlockStore(self.data_dir / "blocks.db")
        self.vector_store = VectorStore(self.data_dir / "vectors.pkl")
        self.embedder = get_embedder()
        
    def ingest(self, source: str, data: Union[str, List[str]], cuts: List[int] = None) -> int:
        """
        Validated ingestion with Conservation Law enforcement.
        
        Two modes:
        1. List of strings (recommended): ingest(source, ["Sent 1.", "Sent 2."])
           - No cuts needed, segments are used directly
        2. Raw text + cuts: ingest(source, "raw text", cuts=[10, 20])
           - Validates that cuts perfectly reconstruct the text
        
        Returns:
            Number of blocks created.
        
        Raises:
            ValueError: If Conservation Law is violated.
        """
        # MODE 1: List of strings (from LLM splitter)
        if isinstance(data, list):
            segments = [s for s in data if s]  # Filter empty
            # Conservation is implicit: raw = "".join(segments)
        
        # MODE 2: Raw text (with optional cuts)
        elif isinstance(data, str):
            if cuts is not None:
                cuts = sorted(set([0] + cuts + [len(data)]))
                segments = [data[cuts[i]:cuts[i+1]] for i in range(len(cuts)-1)]
                
                # CONSERVATION LAW: Validate
                if "".join(segments) != data:
                    raise ValueError("Conservation Law violated: cuts don't reconstruct text")
            else:
                # Fallback: paragraph splitting
                segments = [s.strip() for s in data.split('\n\n') if s.strip()]
        else:
            raise ValueError("data must be str or List[str]")
        
        # Store each segment
        count = 0
        prev_id = None
        
        for i, segment in enumerate(segments):
            if not segment.strip():
                continue
                
            block_id = f"{source}:B{i}"
            
            # Store Physical (SQL)
            self.block_store.save(block_id, segment, segment, source, i)
            
            # Store Wave (Vector)
            vec = self.embedder.encode(segment)
            self.vector_store.add(block_id, vec)
            
            # Store Topology (Tank)
            if hasattr(self.tank, 'absorb'):
                # EQUALS: Block identity
                self.tank.absorb(block_id, segment[:50], Relation.EQUALS.value, 1.0, Truth.SIGMA, f"obs:{source}")
                
                # IMP: Temporal sequence
                if prev_id:
                    self.tank.absorb(prev_id, block_id, Relation.IMP.value, 1.0, Truth.SIGMA, f"seq:{source}")
            
            prev_id = block_id
            count += 1
        
        self._persist()
        return count
    
    def observe(self, source: str, content: str) -> int:
        """
        Simple ingestion (paragraph-based splitting).
        
        For LLM-guided segmentation, use ingest() with cut positions.
        """
        return self.ingest(source, content, cuts=None)

    def resonate(self, signal: str, mode: SearchMode = SearchMode.BINOCULAR, top_k: int = 5) -> List[Block]:
        """
        Interference Pattern.
        """
        query_vec = self.embedder.encode(signal)
        results = []
        
        # 1. Right Eye (Vector/Wave)
        vector_hits = self.vector_store.search(query_vec, top_k=top_k*2)
        
        for bid, v_score in vector_hits:
            raw_block = self.block_store.get(bid)
            if not raw_block: continue
            
            # 2. Left Eye (Merkle/Particle)
            # Simple keyword overlap as proxy for Merkle in Python prototype
            m_score = 0.0
            if mode in [SearchMode.MERKLE, SearchMode.BINOCULAR]:
                signal_words = set(signal.lower().split())
                content_words = set(raw_block['content'].lower().split())
                if signal_words:
                    m_score = len(signal_words & content_words) / len(signal_words)
            
            # 3. Fuse
            final_score = 0.0
            if mode == SearchMode.VECTOR:
                final_score = v_score
            elif mode == SearchMode.MERKLE:
                final_score = m_score
            elif mode == SearchMode.BINOCULAR:
                # Geometric mean: signal multiplication (pure)
                final_score = (v_score * m_score) ** 0.5
            
            if final_score > 0.0:  # No empirical threshold - return all non-zero
                # Convert to SDK Block type
                b = Block(
                    id=bid,
                    content=raw_block['content'],
                    source=raw_block['source'],
                    embedding=self.vector_store.get(bid),
                    score=final_score
                )
                results.append(b)
                
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def crystallize(self, method: str = "threshold", threshold: float = 0.75, top_k: int = 50) -> int:
        """
        Find and link similar blocks (creates OMEGA edges for LLM classification).
        
        Args:
            method: "threshold" (precise, O(N²)) or "hnsw" (fast, O(N log N))
            threshold: Similarity threshold (0.0-1.0). Higher = fewer but stronger links.
            top_k: For HNSW, number of neighbors to consider.
        
        Returns:
            Number of new candidate edges created.
        
        Note:
            Created edges have relation=OMEGA (pending classification).
            Use LLM to upgrade OMEGA→IMP/NOT/EQUALS.
        """
        # Input validation
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError(f"threshold must be 0.0-1.0, got {threshold}")
        if method not in ("threshold", "hnsw"):
            raise ValueError(f"method must be 'threshold' or 'hnsw', got '{method}'")
        
        blocks = self.block_store.get_all()
        if not blocks:
            return 0
        
        new_edges = 0
        
        try:
            import invariant_kernel
            
            # Prepare vectors
            vectors = []
            valid_indices = []
            
            for i, b in enumerate(blocks):
                v = self.vector_store.get(b['id'])
                if v:
                    vectors.append(v)
                    valid_indices.append(i)
            
            if not vectors:
                return 0

            # Run Rust crystallization
            if method == "hnsw":
                matches = invariant_kernel.crystallize_hnsw(vectors, threshold, top_k)
            else:
                matches = invariant_kernel.crystallize_all(vectors, threshold)
            
            for i_local, j_local, sim in matches:
                idx1 = valid_indices[i_local]
                idx2 = valid_indices[j_local]
                b1 = blocks[idx1]
                b2 = blocks[idx2]
                
                # OMEGA: Pending LLM classification
                if hasattr(self.tank, 'absorb'):
                    self.tank.absorb(b1['id'], b2['id'], Relation.OMEGA.value, sim, Truth.ETA, "crystal:rust")
                new_edges += 1
                
        except ImportError:
            raise ImportError(
                "Invariant Kernel (Rust) not found. "
                "Install: cd kernel && maturin develop --release"
            )
        
        self._persist()
        return new_edges

    def evolve(self) -> int:
        """
        Run logical inference on the knowledge graph.
        
        Derives new edges based on transitivity rules.
        Returns the number of new edges created.
        """
        if not hasattr(self.tank, 'edges'): return 0

        try:
            reactor = Reactor(self.tank, strict_lambda=True)
            
            start_edges = len(self.tank.edges)
            reactor.cycle_lambda()
            end_edges = len(self.tank.edges)
            self._persist()
            return end_edges - start_edges
        except Exception as e:
            logger.warning(f"Reactor evolution failed: {e}")
            return 0

    def forget(self, source: str) -> int:
        """
        Antimatter Annihilation — Remove all data for a source.
        """
        ids = self.block_store.get_ids_by_source(source)
        count = self.block_store.delete_by_source(source)
        for bid in ids:
            if bid in self.vector_store.vectors:
                del self.vector_store.vectors[bid]
        
        self._persist()
        return count

    def _persist(self):
        tank_path = self.data_dir / "knowledge.tank"
        if hasattr(self.tank, 'save_to_file'):
            self.tank.save_to_file(tank_path)
        self.vector_store.save()
