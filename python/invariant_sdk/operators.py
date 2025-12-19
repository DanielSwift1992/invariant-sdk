"""
operators.py — MYCELIUM v2.3 Inference Operators

Implements the σ-operator system for documentary truth verification.

Core Principle (MYCELIUM v2.3):
  - Types are OPERATORS, not edge attributes
  - No operator may infer without relocation first
  - σ-proof requires: anchor_state != DECOHERENT AND live_state == ACTIVE

Operators:
  - infer_DEF: A ≡ B (structural pattern via witness bitmask)
  - infer_SEQ: A → B (dt ≤ dt_null after relocation)
  - infer_INHIB: A ⊣ B (W_cooccur < W_null, anti-attraction)
  - infer_GATE: A→B|C (ΔW(C) > 0, context adds energy)
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .overlay import OverlayEdge, OverlayGraph


# =============================================================================
# CONSTANTS
# =============================================================================

# Scan radius for anchor relocation (±R lines)
RELOCATION_RADIUS = 50

# Context window size for ctx_hash (±K tokens)
CONTEXT_WINDOW_K = 2

# Gas filter: tokens with df > GAS_DF_FRACTION * n_windows are Gas
#
# Information-theoretic basis (L0 Physics):
#   p = 0.3 → I(t) = -log(0.3) ≈ 1.7 bits
#   Tokens with < 2 bits information cannot be σ-evidence
#   (too frequent → no discriminative power for INHIB/GATE)
#
# Empirically validated: sweet spot 0.20–0.35, 0.3 is center
# See: percolation phase transition at ~1/e
GAS_DF_FRACTION = 0.3


# =============================================================================
# VERIFY RESULT (3-valued)
# =============================================================================

class VerifyResult(Enum):
    """
    3-valued verification result (MYCELIUM v2.3 §4.1).
    
    PROVEN: σ-path found, all edges valid
    UNKNOWN: Search budget exhausted, no path found yet
    UNPROVEN: Proved non-existence (rare, requires full closure)
    """
    PROVEN = 1
    UNKNOWN = 0
    UNPROVEN = -1


class InferResult(Enum):
    """
    3-valued inference result for operators (MYCELIUM v2.3 strict).
    
    TRUE: Operator condition proven from σ-evidence
    FALSE: Operator condition disproven from σ-evidence  
    UNKNOWN: Cannot determine (no baseline, edge not provable, etc.)
    
    Critical: UNKNOWN ≠ FALSE. "No baseline" means we cannot prove OR disprove.
    """
    TRUE = 1
    FALSE = -1
    UNKNOWN = 0


# =============================================================================
# ANCHOR INTEGRITY PROTOCOL
# =============================================================================

# Import shared normalization to ensure ctx_hash and tokenization are consistent
from .tokenize import normalize_for_hash as normalize_text


def compute_ctx_hash(text: str) -> str:
    """Compute 8-char semantic checksum of normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]


def read_context_window(path: Path, line: int, k: int = CONTEXT_WINDOW_K) -> Optional[str]:
    """
    Read context window of ±k lines around target line.
    
    Args:
        path: File path
        line: 1-indexed line number
        k: Window radius (default 2)
    
    Returns:
        Concatenated text of lines [line-k, line+k] or None if file unreadable
    """
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return None
    
    if not lines or line < 1:
        return None
    
    start = max(0, line - 1 - k)
    end = min(len(lines), line + k)
    
    return ' '.join(lines[start:end])


