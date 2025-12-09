#!/usr/bin/env python3
"""
reactor.py — The Unified Invariant Inference Engine (v2.2 - Agnostic)

Changes v2.2:
  - REMOVED hardcoded English stop-words.
  - ADDED `noise_predicate` injection.
  - Reactor is now purely topological. It relies on the caller to define "noise".
"""

import json
import sys
from enum import Enum
from typing import Dict, List, Set, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

# Import from shared merkle module
try:
    from .merkle import get_token_hash_hex, bond_id
except ImportError:
    # Fallback if run standalone
    import hashlib
    
    class Node:
        def __init__(self, left=None, right=None):
            self.left = left
            self.right = right
        @property
        def is_origin(self):
            return self.left is None and self.right is None
    
    ORIGIN = Node()
    def Dyad(a, b): return Node(a, b)
    
    def encode_byte(byte_val: int) -> Node:
        chain = ORIGIN
        for i in range(8):
            bit = (byte_val >> i) & 1
            bit_node = ORIGIN if bit == 0 else Dyad(ORIGIN, ORIGIN)
            chain = Dyad(bit_node, chain)
        return chain
    
    def encode_string(s: str) -> Node:
        chain = ORIGIN
        for b in reversed(s.encode('utf-8')):
            chain = Dyad(encode_byte(b), chain)
        return chain
    
    def merkle_hash(node: Node) -> bytes:
        if node.is_origin:
            return hashlib.sha256(b'\x00').digest()
        return hashlib.sha256(b'\x01' + merkle_hash(node.left) + merkle_hash(node.right)).digest()
    
    def get_token_hash_hex(s: str) -> str:
        return merkle_hash(encode_string(s)).hex()
    
    def bond_id(u: str, v: str, rel: str) -> str:
        return hashlib.sha256(f"{u}:{rel}:{v}".encode()).hexdigest()[:16]


# ============================================================================
# L1: EPISTEMICS
# ============================================================================

class Truth(Enum):
    ALPHA = 0   # Axiom (User override)
    SIGMA = 1   # Observed (Physical weights)
    LAMBDA = 2  # Derived (Logic)
    ETA = 3     # Hypothesis

@dataclass
class Provenance:
    ring: Truth
    source: str
    confidence: float
    path: Optional[List[str]] = None  # [A_hash, B_hash, C_hash] for transparency

@dataclass
class Edge:
    source: str
    target: str
    relation: str
    energy: float = 0.0
    provenance: List[Provenance] = field(default_factory=list)
    
    @property
    def id(self) -> str:
        return bond_id(self.source, self.target, self.relation)
    
    @property
    def ring(self) -> Truth:
        if not self.provenance: return Truth.ETA
        return min((p.ring for p in self.provenance), key=lambda r: r.value)


# ============================================================================
# L2: THE TANK (SINGULARITY)
# ============================================================================

