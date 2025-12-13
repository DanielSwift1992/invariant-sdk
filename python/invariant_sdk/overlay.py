"""
overlay.py — Local Knowledge Overlay (σ-facts)

In-memory graph from .overlay.jsonl files that layers on top of global crystal.
Implements Separation Law (Invariant V): Crystal (α) vs Overlay (σ).

File Format (.overlay.jsonl):
  {"op": "add", "src": "hash8", "tgt": "hash8", "w": 1.0, "doc": "file.txt"}
  {"op": "sub", "src": "hash8", "tgt": "hash8", "reason": "wrong_context"}
  {"op": "def", "node": "hash8", "label": "MyTerm", "type": "anchor"}
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Iterator


@dataclass
class OverlayEdge:
    """Single edge in overlay."""
    tgt: str  # target hash8
    weight: float
    doc: Optional[str] = None  # source document
    
    def to_dict(self) -> Dict:
        return {"hash8": self.tgt, "weight": self.weight, "doc": self.doc}


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
            
            if src and tgt:
                self.edges[src].append(OverlayEdge(tgt=tgt, weight=weight, doc=doc))
        
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
                    entry = {"op": "add", "src": src, "tgt": edge.tgt, "w": edge.weight}
                    if edge.doc:
                        entry["doc"] = edge.doc
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
        doc: Optional[str] = None
    ) -> None:
        """Add a local edge (σ-fact)."""
        self.edges[src].append(OverlayEdge(tgt=tgt, weight=weight, doc=doc))
    
    def suppress_edge(self, src: str, tgt: str) -> None:
        """Suppress a global edge (hide from results)."""
        self.suppressed.add((src, tgt))
    
    def define_label(self, node: str, label: str) -> None:
        """Define custom label for a hash8."""
        self.labels[node] = label
    
    def get_neighbors(self, src: str) -> List[Dict]:
        """Get local neighbors for a source node."""
        return [e.to_dict() for e in self.edges.get(src, [])]
    
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
    
    def __repr__(self) -> str:
        return f"OverlayGraph(edges={self.n_edges}, nodes={self.n_nodes}, suppressed={len(self.suppressed)})"


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