def reread_context_window(
    doc: str,
    line: int,
    ctx_hash: str,
    base_path: Optional[Path] = None,
) -> Tuple[Optional[str], int, int]:
    """
    Anchor Integrity Protocol (MYCELIUM v2.3 §2.2.1).
    
    Args:
        doc: Document path/name
        line: Stored line number (1-indexed)
        ctx_hash: Stored semantic checksum (8 hex chars)
        base_path: Base path for resolving relative doc paths
    
    Returns:
        (content, new_line, anchor_state)
        - content: Window text if found, None if DECOHERENT
        - new_line: Updated line number (may differ if RELOCATED)
        - anchor_state: 0=COHERENT, 1=RELOCATED, 2=DECOHERENT
    """
    # Resolve path
    if base_path:
        path = base_path / doc
    else:
        path = Path(doc)
    
    if not path.exists():
        return (None, line, OverlayEdge.DECOHERENT)
    
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return (None, line, OverlayEdge.DECOHERENT)
    
    total_lines = len(lines)
    
    # 1. Check original line
    content = read_context_window(path, line)
    if content and compute_ctx_hash(content) == ctx_hash:
        return (content, line, OverlayEdge.COHERENT)
    
    # 2. Scan radius ±R
    for offset in range(1, RELOCATION_RADIUS + 1):
        for candidate in [line + offset, line - offset]:
            if candidate < 1 or candidate > total_lines:
                continue
            content = read_context_window(path, candidate)
            if content and compute_ctx_hash(content) == ctx_hash:
                return (content, candidate, OverlayEdge.RELOCATED)
    
    # 3. Not found
    return (None, line, OverlayEdge.DECOHERENT)


# =============================================================================
# MATCHED NULL (L0-Pure, W-terms)
# =============================================================================

@dataclass
class WindowStats:
    """Statistics for matched null calculation."""
    windows: List[Set[str]]  # List of token sets per window
    token_df: Dict[str, int]  # Document frequency per token
    cooccur: Dict[Tuple[str, str], int]  # Co-occurrence counts
    n_windows: int
    # Distance tracking for dt_null computation
    dt_distances: Dict[Tuple[str, str], List[int]]  # (src, tgt) → list of distances


def build_window_stats(overlay: OverlayGraph, track_distances: bool = True) -> WindowStats:
    """
    Build window statistics for matched null calculation.
    
    Each edge with doc+line represents a window observation.
    """
    windows: List[Set[str]] = []
    token_df: Dict[str, int] = {}
    cooccur: Dict[Tuple[str, str], int] = {}
    dt_distances: Dict[Tuple[str, str], List[int]] = {}
    
    # Group edges by (doc, line) to form windows
    window_map: Dict[Tuple[str, int], Set[str]] = {}
    
    for src, edges in overlay.edges.items():
        for edge in edges:
            if edge.doc and edge.line and edge.is_provable():
                key = (edge.doc, edge.line)
                if key not in window_map:
                    window_map[key] = set()
                window_map[key].add(src)
                window_map[key].add(edge.tgt)
                
                # Track inter-token distance (approximated by witness)
                if track_distances:
                    pair = (src, edge.tgt)
                    if pair not in dt_distances:
                        dt_distances[pair] = []
                    # ADJACENT implies dt=1
                    dt = 1 if (edge.witness & OverlayEdge.ADJACENT) else 2
                    dt_distances[pair].append(dt)
    
    # Convert to list and compute statistics
    for tokens in window_map.values():
        windows.append(tokens)
        
        # Document frequency
        for t in tokens:
            token_df[t] = token_df.get(t, 0) + 1
        
        # Co-occurrence (unordered pairs)
        token_list = sorted(tokens)
        for i, t1 in enumerate(token_list):
            for t2 in token_list[i+1:]:
                pair = (t1, t2)
                cooccur[pair] = cooccur.get(pair, 0) + 1
    
    return WindowStats(
        windows=windows,
        token_df=token_df,
        cooccur=cooccur,
        n_windows=len(windows),
        dt_distances=dt_distances,
    )


