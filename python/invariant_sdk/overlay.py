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
    
    ring values:
      'sigma'  - Observation from document (default, σ-proof capable)
      'lambda' - Ghost edge from Halo (navigation only)
      'eta'    - LLM hypothesis (unverified)
    
    Provenance (Anchor Integrity Protocol):
      'doc'      - Source document path (pointer to reality)
      'line'     - Line number (1-indexed, approximate coordinate)
      'ctx_hash' - Semantic checksum of anchor window (8 hex chars)
                   Hash of normalized anchor ±2 words for drift detection.
                   
    Self-Healing States (see INVARIANTS.md):
      - σ-fresh: ctx_hash matches current file content
      - σ-relocated: ctx_hash found at different line (coordinate updated)
      - σ-broken: ctx_hash not found (source changed, fact unverifiable)
    """
    tgt: str  # target hash8
    weight: float
    doc: Optional[str] = None  # source document (provenance)
    ring: str = "sigma"  # sigma/lambda/eta
    line: Optional[int] = None  # line number (1-indexed)
    ctx_hash: Optional[str] = None  # semantic checksum for drift detection
    
    def to_dict(self) -> Dict:
        d = {
            "hash8": self.tgt, 
            "weight": self.weight, 
            "doc": self.doc,
            "ring": self.ring,
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
    
    # src_hash -> list of edges
    edges: Dict[str, List[OverlayEdge]] = field(default_factory=lambda: defaultdict(list))
    
    # Edges to suppress from global crystal: (src, tgt) pairs
    suppressed: Set[Tuple[str, str]] = field(default_factory=set)
    
    # Custom labels: hash8 -> label
    labels: Dict[str, str] = field(default_factory=dict)
    
    # Source files that contributed to this overlay
    sources: Set[str] = field(default_factory=set)
    
    # Conflicts: [(edge1, edge2), ...] where both claim same src->tgt with different values
    conflicts: List[Tuple[OverlayEdge, OverlayEdge]] = field(default_factory=list)
    
    @classmethod
    def load(cls, path: Path) -> "OverlayGraph":
        """Load overlay from .jsonl file."""
        graph = cls()
        path = Path(path)
        
        if not path.exists():
            return graph
        
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
            line = entry.get("line")  # line number
            ctx_hash = entry.get("ctx_hash")  # semantic checksum for integrity
            
            if src and tgt:
                new_edge = OverlayEdge(
                    tgt=tgt, weight=weight, doc=doc, ring=ring,
                    line=line, ctx_hash=ctx_hash
                )
                # Check for conflicts (same src->tgt with different docs/weights)
                existing = [e for e in self.edges[src] if e.tgt == tgt]
                for e in existing:
                    if e.doc != doc or abs(e.weight - weight) > 0.01:
                        self.conflicts.append((e, new_edge))
                self.edges[src].append(new_edge)
        
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
        for src, edge_list in other.edges.items():
            self.edges[src].extend(edge_list)
        
        self.suppressed.update(other.suppressed)
        self.labels.update(other.labels)
        self.sources.update(other.sources)
    
    def save(self, path: Path) -> None:
        """Save overlay to .jsonl file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            # Write edges
            for src, edge_list in self.edges.items():
                for edge in edge_list:
                    entry = {
                        "op": "add", 
                        "src": src, 
                        "tgt": edge.tgt, 
                        "w": edge.weight,
                        "ring": edge.ring,
                    }
                    if edge.doc:
                        entry["doc"] = edge.doc
                    if edge.line is not None:
                        entry["line"] = edge.line
                    if edge.ctx_hash:
                        entry["ctx_hash"] = edge.ctx_hash
                    f.write(json.dumps(entry) + "\n")
            
            # Write suppressions
            for src, tgt in self.suppressed:
                f.write(json.dumps({"op": "sub", "src": src, "tgt": tgt}) + "\n")
            
            # Write labels
            for node, label in self.labels.items():
                f.write(json.dumps({"op": "def", "node": node, "label": label}) + "\n")
    
    def add_edge(
        self, 
        src: str, 
        tgt: str, 
        weight: float = 1.0, 
        doc: Optional[str] = None,
        ring: str = "sigma",
        line: Optional[int] = None,
        ctx_hash: Optional[str] = None,
    ) -> None:
        """
        Add a local edge with optional provenance (Anchor Integrity Protocol).
        
        Args:
            src: Source hash8
            tgt: Target hash8
            weight: Edge weight (typically 1.0 for facts)
            doc: Source document path (provenance for σ-proof)
            ring: 'sigma' (default), 'lambda', or 'eta'
            line: Line number (1-indexed) — approximate coordinate
            ctx_hash: Semantic checksum of anchor window (8 hex chars)
                      Used for drift detection and self-healing.
        """
        new_edge = OverlayEdge(
            tgt=tgt, weight=weight, doc=doc, ring=ring,
            line=line, ctx_hash=ctx_hash
        )
        # Check for conflicts
        existing = [e for e in self.edges[src] if e.tgt == tgt]
        for e in existing:
            if e.doc != doc or abs(e.weight - weight) > 0.01:
                self.conflicts.append((e, new_edge))
        self.edges[src].append(new_edge)
    
    def suppress_edge(self, src: str, tgt: str) -> None:
        """Suppress a global edge (hide from results)."""
        self.suppressed.add((src, tgt))
    
    def define_label(self, node: str, label: str) -> None:
        """Define custom label for a hash8."""
        self.labels[node] = label
    
    def get_neighbors(self, src: str, ring_filter: Optional[str] = None) -> List[Dict]:
        """
        Get local neighbors for a source node.
        
        Args:
            src: Source hash8
            ring_filter: If set, only return edges with this ring ('sigma', 'lambda', 'eta')
        """
        edges = self.edges.get(src, [])
        if ring_filter:
            edges = [e for e in edges if e.ring == ring_filter]
        return [e.to_dict() for e in edges]
    
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
