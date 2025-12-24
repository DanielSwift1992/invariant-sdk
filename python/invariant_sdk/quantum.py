"""
quantum.py — Dyadic Multi-Scale Energy Calculator (v1.9.5)

Theory (RUNTIME_CONTRACT v1.9.5):
  E = Σₛ wₛ × Σ_events Ψ(event)²
  
  CRITICAL: σ-event = (doc_id, ctx_hash), NOT occurrence.
  
  Key properties:
  - Input: List of σ-events (Dict[anchor→alpha])
  - Presence: MAX alpha per anchor (0/1 semantics)
  - Tiling: Clean dyadic (step = window_size)
  - Partial windows: Included with same weight (no boundary loss)
  
Formula:
  Ψ² = Σα² + 2Σαᵢαⱼ (presence + interference)
"""

from __future__ import annotations

import math
import warnings
from typing import Dict, List, Optional, Tuple, Set


# =============================================================================
# σ-EVENT BASED ENERGY (Theory-Correct v1.9.5)
# =============================================================================

def compute_sigma_energy(
    sigma_events: List[Dict[str, float]],
    query_anchors: Set[str],
    max_scale: int = 8,
) -> float:
    """
    Compute Full Hamiltonian energy E = Ψ² over dyadic scales.
    
    Args:
        sigma_events: List of σ-events, each is Dict[anchor_hash8 -> alpha]
                     e.g. [{"abc": 0.5, "def": 0.3}, {"abc": 0.5}, ...]
        query_anchors: Set of query anchor hash8s
        max_scale: Maximum dyadic scale (default 8 → up to 256 events)
    
    Returns:
        Total energy across all scales (float)
    
    Boundary Condition (v1.7.2):
        Partial windows at the end ARE included with same weight.
        No event is "lost" due to not fitting a complete tile.
    """
    if not sigma_events:
        return 0.0
    
    # Filter events to only include query-relevant anchors
    filtered_events: List[Dict[str, float]] = []
    for event in sigma_events:
        relevant = {h8: alpha for h8, alpha in event.items() 
                   if h8 in query_anchors and alpha > 0}
        if relevant:
            filtered_events.append(relevant)
    
    if not filtered_events:
        return 0.0
    
    n_events = len(filtered_events)
    total_energy = 0.0
    
    for s in range(max_scale):
        window_size = 2 ** s
        if window_size > n_events:
            break
        
        # Derived weight: smaller scales contribute more (local structure)
        weight_s = 1.0 / (2 ** s)
        scale_energy = 0.0
        
        # CLEAN DYADIC TILING: step = window_size
        step = window_size
        
        for start in range(0, n_events, step):
            end = min(start + window_size, n_events)
            # v1.7.2: Include partial windows (no boundary loss)
            # Even incomplete windows contribute energy
            if end <= start:
                continue
            
            window_events = filtered_events[start:end]
            
            # Collect unique anchors with max alpha (presence 0/1 semantics)
            window_anchors: Dict[str, float] = {}
            for event in window_events:
                for h8, alpha in event.items():
                    window_anchors[h8] = max(window_anchors.get(h8, 0), alpha)
            
            # Ψ = sum of amplitudes (each anchor counted ONCE per window)
            psi = sum(window_anchors.values())
            
            # E = Ψ² (Full Hamiltonian)
            window_energy = psi ** 2
            scale_energy += window_energy
        
        total_energy += weight_s * scale_energy
    
    return total_energy