def compute_dt_null_cache(
    stats: WindowStats,
    overlay: OverlayGraph,
) -> Dict[str, int]:
    """
    Compute dt_null for each token (MYCELIUM v2.3 §3.3).
    
    dt_null(B) = median(dt(A, B')) over all windows
    where B' is matched null pair for B.
    
    Returns:
        {token_hash: dt_null} cache for use in infer_SEQ
    """
    dt_null_cache: Dict[str, int] = {}
    
    for token_hash in stats.token_df:
        # Find matched null pair
        null_hash = find_matched_null(token_hash, stats, overlay)
        if null_hash is None:
            continue
        
        # Get all distances to null pair
        distances: List[int] = []
        for src in stats.token_df:
            pair = (src, null_hash)
            if pair in stats.dt_distances:
                distances.extend(stats.dt_distances[pair])
        
        if distances:
            # Median distance
            distances.sort()
            median_idx = len(distances) // 2
            dt_null_cache[token_hash] = distances[median_idx]
    
    return dt_null_cache


def find_matched_null(
    target_hash: str,
    stats: WindowStats,
    overlay: OverlayGraph,
) -> Optional[str]:
    """
    Find frequency-matched null pair (MYCELIUM v2.3 §3.2).
    
    B' = argmin |log df(x) - log df(target)|
    subject to: no σ-edge with any source, not suppressed
    
    Deterministic: tie-break by min(hash8).
    """
    if target_hash not in stats.token_df:
        return None
    
    target_df = stats.token_df[target_hash]
    log_target_df = math.log(target_df + 1)
    
    # Get all tokens connected to target (to exclude)
    connected: Set[str] = set()
    for src, edges in overlay.edges.items():
        for edge in edges:
            if edge.tgt == target_hash and edge.is_provable():
                connected.add(src)
    for edge in overlay.edges.get(target_hash, []):
        if edge.is_provable():
            connected.add(edge.tgt)
    
    # Find best match
    best_hash: Optional[str] = None
    best_diff = float('inf')
    
    for h, df in stats.token_df.items():
        if h == target_hash or h in connected:
            continue
        
        # Check not suppressed (either direction)
        if (target_hash, h) in overlay.suppressed or (h, target_hash) in overlay.suppressed:
            continue
        
        log_df = math.log(df + 1)
        diff = abs(log_df - log_target_df)
        
        if diff < best_diff or (diff == best_diff and (best_hash is None or h < best_hash)):
            best_diff = diff
            best_hash = h
    
    return best_hash


def get_cooccur_weight(a: str, b: str, stats: WindowStats) -> int:
    """Get co-occurrence weight W(A ∧ B)."""
    pair = tuple(sorted([a, b]))
    return stats.cooccur.get(pair, 0)


# =============================================================================
# INFERENCE OPERATORS
# =============================================================================

def infer_DEF(edge: OverlayEdge) -> bool:
    """
    Definition operator: A ≡ B (MYCELIUM v2.3 §2.1).
    
    True if structural pattern detected via witness bitmask.
    Requires: BRACKET, EQUALS, or GLOSSARY witness.
    """
    if not edge.is_provable():
        return False
    
    # DEF patterns: A (B), A = B, A aka B
    def_mask = OverlayEdge.BRACKET | OverlayEdge.EQUALS | OverlayEdge.GLOSSARY
    return (edge.witness & def_mask) != 0