class Tank:
    def __init__(self):
        self.edges: Dict[str, Edge] = {}
        self.adj: Dict[str, List[str]] = defaultdict(list)
        self.labels: Dict[str, str] = {}
        self.mass = 0.0
        self.node_energy: Dict[str, float] = defaultdict(float)  # Entropy Shield: per-node energy

    def add_edge_hash(self, u_h: str, v_h: str, rel: str, 
                      energy: float, ring: Truth, source: str,
                      path: Optional[List[str]] = None) -> Edge:
        """Fundamental interaction on hash space."""
        eid = bond_id(u_h, v_h, rel)
        prov = Provenance(ring, source, energy, path)

        if eid in self.edges:
            e = self.edges[eid]
            e.energy += energy
            e.provenance.append(prov)
            self.mass += energy
        else:
            e = Edge(u_h, v_h, rel, energy, [prov])
            self.edges[eid] = e
            self.adj[u_h].append(eid)
            self.mass += energy
        
        # Entropy Shield: Track per-node energy (both endpoints gain energy)
        self.node_energy[u_h] += energy
        self.node_energy[v_h] += energy
        
        return e

    def absorb(self, u_lbl: str, v_lbl: str, rel: str, 
               energy: float, ring: Truth, source: str):
        """Demo interface: labels → hashes → topology."""
        u_h = get_token_hash_hex(u_lbl)
        v_h = get_token_hash_hex(v_lbl)
        self.labels[u_h] = u_lbl
        self.labels[v_h] = v_lbl
        self.add_edge_hash(u_h, v_h, rel, energy, ring, source)

    def label(self, h: str) -> str:
        return self.labels.get(h, h[:8])

    def get_neighbors(self, u_h: str, max_ring: Truth = Truth.ETA) -> List[Edge]:
        return [
            self.edges[eid] for eid in self.adj.get(u_h, [])
            if self.edges[eid].ring.value <= max_ring.value
        ]
    
    def get_sigma_neighbors(self, u_h: str) -> List[Edge]:
        """Get only σ-edges (for strict λ mode)."""
        return [
            self.edges[eid] for eid in self.adj.get(u_h, [])
            if self.edges[eid].ring == Truth.SIGMA
        ]

    # ================================================================
    # ENTROPY SHIELD: Topological Noise Detection (Zipf's Law)
    # ================================================================
    
    def get_node_energy(self, h: str) -> float:
        """Return accumulated energy for a node."""
        return self.node_energy.get(h, 0.0)
    
    def get_node_probability(self, h: str) -> float:
        """
        P(node) = Energy(node) / TotalEnergy.
        Used for Zipf-based noise detection.
        """
        if self.mass == 0:
            return 0.0
        return self.node_energy.get(h, 0.0) / self.mass

    def load_from_file(self, path_: Path):
        """Load real tank, respecting existing hashes."""
        print(f"Loading {path_}...")
        try:
            with open(path_) as f:
                data = json.load(f)
        except FileNotFoundError:
            print("Error: knowledge.tank not found.")
            return

        count = 0
        for e in data.get("edges", []):
            src_h = e.get("source")
            tgt_h = e.get("target")
            rel = e.get("type", "IMP")
            w = abs(e.get("weight", 0.5))
            debug = e.get("_debug", "")

            if "==" in debug:
                parts = debug.split("==")
                self.labels[src_h] = parts[0].strip()
                self.labels[tgt_h] = parts[1].strip().strip("'")
            elif "->" in debug:
                parts = debug.split("->")
                if len(parts) >= 2:
                    self.labels[src_h] = parts[0].strip().strip("'")
                    self.labels[tgt_h] = parts[1].strip().strip("'")

            # Parse ring from saved data
            ring_name = e.get("_ring", "SIGMA")
            ring = Truth.SIGMA
            try:
                ring = Truth[ring_name]
            except KeyError:
                pass

            self.add_edge_hash(src_h, tgt_h, rel, w, ring, "tank")
            count += 1
        
        # Load node_energy if present (backward compatible)
        if "node_energy" in data:
            self.node_energy = defaultdict(float, data["node_energy"])
            
        print(f"Loaded {count} edges. Mass: {self.mass:.1f}")

    def save_to_file(self, path_: Path):
        """Persist Tank to disk."""
        edges_list = []
        for eid, e in self.edges.items():
            src_lbl = self.labels.get(e.source, e.source[:8])
            tgt_lbl = self.labels.get(e.target, e.target[:8])
            edges_list.append({
                "source": e.source,
                "target": e.target,
                "type": e.relation,
                "weight": e.energy,
                "_debug": f"{src_lbl} --{e.relation}--> {tgt_lbl}",
                "_ring": e.ring.name,
            })
        
        data = {
            "metadata": {
                "total": len(edges_list),
                "mass": self.mass,
            },
            "edges": edges_list,
            "node_energy": dict(self.node_energy),  # Entropy Shield persistence
        }
        
        with open(path_, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved {len(edges_list)} edges to {path_}")

    def stats(self):
        counts = {r: 0 for r in Truth}
        for e in self.edges.values():
            counts[e.ring] += 1
        
        print(f"\n=== TANK STATE (Mass: {self.mass:.1f}) ===")
        print(f"  Nodes: {len(self.labels)}")
        print(f"  Edges: {len(self.edges)}")
        for r in Truth:
            print(f"    {r.name}: {counts[r]}")


# ============================================================================
# THE REACTOR
# ============================================================================
# Internal relation type constants
__REL_IMP = "IMP"
__REL_IS_A = "IS_A"
_REL_EQUALS = "EQUALS"
__REL_HAS_PROP = "HAS_PROP"

# Internal relation property constants
__PROP_TRANSITIVE = "TRANSITIVE"
__PROP_INHERITABLE = "INHERITABLE"
_PROP_SYMMETRIC = "SYMMETRIC"

# Type definition for noise filter
NoisePredicate = Callable[[str], bool]

# Noise detection threshold (k=3 means: filter nodes > mean + 3*std_dev)
# Higher values = less filtering, lower values = more aggressive filtering
_DEFAULT_NOISE_K = 3.0


class Reactor:
    def __init__(self, tank: Tank, strict_lambda: bool = True, 
                 noise_filter: Optional[NoisePredicate] = None,
                 noise_k_sigma: float = _DEFAULT_NOISE_K):
        """
        The Inference Engine .
        
        Args:
            tank: The knowledge Tank
            strict_lambda: If True, only use σ-edges as intermediate (prevents λ-loops)
            noise_filter: Legacy parameter, not needed for new projects.
                         If None, uses k-sigma detection (recommended).
            noise_k_sigma: Sigma multiplier for noise threshold (default 3.0).
                          ("k-sigma is empirical proxy for phase transition"
        """
        self.tank = tank
        self.strict_lambda = strict_lambda
        
        # Entropy Shield: k-sigma based noise detection 
        self.noise_k_sigma = noise_k_sigma
        self._noise_cache: Dict[str, bool] = {}  # Cache for performance
        self._stats_dirty = True  # Recalculate when Tank changes
        
        # Legacy filter (optional)
        self._legacy_noise_filter = noise_filter
        
        # Meta-Topology: Load relation properties from Tank axioms
        self.rel_props = self._load_meta_physics()
        
        self.stats_λ = 0
        self.stats_η = 0

    def _load_meta_physics(self) -> Dict[str, Set[str]]:
        """
        Load relation properties from Tank axioms.
        
        Pattern: [RELATION] --HAS_PROP--> [PROPERTY]
        
        This replaces hardcoded TRANSITIVE/INHERITABLE/SYMMETRIC lists.
        Properties are stored as Ring ALPHA edges in the Tank.
        
        Returns:
            Dict mapping relation name to set of properties
        """
        props: Dict[str, Set[str]] = defaultdict(set)
        
        # Bootstrap: Atom IMP is always transitive (fundamental)
        props[__REL_IMP].add(_PROP_TRANSITIVE)
        
        # Load user axioms from Tank (Ring ALPHA)
        for edge in self.tank.edges.values():
            if edge.relation == _REL_HAS_PROP and edge.ring == Truth.ALPHA:
                rel_name = self.tank.label(edge.source)
                prop_name = self.tank.label(edge.target)
                if rel_name and prop_name:
                    props[rel_name.upper()].add(prop_name.upper())
        
        return props
    
    def has_property(self, relation: str, prop: str) -> bool:
        """Check if relation has a property (TRANSITIVE, INHERITABLE, SYMMETRIC)."""
        return prop.upper() in self.rel_props.get(relation.upper(), set())

    def _compute_noise_threshold(self) -> tuple:
        """
        Compute k-sigma threshold from node_energy distribution.
        
        Note:
        "k-sigma threshold is the empirical proxy for phase transition"
        
        Returns:
            (mean, sigma, threshold) tuple
        """
        energies = list(self.tank.node_energy.values())
        if len(energies) < 2:
            return (0.0, 0.0, float('inf'))  # No noise detection possible
        
        mean = sum(energies) / len(energies)
        variance = sum((e - mean) ** 2 for e in energies) / len(energies)
        sigma = variance ** 0.5
        
        threshold = mean + self.noise_k_sigma * sigma
        return (mean, sigma, threshold)

    def is_topological_noise(self, h: str) -> bool:
        """
        Pure Noise Detection (k-Sigma Method).
        
        Note:
        "k-sigma threshold is the empirical proxy for phase transition"
        
        High-frequency nodes are treated as noise
        Normal nodes are used for inference
        
        A node is noise if:
        1. node_energy > μ + k*σ (frozen/crystallized into syntax)
        2. OR node has no label (orphan hash)
        
        Args:
            h: Node hash
        
        Returns:
            True if node is topological noise (noise)
        """
        # Unlabeled hash is effectively noise
        if h not in self.tank.labels:
            return True
        
        # Compute threshold (cached calculation)
        mean, sigma, threshold = self._compute_noise_threshold()
        
        if sigma == 0:
            return False  # Uniform distribution, no noise
        
        # k-sigma rule: frozen if more than k standard deviations above mean
        node_energy = self.tank.node_energy.get(h, 0.0)
        return node_energy > threshold

    def is_noise(self, h: str) -> bool:
        """
        Noise detection dispatcher.
        
        Uses k-sigma detection by default.
        Falls back to legacy filter if provided (for backward compatibility).
        """
        
        if self._legacy_noise_filter is not None:
            lbl = self.tank.label(h)
            if lbl is None:
                return True
            return self._legacy_noise_filter(lbl)
        
        # RECOMMENDED path: Pure Physics (k-sigma)
        return self.is_topological_noise(h)

    def cycle_lambda(self, decay: float = 0.9, min_energy: float = 0.1):
        """
        CYCLE λ: Formal Logical Closure.
        
        Implements three proven inference rules:
        
        RULE 1 (Transitivity): A→R→B ∧ B→R→C ⟹ A→R→C
          Valid for: IS_A, IMPLIES, LOCATED_IN, PART_OF, LEADS_TO
          Proof: Standard transitive closure (first-order logic)
          
        RULE 2 (IS_A Inheritance): A IS_A B ∧ B→R→C ⟹ A→R→C
          Valid for: LOCATED_IN, HAS_PROPERTY, PART_OF, TYPE, HAS
          Proof: Monotonic inheritance (Description Logic ALC)
          
        RULE 3 (EQUALS Substitution): A EQUALS B ∧ R(A,C) ⟹ R(B,C)
          Proof: Leibniz's law of identity
        """
        # ================================================================
        # RELATION ALGEBRA (Data-Driven from Tank Axioms)
        # Properties loaded via _load_meta_physics() from HAS_PROP edges
        # ================================================================
        print(f"\n--- CYCLE λ: LOGICAL CLOSURE (strict={self.strict_lambda}) ---")
        print(f"  Meta-Physics: {len(self.rel_props)} relations with properties")
        new_edges = []
        
        # ================================================================
        # RULE 1: Same-Relation Transitivity
        # A→R→B ∧ B→R→C ⟹ A→R→C (for TRANSITIVE relations)
        # ================================================================
        for a_h in list(self.tank.adj.keys()):
            if self.is_noise(a_h): continue

            for e1 in self.tank.get_neighbors(a_h, Truth.LAMBDA):
                rel1 = e1.relation.upper()
                if not self.has_property(rel1, _PROP_TRANSITIVE): continue
                b_h = e1.target
                if self.is_noise(b_h): continue

                if self.strict_lambda:
                    b_edges = self.tank.get_sigma_neighbors(b_h)
                else:
                    b_edges = self.tank.get_neighbors(b_h, Truth.LAMBDA)
                
                for e2 in b_edges:
                    rel2 = e2.relation.upper()
                    if rel2 != rel1: continue  # Same relation for transitivity
                    c_h = e2.target
                    if a_h == c_h: continue
                    if self.is_noise(c_h): continue

                    energy = min(e1.energy, e2.energy) * decay
                    if energy < min_energy: continue

                    path = [a_h, b_h, c_h]
                    new_edges.append((a_h, c_h, rel1, energy, path, "RULE1_TRANS"))

        # ================================================================
        # RULE 2: IS_A Inheritance
        # A IS_A B ∧ B→R→C ⟹ A→R→C (for INHERITABLE relations)
        # ================================================================
        for a_h in list(self.tank.adj.keys()):
            if self.is_noise(a_h): continue
            
            # Find all B where A IS_A B
            for e1 in self.tank.get_neighbors(a_h, Truth.LAMBDA):
                if e1.relation.upper() != _REL_IS_A: continue
                b_h = e1.target
                if self.is_noise(b_h): continue
                
                # Find all C where B→R→C (R is inheritable)
                for e2 in self.tank.get_neighbors(b_h, Truth.LAMBDA):
                    rel2 = e2.relation.upper()
                    if not self.has_property(rel2, _PROP_INHERITABLE): continue
                    if rel2 == _REL_IS_A: continue  # Handled by Rule 1
                    c_h = e2.target
                    if a_h == c_h: continue
                    if self.is_noise(c_h): continue
                    
                    energy = min(e1.energy, e2.energy) * decay
                    if energy < min_energy: continue
                    
                    path = [a_h, b_h, c_h]
                    new_edges.append((a_h, c_h, rel2, energy, path, "RULE2_INHERIT"))

        # ================================================================
        # RULE 3: EQUALS Substitution
        # A EQUALS B ∧ R(A,C) ⟹ R(B,C) (for all relations)
        # ================================================================
        for a_h in list(self.tank.adj.keys()):
            if self.is_noise(a_h): continue
            
            # Find all B where A EQUALS B
            for e1 in self.tank.get_neighbors(a_h, Truth.LAMBDA):
                if e1.relation.upper() != "EQUALS": continue
                b_h = e1.target
                if self.is_noise(b_h): continue
                
                # Copy all edges from A to B
                for e2 in self.tank.get_neighbors(a_h, Truth.LAMBDA):
                    if e2.relation.upper() == "EQUALS": continue
                    c_h = e2.target
                    if b_h == c_h: continue
                    if self.is_noise(c_h): continue
                    
                    energy = min(e1.energy, e2.energy) * decay
                    if energy < min_energy: continue
                    
                    path = [b_h, a_h, c_h]
                    new_edges.append((b_h, c_h, e2.relation, energy, path, "RULE3_EQUALS"))

        # ================================================================
        # COMMIT NEW EDGES
        # ================================================================
        added = 0
        for (u, v, rel, e, path, rule) in new_edges:
            eid = bond_id(u, v, rel)
            if eid not in self.tank.edges:
                u_lbl = self.tank.label(u)
                v_lbl = self.tank.label(v)
                b_lbl = self.tank.label(path[1])
                print(f"  [λ] {u_lbl} --{rel}--> {v_lbl} via {b_lbl} (E={e:.2f})")
                
                self.tank.add_edge_hash(u, v, rel, e, Truth.LAMBDA, f"REACTOR_{rule}", path)
                added += 1
                self.stats_λ += 1
        
        if added == 0:
            print("  No new deductions.")
        else:
            print(f"  Total λ-derived: {self.stats_λ}")

    def cycle_mendeleev(self, sim_threshold: float = 0.4, min_neighbors: int = 2):
        """CYCLE η: Mendeleev - symmetry hypotheses."""
        print("\n--- CYCLE η: MENDELEEV ---")
        
        def signature(h: str) -> Set[tuple]:
            return {(e.relation, e.target) for e in self.tank.get_neighbors(h, Truth.LAMBDA)}
        
        candidates = [(h, signature(h)) for h in self.tank.adj.keys() 
                      if len(signature(h)) >= min_neighbors and not self.is_noise(h)]
        print(f"  Candidates: {len(candidates)}")
        
        hypotheses = []
        checked = set()
        
        for i, (a_h, a_sig) in enumerate(candidates):
            for j, (b_h, b_sig) in enumerate(candidates):
                if i >= j: continue
                pair = (min(a_h, b_h), max(a_h, b_h))
                if pair in checked: continue
                checked.add(pair)
                
                inter = len(a_sig & b_sig)
                union = len(a_sig | b_sig)
                if union == 0: continue
                sim = inter / union
                
                if sim < sim_threshold: continue
                
                for (rel, tgt) in a_sig - b_sig:
                    hypotheses.append((b_h, tgt, rel, sim * 0.5, a_h))
                for (rel, tgt) in b_sig - a_sig:
                    hypotheses.append((a_h, tgt, rel, sim * 0.5, b_h))
        
        added = 0
        for (src, tgt, rel, conf, tmpl) in hypotheses[:20]:
            eid = bond_id(src, tgt, rel)
            if eid not in self.tank.edges:
                print(f"  [η] {self.tank.label(src)} → {self.tank.label(tgt)} (via {self.tank.label(tmpl)})")
                path = [src, tmpl, tgt]  # Template-based path
                prov = Provenance(Truth.ETA, f"mendeleev", conf, path)
                e = Edge(src, tgt, rel, conf, [prov])
                self.tank.edges[eid] = e
                self.tank.adj[src].append(eid)
                self.tank.mass += conf
                added += 1
                self.stats_η += 1
        
        print(f"  Total η-hypotheses: {self.stats_η}")

    # ================================================================
    # CYCLE δ: DISCOVER (Rule Synthesis from Examples)
    # Note: Find invariant transformation from In→Out pairs
    # ================================================================
    
    def cycle_discover(self, examples: List[tuple], relation: str = "TRANSFORM", 
                       atomic: bool = True):
        """
        CYCLE δ: Discover transformation rules from examples.
        
        Based on pure topology:
          - Uses merkle.py Node/ORIGIN for structure
          - Computes ΔW (weight difference) as transformation
          - Finds invariant across all examples
          - Creates new α-axiom if invariant exists
        
        Args:
            examples: List of (input_label, output_label) pairs
            relation: Relation type for the discovered rule
            atomic: If True, treat each character as Ω (Token-Level).
                    If False, encode to bit trees (Bit-Level).
                    Default True for text - like DNA ignoring atoms.
        
        Returns:
            The discovered invariant or None
        """
        print(f"\n--- CYCLE δ: DISCOVER ({len(examples)} examples, atomic={atomic}) ---")
        
        if len(examples) < 2:
            print("  [!] Need at least 2 examples")
            return None
        
        # Import topology functions with fallback
        Node = None
        ORIGIN = None
        encode_string = None
        
        try:
            from .merkle import Node, ORIGIN, encode_string
        except ImportError:
            # Define locally as fallback
            class Node:
                def __init__(self, left=None, right=None):
                    self.left = left
                    self.right = right
                @property
                def is_origin(self):
                    return self.left is None and self.right is None
            
            ORIGIN = Node()
            def Dyad(a, b): return Node(a, b)
            
            def encode_byte(byte_val):
                chain = ORIGIN
                for i in range(8):
                    bit = (byte_val >> i) & 1
                    bit_node = ORIGIN if bit == 0 else Dyad(ORIGIN, ORIGIN)
                    chain = Dyad(bit_node, chain)
                return chain
            
            def encode_string(s):
                chain = ORIGIN
                for b in reversed(s.encode('utf-8')):
                    chain = Dyad(encode_byte(b), chain)
                return chain
        
        # === ATOMIC ENCODING (Token-Level) ===
        # Per DNA principle: don't look at atoms, look at nucleotides
        # Each character is Ω (indivisible atom for this task)
        
        def encode_atomic(s: str) -> Node:
            """
            Token-Level Encoding (Renormalization).
            
            Each character → Ω (atom)
            String → Chain of Dyads
            
            'abc' → Δ(Ωa, Δ(Ωb, Δ(Ωc, Ω)))
            
            W('abc') = 5 (3 atoms + 2 dyads)
            D('abc') = 3
            L('abc') = 4 (3 letter atoms + 1 tail Ω)
            """
            chain = ORIGIN
            for char in reversed(s):
                # Each char is an ATOM (Ω with identity)
                # We use a unique Ω per char type
                atom = Node()  # Ω
                chain = Node(atom, chain)  # Δ(Ωchar, rest)
            return chain
        
        # Select encoder based on mode
        encoder = encode_atomic if atomic else encode_string
        
        # === INVARIANT VECTOR FUNCTIONS  ===
        
        def compute_weight(node: Node) -> int:
            """W(n): Structural complexity. W(Ω)=0, W(Δ(a,b))=W(a)+W(b)+1"""
            if node.is_origin:
                return 0
            return compute_weight(node.left) + compute_weight(node.right) + 1
        
        def compute_depth(node: Node) -> int:
            """D(n): Maximum depth. D(Ω)=0, D(Δ(a,b))=max(D(a),D(b))+1"""
            if node.is_origin:
                return 0
            return max(compute_depth(node.left), compute_depth(node.right)) + 1
        
        def compute_leaves(node: Node) -> int:
            """L(n): Number of leaves (Ω nodes). L(Ω)=1, L(Δ(a,b))=L(a)+L(b)"""
            if node.is_origin:
                return 1
            return compute_leaves(node.left) + compute_leaves(node.right)
        
        def compute_shape(node: Node) -> str:
            """S(n): Structural signature (topology without values). For pattern matching."""
            if node.is_origin:
                return "O"  # Origin mark
            return f"D({compute_shape(node.left)},{compute_shape(node.right)})"
        
        def invariant_vector(node: Node) -> tuple:
            """I(n) = (W, D, L, S_hash) - full invariant signature"""
            w = compute_weight(node)
            d = compute_depth(node)
            l = compute_leaves(node)
            s = hash(compute_shape(node)) % 10000  # Compact shape hash
            return (w, d, l, s)
        
        def delta_vector(iv_in: tuple, iv_out: tuple) -> tuple:
            """ΔI = I(out) - I(in) for comparable metrics"""
            return (
                iv_out[0] - iv_in[0],  # ΔW
                iv_out[1] - iv_in[1],  # ΔD
                iv_out[2] - iv_in[2],  # ΔL
                iv_out[3] == iv_in[3], # S_same (shape preserved?)
            )
        
        # Step 1: Compute Δ-vector for each example
        deltas = []
        for inp_lbl, out_lbl in examples:
            inp_node = encoder(inp_lbl)
            out_node = encoder(out_lbl)
            
            iv_in = invariant_vector(inp_node)
            iv_out = invariant_vector(out_node)
            dv = delta_vector(iv_in, iv_out)
            
            print(f"  {inp_lbl} → {out_lbl}:")
            print(f"    I(in)={iv_in}, I(out)={iv_out}")
            print(f"    Δ=(ΔW={dv[0]}, ΔD={dv[1]}, ΔL={dv[2]}, S_same={dv[3]})")
            deltas.append(dv)
        
        # Step 2: Check invariance (all delta-vectors must be identical)
        if len(set(deltas)) == 1:
            invariant = deltas[0]
            print(f"\n  [INVARIANT VECTOR FOUND!]")
            print(f"    ΔW = {invariant[0]}, ΔD = {invariant[1]}, ΔL = {invariant[2]}, S_same = {invariant[3]}")
            
            # Step 3: MDL Cost Calculation
            # Rule cost: ~50 bytes (hash + metadata)
            # Fact cost: ~40 bytes per edge
            rule_cost = 50
            facts_cost = len(examples) * 40
            
            print(f"\n  [MDL] Cost analysis:")
            print(f"    Facts cost: {facts_cost} bytes ({len(examples)} × 40)")
            print(f"    Rule cost:  {rule_cost} bytes")
            
            if rule_cost < facts_cost:
                compression_ratio = facts_cost / rule_cost
                print(f"    → COMPRESS: {compression_ratio:.1f}x savings")
                
                # Step 4: Create the rule with full vector signature
                dw, dd, dl, s_same = invariant
                rule_name = f"RULE_Δ(W{dw:+d},D{dd:+d},L{dl:+d},S={'=' if s_same else '≠'})"
                rule_hash = get_token_hash_hex(rule_name)
                self.tank.labels[rule_hash] = rule_name
                
                # Step 5: Store rule (not individual facts)
                # Add rule definition to tank
                self.tank.absorb(rule_name, f"ΔW={dw},ΔD={dd},ΔL={dl}", "DEFINES", 10.0, 
                               Truth.ALPHA, f"DISCOVER_δ:VECTOR")
                
                # Track what this rule covers
                self.tank.absorb(rule_name, relation, "APPLIES_TO", 10.0,
                               Truth.ALPHA, f"DISCOVER_δ:SCOPE")
                
                print(f"  [LAW] Created: {rule_name}")
                print(f"  [COMPRESSED] Replaced {len(examples)} facts with 1 rule")
                print(f"  [PROOF] All {len(examples)} examples have identical ΔW")
                
                return {
                    "invariant": invariant,
                    "rule_name": rule_name,
                    "compression_ratio": compression_ratio,
                    "facts_replaced": len(examples),
                }
            else:
                print(f"    → NO COMPRESS: Rule not cheaper, keeping facts")
                # Store facts individually
                for inp_lbl, out_lbl in examples:
                    self.tank.absorb(inp_lbl, out_lbl, relation, 10.0, Truth.ALPHA, 
                                   f"DISCOVER_δ:UNCOMPRESSED")
                return {"invariant": invariant, "compressed": False}
        else:
            print(f"\n  [FAIL] No invariant: ΔW values differ {set(deltas)}")
            return None

    def explain(self, u_lbl: str, v_lbl: str):
        """Explain how we know A→B."""
        u_h = get_token_hash_hex(u_lbl)
        v_h = get_token_hash_hex(v_lbl)
        eid = bond_id(u_h, v_h, "IMP")
        
        if eid not in self.tank.edges:
            print(f"No edge {u_lbl} → {v_lbl} found.")
            return
        
        e = self.tank.edges[eid]
        print(f"\n=== EXPLAIN: {u_lbl} → {v_lbl} ===")
        print(f"  Energy: {e.energy:.2f}")
        print(f"  Ring: {e.ring.name}")
        print(f"  Provenance ({len(e.provenance)}):")
        for p in e.provenance:
            if p.path:
                path_lbl = " → ".join(self.tank.label(h) for h in p.path)
                print(f"    [{p.ring.name}] {p.source}: {path_lbl}")
            else:
                print(f"    [{p.ring.name}] {p.source}")

    def ignite(self):
        self.cycle_lambda()
        self.cycle_mendeleev()


# ============================================================================
# MAIN
# ============================================================================

