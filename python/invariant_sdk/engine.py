"""
sdk/engine.py — The Python Implementation of InvariantEngine.
Acts as a bridge between the clean API and the underlying logic components.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ============================================================================
# IMPORTS
# ============================================================================

from .core.reactor import Tank, Reactor, Truth, get_token_hash_hex
from .storage import BlockStore, VectorStore, get_embedder, cosine_similarity
from .types import Block, SearchMode, RefinerStrategy, Relation
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
        
    def observe(self, source: str, content: str) -> int:
        """
        Input Matter. 
        Splits text, hashes it, stores vectors, builds IMP chain.
        """
        # 1. Split (reuse logic or simple split)
        # Simplified block splitter for SDK clarity
        raw_blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
        
        count = 0
        prev_id = None
        
        for i, text in enumerate(raw_blocks):
            # Create ID
            block_id = f"{source}:B{i}"
            
            # Store Physical (SQL)
            self.block_store.save(block_id, text, text, source, i)
            
            # Store Wave (Vector)
            vec = self.embedder.encode(text)
            self.vector_store.add(block_id, vec)
            
            # Store Topology (Tank)
            # EQUALS: Block identity (content → hash)
            if hasattr(self.tank, 'absorb'):
                self.tank.absorb(block_id, text[:50], Relation.EQUALS.value, 1.0, Truth.SIGMA, f"obs:{source}")
            
                # IMP: Time (Sequence)
                if prev_id:
                    self.tank.absorb(prev_id, block_id, Relation.IMP.value, 1.0, Truth.SIGMA, f"seq:{source}")
            
            prev_id = block_id
            count += 1
            
        self._persist()
        return count

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

    def crystallize(self, strategy: RefinerStrategy = RefinerStrategy.KEYWORD, 
                    method: str = "threshold", param: float = 0.75, top_k: int = 50) -> int:
        """
        Phase Transition (Auto-linking).
        Methods:
        - "threshold": Fixed radius (param = 0.75). O(N^2). Precise.
        - "mdl": Adaptive density (param = sensitivity). O(N^2). Context-aware.
        - "hnsw": Small World Index (param = threshold). O(N log N). Scalable (1M+).
        
        Uses Rust Core.
        """
        blocks = self.block_store.get_all()
        if not blocks: return 0
        
        new_edges = 0
        
        # Try Rust Acceleration
        try:
            import invariant_kernel
            
            # Prepare vectors (aligned with blocks list)
            vectors = []
            valid_indices = []
            
            for i, b in enumerate(blocks):
                v = self.vector_store.get(b['id'])
                if v:
                    vectors.append(v)
                    valid_indices.append(i)
            
            if not vectors: return 0

            # Run Rust (Method Selection)
            # print(f"[CRYSTALLIZE] Running Rust Core ({method})...")
            
            if method == "hnsw":
                # HNSW: O(N log N) - for large datasets
                matches = invariant_kernel.crystallize_hnsw(vectors, param, top_k)
            else:
                # Threshold (brute-force): O(N²) - for small datasets
                matches = invariant_kernel.crystallize_all(vectors, param)
            
            for i_local, j_local, sim in matches:
                # Map back to original blocks
                idx1 = valid_indices[i_local]
                idx2 = valid_indices[j_local]
                b1 = blocks[idx1]
                b2 = blocks[idx2]
                
                # OMEGA: Pending classification (crystallize creates candidates)
                # Agent layer determines final edge type
                rel = Relation.OMEGA.value
                
                if hasattr(self.tank, 'absorb'):
                    self.tank.absorb(b1['id'], b2['id'], rel, sim, Truth.ETA, "crystal:rust")
                new_edges += 1
                
        except ImportError:
            # Enforce Rust Core
            raise ImportError(
                "Invariant Kernel (Rust) not found. "
                "Please compile the kernel: 'maturin develop --release'"
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