def infer_SEQ(
    edge: OverlayEdge,
    dt_observed: int,
    stats: Optional[WindowStats] = None,
    overlay: Optional[OverlayGraph] = None,
    dt_null_cache: Optional[Dict[str, int]] = None,
) -> InferResult:
    """
    Sequence operator: A → B (MYCELIUM v2.3 §2.1).
    
    Returns:
        TRUE: dt_observed ≤ dt_null (proven sequence)
        FALSE: dt_observed > dt_null (proven not-sequence)
        UNKNOWN: Cannot determine (no baseline, edge not provable)
    """
    if not edge.is_provable():
        return InferResult.UNKNOWN
    
    # If we have pre-computed dt_null from ingest, use it
    if dt_null_cache is not None and edge.tgt in dt_null_cache:
        dt_null = dt_null_cache[edge.tgt]
        return InferResult.TRUE if dt_observed <= dt_null else InferResult.FALSE
    
    # Full check with matched null
    if stats is None or overlay is None:
        # ADJACENT witness + dt=1 is structurally proven (consecutive tokens)
        if (edge.witness & OverlayEdge.ADJACENT) != 0 and dt_observed == 1:
            return InferResult.TRUE
        # Cannot determine without baseline
        return InferResult.UNKNOWN
    
    # Find matched null pair for target
    null_hash = find_matched_null(edge.tgt, stats, overlay)
    if null_hash is None:
        # No baseline available → UNKNOWN (not FALSE!)
        # ADJACENT + dt=1 still structurally proven
        if (edge.witness & OverlayEdge.ADJACENT) != 0 and dt_observed == 1:
            return InferResult.TRUE
        return InferResult.UNKNOWN
    
    # Compute dt_null from distances if available
    if edge.tgt in stats.dt_distances:
        distances = []
        for src_tgt, dist_list in stats.dt_distances.items():
            if src_tgt[1] == null_hash:
                distances.extend(dist_list)
        if distances:
            distances.sort()
            dt_null = distances[len(distances) // 2]
            return InferResult.TRUE if dt_observed <= dt_null else InferResult.FALSE
    
    # Fallback: ADJACENT + dt=1
    if (edge.witness & OverlayEdge.ADJACENT) != 0 and dt_observed == 1:
        return InferResult.TRUE
    
    return InferResult.UNKNOWN


def infer_INHIB(
    src: str,
    tgt: str,
    stats: WindowStats,
    overlay: OverlayGraph,
) -> InferResult:
    """
    Inhibition operator: A ⊣ B (MYCELIUM v2.3 §3.3).
    
    Returns:
        TRUE: W_cooccur < W_null (proven anti-correlation)
        FALSE: W_cooccur >= W_null (proven not anti-correlation)
        UNKNOWN: Cannot determine (no baseline, or Gas token)
    
    Gas Filter: High-frequency tokens (stopwords) cannot be INHIB evidence.
    """
    # Gas filter: high-df tokens cannot participate in INHIB
    gas_threshold = int(stats.n_windows * GAS_DF_FRACTION)
    src_df = stats.token_df.get(src, 0)
    tgt_df = stats.token_df.get(tgt, 0)
    
    if src_df > gas_threshold or tgt_df > gas_threshold:
        return InferResult.UNKNOWN  # Gas tokens cannot prove INHIB
    
    # Get observed co-occurrence
    w_cooccur = get_cooccur_weight(src, tgt, stats)
    
    # Find matched null for comparison
    null_hash = find_matched_null(tgt, stats, overlay)
    if null_hash is None:
        # No baseline → UNKNOWN (not FALSE!)
        return InferResult.UNKNOWN
    
    w_null = get_cooccur_weight(src, null_hash, stats)
    
    # Compare with baseline
    if w_cooccur < w_null:
        return InferResult.TRUE
    else:
        return InferResult.FALSE


def infer_GATE(
    src: str,
    tgt: str,
    context: str,
    stats: WindowStats,
) -> InferResult:
    """
    Gate operator: A→B|C (MYCELIUM v2.3 §3.4).
    
    Returns:
        TRUE: ΔW(C) >= 1 (context significantly increases co-occurrence)
        FALSE: ΔW(C) < 1 (context does not gate the connection)
        UNKNOWN: Cannot determine (no windows, context not in corpus, or Gas token)
    
    ΔW(C) = W(A∧B∧C) - W(A∧B) × W(C) / |W|
    
    STRICT: Uses ΔW >= 1 (W_unit) instead of > 0 to avoid noise.
    
    Gas Filter: Context C cannot be a Gas token (stopword).
    """
    if stats.n_windows == 0:
        return InferResult.UNKNOWN
    
    # Context must be in corpus
    if context not in stats.token_df:
        return InferResult.UNKNOWN
    
    # Gas filter: context C cannot be high-frequency stopword
    gas_threshold = int(stats.n_windows * GAS_DF_FRACTION)
    ctx_df = stats.token_df.get(context, 0)
    if ctx_df > gas_threshold:
        return InferResult.UNKNOWN  # Gas context cannot prove GATE
    
    # Count windows with all three
    w_abc = 0
    for window in stats.windows:
        if src in window and tgt in window and context in window:
            w_abc += 1
    
    # W(A∧B)
    w_ab = get_cooccur_weight(src, tgt, stats)
    
    # W(C)
    w_c = stats.token_df.get(context, 0)
    
    # Expected co-occurrence without gate effect
    expected = w_ab * w_c / stats.n_windows if stats.n_windows > 0 else 0
    
    # Gate active if context increases co-occurrence by at least W_unit=1
    delta_w = w_abc - expected
    if delta_w >= 1.0:
        return InferResult.TRUE
    else:
        return InferResult.FALSE


# =============================================================================
# VERIFICATION (3-valued)
# =============================================================================

def verify_path(
    src: str,
    tgt: str,
    overlay: OverlayGraph,
    max_hops: int = 3,
    max_edges: int = 1000,
) -> Tuple[VerifyResult, List[OverlayEdge]]:
    """
    Verify if σ-path exists between src and tgt (MYCELIUM v2.3 §4.1).
    
    Args:
        src: Source hash8
        tgt: Target hash8
        overlay: Overlay graph
        max_hops: Maximum path length
        max_edges: Maximum edges to examine (budget)
    
    Returns:
        (result, path) where:
        - result: PROVEN if path found, UNKNOWN if budget exhausted
        - path: List of edges forming the path (empty if not found)
    
    Note: UNPROVEN is only returned if we can prove non-existence,
    which requires complete graph enumeration. Budget exhaustion → UNKNOWN.
    """
    if src == tgt:
        return (VerifyResult.PROVEN, [])
    
    # BFS with budget
    visited: Set[str] = {src}
    queue: List[Tuple[str, List[OverlayEdge]]] = [(src, [])]
    edges_examined = 0
    
    while queue and edges_examined < max_edges:
        current, path = queue.pop(0)
        
        if len(path) >= max_hops:
            continue
        
        for edge in overlay.edges.get(current, []):
            edges_examined += 1
            
            # Only provable edges (anchor + live state valid)
            if not edge.is_provable():
                continue
            
            if edge.tgt == tgt:
                return (VerifyResult.PROVEN, path + [edge])
            
            if edge.tgt not in visited:
                visited.add(edge.tgt)
                queue.append((edge.tgt, path + [edge]))
            
            if edges_examined >= max_edges:
                break
    
    # Budget exhausted or no path found
    # Return UNKNOWN because we can't prove non-existence without full enumeration
    return (VerifyResult.UNKNOWN, [])


# =============================================================================
# HIGH-LEVEL INTEGRATION
# =============================================================================

def relocate_and_verify(
    edge: OverlayEdge,
    base_path: Optional[Path] = None,
) -> Tuple[Optional[str], int]:
    """
    Relocate edge and update anchor_state (MYCELIUM v2.3 §2.2).
    
    Returns:
        (content, new_anchor_state)
    """
    if not edge.doc or not edge.line or not edge.ctx_hash:
        return (None, OverlayEdge.DECOHERENT)
    
    content, new_line, anchor_state = reread_context_window(
        doc=edge.doc,
        line=edge.line,
        ctx_hash=edge.ctx_hash,
        base_path=base_path,
    )
    
    # Update edge if relocated (caller should persist if needed)
    if anchor_state == OverlayEdge.RELOCATED and new_line != edge.line:
        edge.line = new_line
    
    edge.anchor_state = anchor_state
    return (content, anchor_state)