def compute_sigma_coherence(
    sigma_events: List[Dict[str, float]],
    query_anchors: Set[str],
    max_scale: int = 8,
    query_amplitudes: Optional[Dict[str, float]] = None,
    direct_anchors: Optional[Set[str]] = None,
) -> float:
    """
    Compute Interaction-Only energy I = Ψ² - Σα².
    
    This is the PURE INTERFERENCE term: 2Σαᵢαⱼ
    Use for typed/strict mode where pure structure matters.
    
    v1.9.4: query_amplitudes parameter for query-level binding.
    v1.9.5: direct_anchors parameter for Intent-Sovereignty (Invariant IV).
    
    Args:
        direct_anchors: Set of hash8s that are direct query terms.
                       Direct-to-Direct pairs ALWAYS bypass threshold.
                       (Will > Observation per Hierarchy Law)
    
    Returns:
        Coherence energy (0 if no interaction, positive if anchors co-occur)
    """
    if not sigma_events:
        return 0.0
    
    filtered_events: List[Dict[str, float]] = []
    for event in sigma_events:
        relevant = {h8: alpha for h8, alpha in event.items() 
                   if h8 in query_anchors and alpha > 0}
        if relevant:
            filtered_events.append(relevant)
    
    if len(filtered_events) < 2:
        return 0.0
    
    n_events = len(filtered_events)
    total_coherence = 0.0
    
    # v1.9.4: Query-level binding (invariant X)
    # Threshold from QUERY amplitudes (constant per query), not from doc
    if query_amplitudes:
        threshold = binding_threshold(query_amplitudes)
    else:
        # Fallback: compute from what's in document (legacy behavior)
        all_query_alphas = {}
        for event in filtered_events:
            for h8, alpha in event.items():
                all_query_alphas[h8] = max(all_query_alphas.get(h8, 0), alpha)
        threshold = binding_threshold(all_query_alphas)
    
    for s in range(max_scale):
        window_size = 2 ** s
        if window_size > n_events:
            break
        
        weight_s = 1.0 / (2 ** s)
        scale_coherence = 0.0
        step = window_size
        
        for start in range(0, n_events, step):
            end = min(start + window_size, n_events)
            if end <= start:
                continue
            
            window_events = filtered_events[start:end]
            
            window_anchors: Dict[str, float] = {}
            for event in window_events:
                for h8, alpha in event.items():
                    window_anchors[h8] = max(window_anchors.get(h8, 0), alpha)
            
            # Need at least 2 different anchors for interaction
            if len(window_anchors) < 2:
                continue
            
            # v1.9.5: Intent-Sovereignty LAW (Invariant IV)
            # Direct-to-Direct pairs ALWAYS pass (Will > Observation)
            # Expansion pairs require pair_product >= threshold
            anchors_list = list(window_anchors.items())
            window_coherence = 0.0
            for i, (h8_i, alpha_i) in enumerate(anchors_list):
                for h8_j, alpha_j in anchors_list[i+1:]:
                    pair_product = alpha_i * alpha_j
                    
                    # Intent-Sovereignty: direct pairs bypass threshold
                    is_direct_pair = (
                        direct_anchors is not None
                        and h8_i in direct_anchors
                        and h8_j in direct_anchors
                    )
                    
                    if is_direct_pair or pair_product >= threshold:
                        window_coherence += 2 * pair_product  # 2αᵢαⱼ
            
            scale_coherence += window_coherence
        
        total_coherence += weight_s * scale_coherence
    
    return total_coherence


def compute_ranking_tuple(
    sigma_events: List[Dict[str, float]],
    query_anchors: Set[str],
    max_scale: int = 8,
) -> Tuple[float, float, int]:
    """
    Compute (E, I, min_scale) tuple for stable ranking (v1.8).
    
    Returns:
        E: Full Hamiltonian energy
        I: Pure interference (coherence)
        min_scale: Smallest scale where ≥2 different anchors in a window
                   (lower = more local coherence, better)
    
    Ranking order: (-E desc, -I desc, min_scale asc)
    """
    if not sigma_events:
        return (0.0, 0.0, max_scale)
    
    # Filter to query-relevant anchors
    filtered_events: List[Dict[str, float]] = []
    for event in sigma_events:
        relevant = {h8: alpha for h8, alpha in event.items() 
                   if h8 in query_anchors and alpha > 0}
        if relevant:
            filtered_events.append(relevant)
    
    if not filtered_events:
        return (0.0, 0.0, max_scale)
    
    n_events = len(filtered_events)
    total_energy = 0.0
    total_coherence = 0.0
    min_resonance_scale = max_scale  # Smallest scale with ≥2 different anchors
    
    for s in range(max_scale):
        window_size = 2 ** s
        if window_size > n_events:
            break
        
        weight_s = 1.0 / (2 ** s)
        scale_energy = 0.0
        scale_coherence = 0.0
        step = window_size
        
        for start in range(0, n_events, step):
            end = min(start + window_size, n_events)
            if end <= start:
                continue
            
            window_events = filtered_events[start:end]
            
            window_anchors: Dict[str, float] = {}
            for event in window_events:
                for h8, alpha in event.items():
                    window_anchors[h8] = max(window_anchors.get(h8, 0), alpha)
            
            psi = sum(window_anchors.values())
            sum_sq = sum(a ** 2 for a in window_anchors.values())
            
            window_energy = psi ** 2
            window_coherence = max(0.0, psi ** 2 - sum_sq)
            
            scale_energy += window_energy
            scale_coherence += window_coherence
            
            # Track minimum scale with resonance (≥2 different anchors)
            if len(window_anchors) >= 2 and s < min_resonance_scale:
                min_resonance_scale = s
        
        total_energy += weight_s * scale_energy
        total_coherence += weight_s * scale_coherence
    
    return (total_energy, total_coherence, min_resonance_scale)


