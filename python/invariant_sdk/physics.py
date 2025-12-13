"""
physics.py — HaloPhysics Engine (Semantic Scalpels)

Unified high-level API for semantic physics operations.
Implements Bisection Law (INVARIANTS.md): every action provides ≥1 bit information gain.

Operations:
  - focus() = Interference (∩) — Bisector, cuts exponentially
  - expand() = Blend (∪) — Accumulator, expands context
  - subtract() = Negative Space Cut (\\) — Bisector, ≥1 bit
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .halo import HaloClient


@dataclass
class VerificationResult:
    """
    Result of σ-proof verification.
    
    An assertion is considered σ-proven if:
      1. A path exists in the σ-overlay from subject to object
      2. At least one edge has document provenance (doc field)
    
    Without σ-proof, the assertion is a hypothesis (η) and should be
    treated with caution (e.g., blocked, flagged, or require confirmation).
    """
    
    proven: bool  # True if σ-proof exists
    path: List[Dict]  # Edges in the proof path (may be empty)
    sources: List[str]  # Document sources (provenance)
    conflicts: List[Dict]  # Conflicting edges if any
    subject_hash: str  # Resolved subject hash8
    object_hash: str  # Resolved object hash8
    message: str  # Human-readable explanation
    
    def __repr__(self) -> str:
        icon = "✓" if self.proven else "✗"
        return f"VerificationResult({icon} proven={self.proven}, sources={len(self.sources)}, conflicts={len(self.conflicts)})"


@dataclass
class Concept:
    """
    Resolved semantic concept with L0 physics properties.
    
    A Concept is either:
      - An Atom (single token, single hash8)
      - A Molecule (multiple tokens composed via MDL)
    """
    
    atoms: List[str]  # hash8 addresses
    halo: List[Dict]  # neighbors [{hash8, token, weight}]
    degree_total: int  # from server (for mass calculation)
    mean_mass: float  # from crystal meta (phase boundary)
    _client: Optional[HaloClient] = field(default=None, repr=False)
    
    @property
    def mass(self) -> float:
        """
        Topological Mass = 1/log(2 + degree).
        
        High mass (≈0.5) = Solid anchor (rare word, few connections)
        Low mass (≈0.1) = Gas/noise (common word, many connections)
        """
        return 1.0 / math.log(2 + self.degree_total) if self.degree_total >= 0 else 0.0
    
    @property
    def phase(self) -> str:
        """Phase classification: 'solid' or 'gas'."""
        return "solid" if self.mass > self.mean_mass else "gas"
    
    @property
    def is_atom(self) -> bool:
        """True if this is a single-token concept."""
        return len(self.atoms) == 1
    
    def get_orbit(self, min_weight: float = 0.0, max_weight: float = 1.0) -> List[Dict]:
        """
        Get neighbors in a specific weight range (orbital shell).
        
        Orbits (from INVARIANTS theory):
          - Core (0.8+): Synonyms, definitions
          - Near (0.5-0.8): Strong associations, properties
          - Far (0.3-0.5): Weak associations, context
        
        Returns list of {hash8, token, weight} dicts.
        """
        return [
            n for n in self.halo 
            if min_weight <= abs(n.get("weight", 0)) <= max_weight
        ]
    
    @property
    def core(self) -> List[Dict]:
        """Core orbit (|weight| ≥ 0.7) — near-synonyms."""
        return self.get_orbit(0.7, 1.0)
    
    @property
    def near(self) -> List[Dict]:
        """Near orbit (0.5 ≤ |weight| < 0.7) — strong associations."""
        return self.get_orbit(0.5, 0.7)
    
    @property
    def far(self) -> List[Dict]:
        """Far orbit (threshold ≤ |weight| < 0.5) — weak associations."""
        return self.get_orbit(0.0, 0.5)
    
    def focus(self, other: "Concept") -> "Concept":
        """
        Interference (∩) — Bisector operation.
        
        Keeps only neighbors that appear in BOTH halos.
        Weight = product of individual weights.
        
        Information Gain: ≫1 bit (exponential reduction in high-dim space).
        
        Example: king.focus(woman) → neighbors around "queen"
        """
        if self._client is None:
            raise RuntimeError("Concept requires _client for focus()")
        
        # Build hash8 → weight maps
        self_map = {n["hash8"]: n for n in self.halo}
        other_map = {n["hash8"]: n for n in other.halo}
        
        # Intersection with weight multiplication
        intersection = []
        for h8, self_n in self_map.items():
            if h8 in other_map:
                other_n = other_map[h8]
                intersection.append({
                    "hash8": h8,
                    "token": self_n.get("token", ""),
                    "weight": self_n["weight"] * other_n["weight"]
                })
        
        # Sort by |weight| descending
        intersection.sort(key=lambda x: abs(x["weight"]), reverse=True)
        
        return Concept(
            atoms=self.atoms + other.atoms,
            halo=intersection,
            degree_total=len(intersection),
            mean_mass=self.mean_mass,
            _client=self._client
        )
    
    def expand(self, other: "Concept", op: str = "mean") -> "Concept":
        """
        Blend (∪) — Accumulator operation.
        
        Takes union of neighbors with aggregated weights.
        
        Note: This is NOT a bisector — it INCREASES uncertainty.
        Use for exploration, not for precision.
        
        ops: "mean", "sum", "max"
        """
        if self._client is None:
            raise RuntimeError("Concept requires _client for expand()")
        
        # Collect all neighbors
        combined: Dict[str, List[Dict]] = {}
        for n in self.halo:
            h8 = n["hash8"]
            if h8 not in combined:
                combined[h8] = []
            combined[h8].append(n)
        for n in other.halo:
            h8 = n["hash8"]
            if h8 not in combined:
                combined[h8] = []
            combined[h8].append(n)
        
        # Aggregate
        union = []
        for h8, entries in combined.items():
            weights = [e["weight"] for e in entries]
            if op == "mean":
                w = sum(weights) / len(weights)
            elif op == "sum":
                w = sum(weights)
            elif op == "max":
                w = max(weights, key=abs)
            else:
                w = sum(weights) / len(weights)
            
            union.append({
                "hash8": h8,
                "token": entries[0].get("token", ""),
                "weight": w
            })
        
        union.sort(key=lambda x: abs(x["weight"]), reverse=True)
        
        return Concept(
            atoms=self.atoms + other.atoms,
            halo=union,
            degree_total=len(union),
            mean_mass=self.mean_mass,
            _client=self._client
        )
    
    def subtract(self, other: "Concept") -> "Concept":
        """
        Subtraction (A \\ B) — Bisector operation.
        
        Keeps neighbors in A that are NOT in B.
        
        Information Gain: ≥1 bit (removes B-region from A).
        """
        other_hashes = {n["hash8"] for n in other.halo}
        diff = [n for n in self.halo if n["hash8"] not in other_hashes]
        
        return Concept(
            atoms=self.atoms,
            halo=diff,
            degree_total=len(diff),
            mean_mass=self.mean_mass,
            _client=self._client
        )
    
    def __repr__(self) -> str:
        phase_icon = "◆" if self.phase == "solid" else "○"
        return (
            f"Concept({phase_icon} atoms={len(self.atoms)}, "
            f"halo={len(self.halo)}, mass={self.mass:.3f})"
        )


class HaloPhysics:
    """
    Semantic Physics Engine.
    
    High-level API for working with the Halo server using
    Bisection Law principles (INVARIANTS.md).
    
    Supports local overlay (σ-facts) layered on global crystal (α-axioms).
    
    Example:
        client = HaloPhysics("http://165.22.145.158:8080")
        king = client.resolve("king")
        queen = king.focus(client.resolve("woman"))
        print(queen.core)  # Neighbors in core orbit
        
        # With local overlay:
        client = HaloPhysics(server, overlay=Path("./project.overlay.jsonl"))
    """
    
    def __init__(
        self, 
        server: str = "http://165.22.145.158:8080",
        overlay: Optional[Path] = None,
        auto_discover_overlay: bool = True,
    ):
        from .overlay import OverlayGraph, find_overlays
        
        self._client = HaloClient(server)
        self._meta = None
        
        # Load overlay(s)
        if overlay:
            self._overlay = OverlayGraph.load(overlay)
        elif auto_discover_overlay:
            paths = find_overlays()
            self._overlay = OverlayGraph.load_cascade(paths) if paths else None
        else:
            self._overlay = None
    
    @property
    def meta(self) -> Dict:
        """Crystal metadata (cached)."""
        if self._meta is None:
            self._meta = self._client.get_meta()
        return self._meta
    
    @property
    def mean_mass(self) -> float:
        """Mean mass from crystal (phase boundary)."""
        return self.meta.get("mean_mass", 0.26)
    
    @property
    def crystal_id(self) -> str:
        """Crystal identifier."""
        return self.meta.get("crystal_id", "unknown")
    
    @property
    def overlay(self):
        """Access to local overlay graph."""
        return self._overlay
    
    def _merge_with_overlay(self, hash8: str, global_halo: List[Dict]) -> List[Dict]:
        """
        Merge global halo with local overlay.
        
        Hierarchy Law: Local σ beats Global α.
        """
        if not self._overlay:
            return global_halo
        
        # Get local edges for this node
        local_edges = self._overlay.get_neighbors(hash8)
        
        # Filter out suppressed global edges
        filtered_global = [
            n for n in global_halo
            if not self._overlay.is_suppressed(hash8, n.get("hash8", ""))
        ]
        
        # Merge: local first (priority), then global
        merged = {}
        
        # Add global edges
        for n in filtered_global:
            h8 = n.get("hash8", "")
            merged[h8] = n
        
        # Override with local edges (σ > α)
        for n in local_edges:
            h8 = n.get("hash8", "")
            merged[h8] = n
        
        # Sort by |weight| descending
        result = list(merged.values())
        result.sort(key=lambda x: abs(x.get("weight", 0)), reverse=True)
        
        return result
    
    def resolve(self, text: str, mode: str = "interference") -> Concept:
        """
        Resolve text to a Concept with full physics properties.
        
        Args:
            text: Word or short phrase
            mode: "interference" (focus) or "blend" (expand) for multi-token
        
        Returns:
            Concept with halo, mass, phase, and physics methods
            
        Note: Local overlay (σ) is merged with global halo (α).
        """
        from .halo import hash8_hex
        
        # Simple approach: try word with Ġ prefix (word-begin token)
        words = [w.strip().lower() for w in text.split() if w.strip()]
        atoms = []
        all_halos = []
        total_degree = 0
        
        for word in words:
            # Try Ġ-prefixed first (common for Qwen/GPT-2 BPE)
            candidates = [f"Ġ{word}", word, f"▁{word}"]
            found = False
            
            for candidate in candidates:
                h8 = hash8_hex(candidate)
                result = self._client.get_halo_page(h8, limit=500)
                
                if result.get("exists") or result.get("neighbors"):
                    atoms.append(h8)
                    neighbors = result.get("neighbors", [])
                    
                    # Add token info to neighbors
                    for n in neighbors:
                        n["token"] = n.get("token", n.get("hash8", "")[:8])
                    
                    # Merge with overlay
                    neighbors = self._merge_with_overlay(h8, neighbors)
                    
                    all_halos.append(neighbors)
                    total_degree = result.get("meta", {}).get("degree_total", len(neighbors))
                    found = True
                    break
            
            if not found:
                # Check if word exists in local overlay only
                if self._overlay:
                    h8 = hash8_hex(f"Ġ{word}")
                    local_edges = self._overlay.get_neighbors(h8)
                    if local_edges:
                        atoms.append(h8)
                        all_halos.append(local_edges)
                        found = True
        
        if not atoms:
            # No atoms found
            return Concept(
                atoms=[],
                halo=[],
                degree_total=0,
                mean_mass=self.mean_mass,
                _client=self._client
            )
        
        # Single atom: return its halo directly
        if len(atoms) == 1:
            return Concept(
                atoms=atoms,
                halo=all_halos[0],
                degree_total=total_degree,
                mean_mass=self.mean_mass,
                _client=self._client
            )
        
        # Multiple atoms: apply interference or blend
        if mode == "interference":
            halo = self._client._interference_halo(all_halos)
        else:
            halo = self._client._blend_halo(all_halos)
        
        return Concept(
            atoms=atoms,
            halo=halo,
            degree_total=len(halo),
            mean_mass=self.mean_mass,
            _client=self._client
        )
    
    def resolve_word(self, word: str) -> Optional[str]:
        """Resolve a single word to its hash8 address."""
        return self._client.resolve_word(word)
    
    def subtract(self, a: Concept, b: Concept) -> Concept:
        """
        Negative space cut (A \\ B).
        
        Removes B-meaning from A.
        Information Gain: ≥1 bit.
        """
        return a.subtract(b)
    
    def verify(
        self, 
        subject: str, 
        object: str,
        predicate: str = None,
    ) -> VerificationResult:
        """
        Verify if an assertion has σ-proof (documentary evidence).
        
        This is the core B2B Guardrails function:
          - LLM says something (η = hypothesis)
          - We check if local documents (σ) support it
          - If no σ-path → assertion is unverified
        
        σ-proof requires:
          1. Path exists in σ-overlay from subject to object
          2. At least one edge has document provenance
        
        Note: Global crystal (α) is NOT used for proof.
        α provides context/associations, σ provides truth.
        
        Args:
            subject: Subject of assertion (e.g., "contract", "Elon Musk")
            object: Object of assertion (e.g., "3 years", "Apple")
            predicate: Optional predicate (currently unused, for future use)
        
        Returns:
            VerificationResult with proven status, path, sources, and conflicts
        
        Example:
            result = client.verify("contract", "3 years")
            if not result.proven:
                return "No documentary evidence for this claim"
        """
        from .halo import hash8_hex
        
        # Require overlay for verification
        if not self._overlay:
            return VerificationResult(
                proven=False,
                path=[],
                sources=[],
                conflicts=[],
                subject_hash="",
                object_hash="",
                message="No overlay loaded. Cannot verify without σ-facts."
            )
        
        # Resolve subject to hash8
        subject_hash = None
        for candidate in [f"Ġ{subject.lower()}", subject.lower(), f"▁{subject.lower()}"]:
            h8 = hash8_hex(candidate)
            if any(e.tgt for e in self._overlay.edges.get(h8, [])):
                subject_hash = h8
                break
        
        if not subject_hash:
            # Fallback: use Ġ-prefixed hash even if not in overlay
            subject_hash = hash8_hex(f"Ġ{subject.lower()}")
        
        # Resolve object to hash8
        object_hash = None
        for candidate in [f"Ġ{object.lower()}", object.lower(), f"▁{object.lower()}"]:
            h8 = hash8_hex(candidate)
            # Check if this hash appears as target in any edge
            for src, edges in self._overlay.edges.items():
                if any(e.tgt == h8 for e in edges):
                    object_hash = h8
                    break
            if object_hash:
                break
        
        if not object_hash:
            object_hash = hash8_hex(f"Ġ{object.lower()}")
        
        # Check for σ-path
        proven, path_edges = self._overlay.has_sigma_path(subject_hash, object_hash)
        
        # Extract sources (document provenance)
        sources = []
        path_dicts = []
        for edge in path_edges:
            path_dicts.append(edge.to_dict())
            if edge.doc and edge.doc not in sources:
                sources.append(edge.doc)
        
        # Check for conflicts
        conflicts = []
        for edge1, edge2 in self._overlay.get_conflicts():
            if edge1.tgt == object_hash or edge2.tgt == object_hash:
                conflicts.append({
                    "edge1": edge1.to_dict(),
                    "edge2": edge2.to_dict(),
                })
        
        # Build message
        if proven:
            if sources:
                message = f"σ-proven with provenance from: {', '.join(sources)}"
            else:
                message = "σ-path exists but no document provenance (weak proof)"
        else:
            if self._overlay.n_edges == 0:
                message = "Overlay is empty. Ingest documents first."
            else:
                message = f"No σ-path from '{subject}' to '{object}'. Assertion is unverified (η)."
        
        return VerificationResult(
            proven=proven and len(sources) > 0,  # Require provenance for true proof
            path=path_dicts,
            sources=sources,
            conflicts=conflicts,
            subject_hash=subject_hash,
            object_hash=object_hash,
            message=message
        )
    
    def get_conflicts(self) -> List[Dict]:
        """
        Get all σ-conflicts (same assertion with different values/sources).
        
        Useful for document analysis: "In contract A it says 3 years,
        but in contract B it says 5 years."
        """
        if not self._overlay:
            return []
        
        conflicts = []
        for edge1, edge2 in self._overlay.get_conflicts():
            conflicts.append({
                "edge1": edge1.to_dict(),
                "edge2": edge2.to_dict(),
            })
        return conflicts
    
    def __repr__(self) -> str:
        overlay_info = f"+overlay({self._overlay.n_edges})" if self._overlay else ""
        return f"HaloPhysics({self.crystal_id}{overlay_info})"

