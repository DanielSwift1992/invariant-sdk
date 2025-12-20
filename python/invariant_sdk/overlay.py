"""
overlay.py — Local Knowledge Overlay (σ-facts)

In-memory graph from .overlay.jsonl files that layers on top of global crystal.
Implements Separation Law (Invariant V): Crystal (α) vs Overlay (σ).

Ring Hierarchy (INVARIANTS.md):
  α (alpha) - Global crystal axioms (read-only)
  σ (sigma) - Local observations with document provenance (σ-proof)
  λ (lambda) - Ghost edges from Halo (navigation, not proof)
  η (eta)   - LLM hypothesis (requires σ-verification)

File Format (.overlay.jsonl):
  {"op": "add", "src": "hash8", "tgt": "hash8", "w": 1.0, "doc": "file.txt", "ring": "sigma"}
  {"op": "sub", "src": "hash8", "tgt": "hash8", "reason": "wrong_context"}
  {"op": "def", "node": "hash8", "label": "MyTerm", "type": "anchor"}
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Iterator


# Ring priority (higher number = higher priority)
RING_PRIORITY = {"eta": 0, "lambda": 1, "sigma": 2, "alpha": 3}


@dataclass
class OverlayEdge:
    """
    Single edge in overlay with ring classification and provenance.
    
    MYCELIUM v2.3 Compliant.
    
    ring values:
      'sigma'  - Observation from document (default, σ-proof capable)
      'lambda' - Ghost edge from Halo (navigation only)
      'eta'    - LLM hypothesis (unverified)
    
    Witness Bitmask (Physical Form):
      0x01 ADJACENT  - Consecutive tokens in window
      0x02 BRACKET   - A (B) pattern
      0x04 EQUALS    - A = B or A: B pattern
      0x08 GLOSSARY  - A, aka B pattern
    
    Anchor State (§1.4):
      0 COHERENT    - ctx_hash matches at stored line
      1 RELOCATED   - ctx_hash found in scan radius (±50)
      2 DECOHERENT  - ctx_hash not found → fact invalid
    
    Live State (§1.5):
      0 ACTIVE      - Fact active in Reactor
      1 DEPLETED    - Fact superseded (logical tombstone)
    """
    tgt: str  # target hash8
    weight: float
    doc: Optional[str] = None  # source document (provenance)
    ring: str = "sigma"  # sigma/lambda/eta
    phase: str = "solid"  # solid/gas (target word phase)
    line: Optional[int] = None  # line number (1-indexed)
    ctx_hash: Optional[str] = None  # semantic checksum for drift detection
    witness: int = 0  # structural bitmask (ADJACENT|BRACKET|EQUALS|GLOSSARY)
    anchor_state: int = 0  # 0=COHERENT, 1=RELOCATED, 2=DECOHERENT
    live_state: int = 0  # 0=ACTIVE, 1=DEPLETED
    
    # Witness bitmask constants
    ADJACENT = 0x01
    BRACKET = 0x02
    EQUALS = 0x04
    GLOSSARY = 0x08
    
    # Anchor state constants
    COHERENT = 0
    RELOCATED = 1
    DECOHERENT = 2
    
    # Live state constants  
    ACTIVE = 0
    DEPLETED = 1
    
    def to_dict(self) -> Dict:
        d = {
            "hash8": self.tgt, 
            "weight": self.weight, 
            "doc": self.doc,
            "ring": self.ring,
            "phase": self.phase,
            "witness": self.witness,
            "anchor_state": self.anchor_state,
            "live_state": self.live_state,
        }
        if self.line is not None:
            d["line"] = self.line
        if self.ctx_hash is not None:
            d["ctx_hash"] = self.ctx_hash
        return d
    
    def has_provenance(self) -> bool:
        """True if edge has document provenance (σ-proof capable)."""
        return self.ring == "sigma" and self.doc is not None
    
    def has_integrity(self) -> bool:
        """True if edge can be verified via ctx_hash (self-healing capable)."""
        return self.ctx_hash is not None and self.line is not None
    
    def is_provable(self) -> bool:
        """
        True if edge can participate in σ-proof (MYCELIUM v2.3 §1.5).
        
        Requires:
          - anchor_state != DECOHERENT (source verifiable)
          - live_state == ACTIVE (not tombstoned)
          - has provenance (sigma ring + doc)
        """
        return (
            self.anchor_state != self.DECOHERENT
            and self.live_state == self.ACTIVE
            and self.has_provenance()
        )


@dataclass
class OverlayGraph:
    """
    In-memory graph from .overlay.jsonl files.
    
    Stores local facts (σ-observations) that layer on top of global crystal.
    
    Operations:
      - add: Add local edge
      - sub: Suppress global edge (hide it from results)
      - def: Define custom label for a hash8
    """
    
    # src_hash -> list of edges (forward direction)
    edges: Dict[str, List[OverlayEdge]] = field(default_factory=lambda: defaultdict(list))
    
    # tgt_hash -> list of (src, edge) pairs (reverse direction for bidirectional lookup)
    reverse_edges: Dict[str, List[Tuple[str, OverlayEdge]]] = field(default_factory=lambda: defaultdict(list))
    
    # Edges to suppress from global crystal: (src, tgt) pairs
    suppressed: Set[Tuple[str, str]] = field(default_factory=set)
    
    # Custom labels: hash8 -> label
    labels: Dict[str, str] = field(default_factory=dict)
    
    # Source files that contributed to this overlay
    sources: Set[str] = field(default_factory=set)
    
    # Conflicts: [(edge1, edge2), ...] where both claim same src->tgt with different values
    conflicts: List[Tuple[OverlayEdge, OverlayEdge]] = field(default_factory=list)
    
    # Doc to source nodes mapping for fast deletion (Optimization V.3.1)
    doc_to_nodes: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    
    # Private cache for provenance_map (cleared on mutations)
    _provenance_cache: Optional[Dict[str, str]] = field(default=None, repr=False)
    
    # Format version for compatibility (v2.3 = witness field added)
    format_version: str = field(default="2.3")
    
    @property
    def provenance_map(self) -> Dict[str, str]:
        """
        O(1) lookup: hash8 → doc (Optimization V.3.2).
        
        Cached property. Rebuilds only when overlay mutates.
        Used by physics.expand_query for LOCAL OVERLAY marking.
        """
        if self._provenance_cache is None:
            cache: Dict[str, str] = {}
            for src, edge_list in self.edges.items():
                for edge in edge_list:
                    if edge.doc:
                        cache[src] = edge.doc
                        cache[edge.tgt] = edge.doc
            self._provenance_cache = cache
        return self._provenance_cache
    
    @classmethod
    def load(cls, path: Path) -> "OverlayGraph":
        """Load overlay from .pkl (binary, fast) or .jsonl (text, slow).
        
        Priority: .pkl if exists, else .jsonl.
        Binary format is 10x faster for large overlays (142 MB → instant).
        """
        import pickle
        
        graph = cls()
        path = Path(path)
        
        if not path.exists():
            return graph
        
        # Try binary format first (10x faster)
        pkl_path = path.with_suffix('.pkl')
        if pkl_path.exists():
            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
                loaded_edges = data.get('edges', {})
                # Wrap in defaultdict to preserve add_edge() functionality
                graph.edges = defaultdict(list, loaded_edges)
                graph.suppressed = data.get('suppressed', graph.suppressed)
                graph.labels = data.get('labels', graph.labels)
                
                # Rebuild reverse_edges for bidirectional lookup (backward compat)
                loaded_reverse = data.get('reverse_edges', {})
                if loaded_reverse:
                    graph.reverse_edges = defaultdict(list, loaded_reverse)
                else:
                    # Rebuild from edges if not in pickle
                    for src, edge_list in graph.edges.items():
                        for edge in edge_list:
                            graph.reverse_edges[edge.tgt].append((src, edge))
                
                # Load doc_to_nodes index (O(1) deletion) or rebuild
                loaded_doc_index = data.get('doc_to_nodes', {})
                if loaded_doc_index:
                    graph.doc_to_nodes = defaultdict(set, {k: set(v) for k, v in loaded_doc_index.items()})
                else:
                    # Rebuild from edges if not in pickle (backward compat)
                    for src, edge_list in graph.edges.items():
                        for edge in edge_list:
                            if edge.doc:
                                graph.doc_to_nodes[edge.doc].add(src)
                
                graph.sources.add(str(pkl_path))
                return graph
            except Exception:
                pass  # Fall back to JSONL
        
        # Fall back to JSONL parsing (slow for large files)
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                try:
                    entry = json.loads(line)
                    graph._apply_entry(entry)
                except json.JSONDecodeError:
                    continue
        
        graph.sources.add(str(path))
        return graph
    
    @classmethod
    def load_cascade(cls, paths: List[Path]) -> "OverlayGraph":
        """
        Load multiple overlays in order (later overrides earlier).
        
        Typical order:
          1. ~/.invariant/global.overlay.jsonl
          2. ./.invariant/project.overlay.jsonl
        """
        graph = cls()
        for path in paths:
            if Path(path).exists():
                partial = cls.load(path)
                graph.merge(partial)
        return graph
    
    def _apply_entry(self, entry: Dict) -> None:
        """Apply a single JSON entry."""
        op = entry.get("op", "add")
        
        if op == "add":
            src = entry.get("src", "")
            tgt = entry.get("tgt", "")
            weight = float(entry.get("w", 1.0))
            doc = entry.get("doc")
            ring = entry.get("ring", "sigma")  # default to sigma for backward compat
            phase = entry.get("phase", "solid")  # default to solid for backward compat
            line = entry.get("line")  # line number
            ctx_hash = entry.get("ctx_hash")  # semantic checksum for integrity
            
            if src and tgt:
                new_edge = OverlayEdge(
                    tgt=tgt, weight=weight, doc=doc, ring=ring,
                    phase=phase, line=line, ctx_hash=ctx_hash,
                    witness=int(entry.get("witness", 0)),
                    anchor_state=int(entry.get("anchor_state", 0)),
                    live_state=int(entry.get("live_state", 0)),
                )
                # O(1) append — conflict detection is lazy (via get_conflicts)
                # This avoids O(N²) on JSONL load (Supercharged fix)
                self.edges[src].append(new_edge)
                # Add reverse index for bidirectional lookup
                self.reverse_edges[tgt].append((src, new_edge))
                # Add doc index for O(1) deletion
                if doc:
                    self.doc_to_nodes[doc].add(src)
        
        elif op == "sub":
            src = entry.get("src", "")
            tgt = entry.get("tgt", "")
            if src and tgt:
                self.suppressed.add((src, tgt))
        
        elif op == "def":
            node = entry.get("node", "")
            label = entry.get("label", "")
            if node and label:
                self.labels[node] = label
    
    def merge(self, other: "OverlayGraph") -> None:
        """Merge another overlay into this one (other takes priority)."""
        # Merge edges + detect σ-conflicts (INVARIANTS.md line 126)
        # Only σ-edges can conflict — λ-edges are navigation, not facts
        for src, edge_list in other.edges.items():
            existing = self.edges.get(src, [])
            for new_edge in edge_list:
                if new_edge.ring == "sigma":
                    for e in existing:
                        if e.tgt != new_edge.tgt or e.ring != "sigma":
                            continue
                        if e.doc != new_edge.doc:  # Different source = conflict
                            self.conflicts.append((e, new_edge))
            self.edges[src].extend(edge_list)
        
        self.suppressed.update(other.suppressed)
        self.labels.update(other.labels)
        self.sources.update(other.sources)
        self.conflicts.extend(other.conflicts)
    
    def save(self, path: Path) -> None:
        """Save overlay to .jsonl file. Optimized with buffered writes."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build all lines in memory first (faster than many small writes)
        lines = []
        
        # Edges
        for src, edge_list in self.edges.items():
            for edge in edge_list:
                entry = {
                    "op": "add", 
                    "src": src, 
                    "tgt": edge.tgt, 
                    "w": edge.weight,
                    "ring": edge.ring,
                    "phase": edge.phase,
                }
                if edge.doc:
                    entry["doc"] = edge.doc
                if edge.line is not None:
                    entry["line"] = edge.line
                if edge.ctx_hash:
                    entry["ctx_hash"] = edge.ctx_hash
                # Persist physical state fields (v1.7.2)
                if edge.witness:
                    entry["witness"] = edge.witness
                if edge.anchor_state:
                    entry["anchor_state"] = edge.anchor_state
                if edge.live_state:
                    entry["live_state"] = edge.live_state
                lines.append(json.dumps(entry))
        
        # Suppressions
        for src, tgt in self.suppressed:
            lines.append(json.dumps({"op": "sub", "src": src, "tgt": tgt}))
        
        # Labels
        for node, label in self.labels.items():
            lines.append(json.dumps({"op": "def", "node": node, "label": label}))
        
        # Single JSONL write (human readable)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
            if lines:
                f.write('\n')
        
        # Also save pickle for fast loading (10x faster)
        import pickle
        pkl_path = path.with_suffix('.pkl')
        with open(pkl_path, 'wb') as f:
            pickle.dump({
                'edges': dict(self.edges),  # Convert defaultdict to dict
                'suppressed': self.suppressed,
                'labels': self.labels,
                'doc_to_nodes': dict(self.doc_to_nodes),  # O(1) doc deletion index
            }, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    def add_edge(
        self, 
        src: str, 
        tgt: str, 
        weight: float = 1.0, 
        doc: Optional[str] = None,
        ring: str = "sigma",
        phase: str = "solid",
        line: Optional[int] = None,
        ctx_hash: Optional[str] = None,
        witness: int = 0,
        anchor_state: int = 0,
        live_state: int = 0,
    ) -> None:
        """
        Add a local edge with optional provenance (MYCELIUM v2.3).
        
        Args:
            src: Source hash8
            tgt: Target hash8
            weight: Edge weight (typically 1.0 for facts)
            doc: Source document path (provenance for σ-proof)
            ring: 'sigma' (default), 'lambda', or 'eta'
            phase: 'solid' (anchor) or 'gas' (LINK word)
            line: Line number (1-indexed)
            ctx_hash: Semantic checksum of anchor window (8 hex chars)
            witness: Structural bitmask (ADJACENT|BRACKET|EQUALS|GLOSSARY)
            anchor_state: 0=COHERENT, 1=RELOCATED, 2=DECOHERENT
            live_state: 0=ACTIVE, 1=DEPLETED
        
        Performance: O(1) append. Conflict detection moved to lazy check.
        """
        new_edge = OverlayEdge(
            tgt=tgt, weight=weight, doc=doc, ring=ring,
            phase=phase, line=line, ctx_hash=ctx_hash,
            witness=witness, anchor_state=anchor_state, live_state=live_state,
        )
        # O(1) append - conflict detection is now lazy (check on demand)
        self.edges[src].append(new_edge)
        # Add reverse index for bidirectional lookup (for incoming edges)
        self.reverse_edges[tgt].append((src, new_edge))
        # O(1) doc index update for fast deletion
        if doc:
            self.doc_to_nodes[doc].add(src)
            # Invalidate provenance_cache (V.3.2)
            self._provenance_cache = None
    
    def suppress_edge(self, src: str, tgt: str) -> None:
        """Suppress a global edge (hide from results)."""
        self.suppressed.add((src, tgt))
    
    def define_label(self, node: str, label: str) -> None:
        """Define custom label for a hash8."""
        self.labels[node] = label
    
    def delete_doc(self, doc: str) -> int:
        """Delete all edges belonging to a document.
        
        Args:
            doc: Document name/path to delete
            
        Returns:
            Number of edges deleted
        
        Theory: Conservation Law - explicit deletion only (no silent evaporation).
        Performance: O(NodesInDoc) using doc_to_nodes index.
        """
        if doc not in self.doc_to_nodes:
            return 0
            
        deleted = 0
        nodes = list(self.doc_to_nodes[doc])
        for src in nodes:
            original_len = len(self.edges[src])
            self.edges[src] = [e for e in self.edges[src] if e.doc != doc]
            deleted += original_len - len(self.edges[src])
            # Clean up empty source nodes
            if not self.edges[src]:
                del self.edges[src]
        
        del self.doc_to_nodes[doc]
        # Invalidate provenance_cache (V.3.2)
        self._provenance_cache = None
        return deleted
    
    def get_neighbors(self, node: str, ring_filter: Optional[str] = None, bidirectional: bool = True) -> List[Dict]:
        """
        Get local neighbors for a node (bidirectional by default).
        
        Args:
            node: Hash8 to find neighbors for
            ring_filter: If set, only return edges with this ring ('sigma', 'lambda', 'eta')
            bidirectional: If True, return both outgoing AND incoming edges
        
        Returns:
            List of neighbor dicts with 'tgt' (or 'src' for reverse), weight, doc, etc.
        """
        result = []
        
        # Forward edges: node -> neighbor
        edges = self.edges.get(node, [])
        if ring_filter:
            edges = [e for e in edges if e.ring == ring_filter]
        result.extend([e.to_dict() for e in edges])
        
        # Reverse edges: other -> node (bidirectional)
        if bidirectional:
            for src, edge in self.reverse_edges.get(node, []):
                if ring_filter and edge.ring != ring_filter:
                    continue
                d = edge.to_dict()
                d["tgt"] = src  # The "neighbor" is the source of this incoming edge
                d["reverse"] = True  # Mark as reverse direction
                result.append(d)
        
        return result
    
    def get_label(self, node: str) -> Optional[str]:
        """Get custom label for a node, if defined."""
        return self.labels.get(node)
    
    def is_suppressed(self, src: str, tgt: str) -> bool:
        """Check if edge should be hidden from results."""
        return (src, tgt) in self.suppressed
    
    def all_sources(self) -> Iterator[str]:
        """Iterate over all source nodes that have local edges."""
        return iter(self.edges.keys())
    
    @property
    def n_edges(self) -> int:
        """Total number of local edges."""
        return sum(len(edges) for edges in self.edges.values())
    
    @property
    def n_nodes(self) -> int:
        """Number of unique nodes (sources + targets)."""
        nodes = set(self.edges.keys())
        for edge_list in self.edges.values():
            nodes.update(e.tgt for e in edge_list)
        return len(nodes)
    
    def has_sigma_path(self, src: str, tgt: str) -> Tuple[bool, List[OverlayEdge]]:
        """
        Check if there's a σ-proof path from src to tgt.
        
        σ-proof requires:
          1. Path exists in σ-ring edges
          2. At least one edge has document provenance
        
        Returns:
            (proven: bool, path: List[OverlayEdge])
        """
        # Direct edge check (most common case)
        for edge in self.edges.get(src, []):
            if edge.tgt == tgt and edge.ring == "sigma":
                return (edge.has_provenance(), [edge])
        
        # BFS for 2-hop path (A → B → C)
        visited = {src}
        queue = [(src, [])]
        
        while queue:
            current, path = queue.pop(0)
            
            for edge in self.edges.get(current, []):
                if edge.ring != "sigma":
                    continue
                    
                if edge.tgt == tgt:
                    full_path = path + [edge]
                    has_provenance = any(e.has_provenance() for e in full_path)
                    return (has_provenance, full_path)
                
                if edge.tgt not in visited and len(path) < 2:  # max 2 hops
                    visited.add(edge.tgt)
                    queue.append((edge.tgt, path + [edge]))
        
        return (False, [])
    
    def has_path(self, src: str, tgt: str, max_hops: int = 3) -> Tuple[bool, List[OverlayEdge], str]:
        """
        Check if there's ANY path from src to tgt (σ or λ edges).
        
        This allows traversal through gas words (λ-edges).
        
        Returns:
            (found: bool, path: List[OverlayEdge], ring: str)
            ring is 'sigma' if ALL edges are σ, else 'lambda'
        """
        # Direct edge check (most common case)
        for edge in self.edges.get(src, []):
            if edge.tgt == tgt:
                return (True, [edge], edge.ring)
        
        # BFS for multi-hop path
        visited = {src}
        queue = [(src, [])]
        
        while queue:
            current, path = queue.pop(0)
            
            for edge in self.edges.get(current, []):
                new_path = path + [edge]
                
                if edge.tgt == tgt:
                    # Determine ring: sigma only if ALL edges are sigma
                    ring = "sigma" if all(e.ring == "sigma" for e in new_path) else "lambda"
                    return (True, new_path, ring)
                
                if edge.tgt not in visited and len(path) < max_hops:
                    visited.add(edge.tgt)
                    queue.append((edge.tgt, new_path))
        
        return (False, [], "")
    
    def get_conflicts(self) -> List[Tuple[OverlayEdge, OverlayEdge]]:
        """Get all detected conflicts (same edge, different values/sources)."""
        return self.conflicts
    
    def get_sigma_edges(self) -> Iterator[Tuple[str, OverlayEdge]]:
        """Iterate over all σ-ring edges with their sources."""
        for src, edge_list in self.edges.items():
            for edge in edge_list:
                if edge.ring == "sigma":
                    yield (src, edge)
    
    def __repr__(self) -> str:
        n_sigma = sum(1 for _ in self.get_sigma_edges())
        return f"OverlayGraph(edges={self.n_edges}, σ={n_sigma}, conflicts={len(self.conflicts)})"


def find_overlays(start_dir: Optional[Path] = None) -> List[Path]:
    """
    Find overlay files in standard locations.
    
    Search order (later overrides earlier):
      1. ~/.invariant/global.overlay.jsonl
      2. ./.invariant/overlay.jsonl (walk up to find)
    """
    paths = []
    
    # User global
    global_path = Path.home() / ".invariant" / "global.overlay.jsonl"
    if global_path.exists():
        paths.append(global_path)
    
    # Project local (walk up directory tree)
    if start_dir is None:
        start_dir = Path.cwd()
    
    current = Path(start_dir).resolve()
    while current != current.parent:
        local_path = current / ".invariant" / "overlay.jsonl"
        if local_path.exists():
            paths.append(local_path)
            break
        current = current.parent
    
    return paths