# =============================================================================
# v1.9: INVARIANT IX — MAXIMALITY LAW (Peak Energy Wins)
# =============================================================================

def compute_peak_score(
    sigma_events: List[Dict[str, float]],
    query_anchors: Set[str],
    max_scale: int = 8,
    query_amplitudes: Optional[Dict[str, float]] = None,
    direct_anchors: Optional[Set[str]] = None,
) -> float:
    """
    Invariant IX: Peak Energy Wins.
    
    Returns maximum window energy across all dyadic scales.
    Needles in long documents are not diluted.
    
    v1.9.4: query_amplitudes parameter for query-level binding.
    v1.9.5: direct_anchors parameter for Intent-Sovereignty (Invariant IV).
    
    Energy is now binding-protected: E = Σα² + filtered_2αᵢαⱼ
    Direct-to-Direct pairs ALWAYS contribute (Will > Observation).
    
    Score_max(d,q) = max_{window} E_filtered(window, q)
    """
    if not sigma_events:
        return 0.0
    
    filtered_events: List[Dict[str, float]] = []
    for event in sigma_events:
        relevant = {h8: alpha for h8, alpha in event.items() 
                   if h8 in query_anchors and alpha > 0}
        if relevant:
            filtered_events.append(relevant)
    
    if not filtered_events:
        return 0.0
    
    n_events = len(filtered_events)
    max_energy = 0.0
    
    # v1.9.4: Query-level binding threshold
    if query_amplitudes:
        threshold = binding_threshold(query_amplitudes)
    else:
        # Fallback: compute from all anchors in doc
        all_doc_alphas = {}
        for event in filtered_events:
            for h8, alpha in event.items():
                all_doc_alphas[h8] = max(all_doc_alphas.get(h8, 0), alpha)
        threshold = binding_threshold(all_doc_alphas)
    
    for s in range(max_scale):
        window_size = 2 ** s
        if window_size > n_events:
            break
        
        step = window_size
        
        for start in range(0, n_events, step):
            end = min(start + window_size, n_events)
            if end <= start:
                continue
            
            window_events = filtered_events[start:end]
            
            window_anchors: Dict[str, float] = {}
            for event in window_events:
                for h8, alpha in event.items():
                    window_anchors[h8] = max(window_anchors.get(h8, 0), alpha)
            
            # v1.9.5: Binding-protected energy with Intent-Sovereignty
            # E = Σα² + Σ(filtered 2αᵢαⱼ)
            # Direct pairs ALWAYS pass (Will > Observation)
            sum_sq = sum(a ** 2 for a in window_anchors.values())
            
            # Compute filtered cross-terms
            filtered_cross = 0.0
            anchors_list = list(window_anchors.items())
            for i, (h8_i, alpha_i) in enumerate(anchors_list):
                for h8_j, alpha_j in anchors_list[i+1:]:
                    pair_product = alpha_i * alpha_j
                    
                    # Intent-Sovereignty: direct pairs bypass threshold
                    is_direct_pair = (
                        direct_anchors is not None
                        and h8_i in direct_anchors
                        and h8_j in direct_anchors
                    )
                    
                    if is_direct_pair or pair_product >= threshold:
                        filtered_cross += 2 * pair_product
            
            window_energy = sum_sq + filtered_cross
            
            # Track maximum
            if window_energy > max_energy:
                max_energy = window_energy
    
    return max_energy


def compute_free_energy_score(
    sigma_events: List[Dict[str, float]],
    query_anchors: Set[str],
    beta: float,
    max_scale: int = 8,
) -> float:
    """
    Invariant IX': Free Energy Aggregator.
    
    Score_β = (1/β) × log Σ exp(β × E(window))
    
    β → ∞: Max mode (needle queries)
    β → 0: Sum mode (thematic queries)
    """
    if not sigma_events or beta <= 0:
        return 0.0
    
    filtered_events: List[Dict[str, float]] = []
    for event in sigma_events:
        relevant = {h8: alpha for h8, alpha in event.items() 
                   if h8 in query_anchors and alpha > 0}
        if relevant:
            filtered_events.append(relevant)
    
    if not filtered_events:
        return 0.0
    
    n_events = len(filtered_events)
    window_energies: List[float] = []
    
    for s in range(max_scale):
        window_size = 2 ** s
        if window_size > n_events:
            break
        
        step = window_size
        
        for start in range(0, n_events, step):
            end = min(start + window_size, n_events)
            if end <= start:
                continue
            
            window_events = filtered_events[start:end]
            
            window_anchors: Dict[str, float] = {}
            for event in window_events:
                for h8, alpha in event.items():
                    window_anchors[h8] = max(window_anchors.get(h8, 0), alpha)
            
            psi = sum(window_anchors.values())
            window_energy = psi ** 2
            window_energies.append(window_energy)
    
    if not window_energies:
        return 0.0
    
    # Log-sum-exp trick for numerical stability
    # F = (1/β) * log Σ exp(β*E) = max_E + (1/β) * log Σ exp(β*(E - max_E))
    max_e = max(window_energies)
    if max_e <= 0:
        return 0.0
    
    # v1.9.4: Fixed formula - multiply max_e by beta before adding
    log_sum = beta * max_e + math.log(sum(math.exp(beta * (e - max_e)) for e in window_energies))
    return log_sum / beta


def beta_from_query(amplitudes: Dict[str, float]) -> float:
    """
    Invariant IX'.3: Derive β from query concentration.
    
    β = max(α) / (Σα + ε) × N
    
    Needle query (one dominant anchor) → β ≈ 1 → max mode
    Thematic query (equal anchors) → β ≈ 1/N → sum mode
    
    NOTE: No arbitrary clamp. Pure derived value.
    """
    if not amplitudes:
        return 1.0
    
    values = [a for a in amplitudes.values() if a > 0]
    if not values:
        return 1.0
    
    max_alpha = max(values)
    sum_alpha = sum(values)
    
    # β = concentration × N (pure derivation)
    n = len(values)
    ratio = max_alpha / (sum_alpha + 1e-9)
    
    return ratio * n


def binding_threshold(amplitudes: Dict[str, float]) -> float:
    """
    Invariant X: Binding Threshold.
    
    ε(q) = median(αᵢ × αⱼ) for all query pairs.
    
    Cross-terms with αᵢ × αⱼ ≤ ε are considered noise.
    """
    if not amplitudes or len(amplitudes) < 2:
        return 0.0
    
    values = [a for a in amplitudes.values() if a > 0]
    if len(values) < 2:
        return 0.0
    
    # Compute all pairwise products
    products = []
    for i, a in enumerate(values):
        for b in values[i+1:]:
            products.append(a * b)
    
    if not products:
        return 0.0
    
    # Median as threshold
    products.sort()
    mid = len(products) // 2
    if len(products) % 2 == 0:
        return (products[mid - 1] + products[mid]) / 2
    return products[mid]


def compute_sigma_decomposition(
    sigma_events: List[Dict[str, float]],
    query_anchors: Set[str],
    max_scale: int = 8,
) -> Dict[str, float]:
    """
    Decompose energy into presence and interference components.
    
    Returns:
        {
            "total": E = Ψ²,
            "presence": Σα²,
            "interference": 2Σαᵢαⱼ,
            "coherence_ratio": interference / total
        }
    """
    if not sigma_events:
        return {"total": 0.0, "presence": 0.0, "interference": 0.0, "coherence_ratio": 0.0}
    
    filtered_events: List[Dict[str, float]] = []
    for event in sigma_events:
        relevant = {h8: alpha for h8, alpha in event.items() 
                   if h8 in query_anchors and alpha > 0}
        if relevant:
            filtered_events.append(relevant)
    
    if not filtered_events:
        return {"total": 0.0, "presence": 0.0, "interference": 0.0, "coherence_ratio": 0.0}
    
    n_events = len(filtered_events)
    total_presence = 0.0
    total_interference = 0.0
    
    for s in range(max_scale):
        window_size = 2 ** s
        if window_size > n_events:
            break
        
        weight_s = 1.0 / (2 ** s)
        step = window_size
        
        for start in range(0, n_events, step):
            end = min(start + window_size, n_events)
            if end <= start:
                continue
            
            window_events = filtered_events[start:end]
            
            window_anchors: Dict[str, float] = {}
            for event in window_events:
                for h8, alpha in event.items():
                    window_anchors[h8] = max(window_anchors.get(h8, 0), alpha)
            
            psi = sum(window_anchors.values())
            sum_sq = sum(a ** 2 for a in window_anchors.values())
            
            presence = sum_sq
            interference = max(0.0, psi ** 2 - sum_sq)
            
            total_presence += weight_s * presence
            total_interference += weight_s * interference
    
    total = total_presence + total_interference
    
    return {
        "total": total,
        "presence": total_presence,
        "interference": total_interference,
        "coherence_ratio": total_interference / total if total > 0 else 0.0,
    }


# =============================================================================
# CONVERSION: Occurrence stream → σ-events
# =============================================================================

def occurrences_to_sigma_events(
    doc_events: List[Tuple[int, str, float]],
    query_hashes: Set[str],
) -> List[Dict[str, float]]:
    """
    Convert legacy occurrence stream to σ-events.
    
    Groups by line number (ordinal), takes MAX alpha per anchor per line.
    
    Args:
        doc_events: List of (line, hash8, alpha) tuples
        query_hashes: Set of query anchor hash8s
    
    Returns:
        List of σ-events (sorted by line)
    """
    line_events: Dict[int, Dict[str, float]] = {}
    for line, h8, alpha in doc_events:
        if h8 in query_hashes and alpha > 0:
            if line not in line_events:
                line_events[line] = {}
            # MAX alpha per anchor per line (presence semantics)
            line_events[line][h8] = max(line_events[line].get(h8, 0), alpha)
    
    return [line_events[ln] for ln in sorted(line_events.keys())]


# =============================================================================
# LEGACY WRAPPERS (Deprecated - use sigma_* functions directly)
# =============================================================================

def compute_dyadic_energy(
    doc_events: List[Tuple[int, str, float]],
    query_hashes: Set[str],
    max_scale: int = 8,
) -> float:
    """
    DEPRECATED: Use compute_sigma_energy with occurrences_to_sigma_events.
    
    This wrapper converts occurrence stream to σ-events and calls new API.
    """
    sigma_events = occurrences_to_sigma_events(doc_events, query_hashes)
    return compute_sigma_energy(sigma_events, query_hashes, max_scale)


def compute_coherence_energy(
    doc_events: List[Tuple[int, str, float]],
    query_hashes: Set[str],
    max_scale: int = 8,
) -> float:
    """
    DEPRECATED: Use compute_sigma_coherence with occurrences_to_sigma_events.
    """
    sigma_events = occurrences_to_sigma_events(doc_events, query_hashes)
    return compute_sigma_coherence(sigma_events, query_hashes, max_scale)


def compute_energy_decomposition(
    doc_events: List[Tuple[int, str, float]],
    query_hashes: Set[str],
    max_scale: int = 8,
) -> Dict[str, float]:
    """
    DEPRECATED: Use compute_sigma_decomposition with occurrences_to_sigma_events.
    """
    sigma_events = occurrences_to_sigma_events(doc_events, query_hashes)
    return compute_sigma_decomposition(sigma_events, query_hashes, max_scale)


# =============================================================================
# NORMALIZATION
# =============================================================================

def normalize_by_entropy(score: float, n_events: int) -> float:
    """
    Apply entropy-based normalization (RUNTIME_CONTRACT §7).
    
    norm(doc) = score / log(1 + n_events)
    
    NOTE: n_events should be count of UNIQUE σ-events, not occurrences.
    """
    if n_events <= 0:
        return score
    return score / math.log(1 + n_events)


# =============================================================================
# AMPLITUDE CALCULATION
# =============================================================================

def compute_amplitude(
    *,
    mass: float,
    df: int,
    n_docs: int,
    coupling: float = 1.0,
) -> float:
    """
    Compute anchor amplitude α = Mass × IDF × Coupling.
    
    INVARIANT: df == 0 ⟹ α = 0
    """
    if df == 0:
        return 0.0
    
    if df >= n_docs:
        idf = 0.0
    else:
        idf = math.log(n_docs / df)
    
    return mass * idf * coupling
