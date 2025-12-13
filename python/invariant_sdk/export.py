"""
export.py — Graph Export Utilities

Export Concept halos to various formats for visualization and analysis.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .physics import Concept


def to_dot(
    concept: "Concept",
    output: Path,
    *,
    max_nodes: int = 50,
    min_weight: float = 0.0,
    title: Optional[str] = None,
) -> Path:
    """
    Export Concept halo to Graphviz .dot format.
    
    Args:
        concept: Resolved Concept with halo
        output: Output path for .dot file
        max_nodes: Maximum neighbors to include
        min_weight: Minimum |weight| to include
        title: Optional graph title
    
    Returns:
        Path to created .dot file
    """
    output = Path(output)
    
    # Filter and limit
    neighbors = [
        n for n in concept.halo 
        if abs(n.get("weight", 0)) >= min_weight
    ][:max_nodes]
    
    # Determine center label
    if concept.atoms:
        center = concept.atoms[0][:8] + "..."
    else:
        center = "query"
    
    lines = [
        "digraph G {",
        "  rankdir=LR;",
        '  node [shape=box, style=rounded, fontname="Arial"];',
        '  edge [fontsize=8, fontname="Arial"];',
        "",
        f'  // Center: {len(concept.atoms)} atoms, {len(concept.halo)} neighbors',
        f'  // Phase: {concept.phase}, Mass: {concept.mass:.3f}',
        "",
    ]
    
    if title:
        lines.append(f'  label="{title}";')
        lines.append('  labelloc="t";')
        lines.append("")
    
    # Center node
    center_style = 'style="filled,rounded"' if concept.phase == "solid" else 'style=rounded'
    lines.append(f'  "center" [label="{center}" {center_style} fillcolor="#e3f2fd"];')
    lines.append("")
    
    # Neighbor nodes with weight-based coloring
    for n in neighbors:
        token = n.get("token", n.get("hash8", "?")[:8])
        token_safe = re.sub(r'[^a-zA-Z0-9_]', '_', str(token))
        weight = n.get("weight", 0)
        
        # Color by weight
        if abs(weight) >= 0.7:
            color = "#4caf50"  # Green - core
            width = "2"
        elif abs(weight) >= 0.5:
            color = "#2196f3"  # Blue - near
            width = "1.5"
        else:
            color = "#9e9e9e"  # Gray - far
            width = "1"
        
        # Edge direction based on sign
        edge_style = "solid" if weight >= 0 else "dashed"
        
        lines.append(f'  "{token_safe}" [label="{token}"];')
        lines.append(
            f'  "center" -> "{token_safe}" '
            f'[label="{weight:.2f}" color="{color}" penwidth={width} style={edge_style}];'
        )
    
    lines.append("}")
    
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def to_summary(concept: "Concept", max_per_orbit: int = 5) -> str:
    """
    Generate text summary of Concept orbits.
    
    Returns formatted string showing:
      - Core neighbors (|w| ≥ 0.7)
      - Near neighbors (0.5 ≤ |w| < 0.7)
      - Far neighbors (|w| < 0.5)
    """
    lines = [
        f"Concept: {len(concept.atoms)} atoms, {len(concept.halo)} neighbors",
        f"Phase: {concept.phase.upper()}, Mass: {concept.mass:.4f}",
        "",
    ]
    
    core = concept.core[:max_per_orbit]
    near = concept.near[:max_per_orbit]
    far = concept.far[:max_per_orbit]
    
    if core:
        tokens = [f"{n.get('token', '?')} ({n['weight']:.2f})" for n in core]
        lines.append(f"Core [0.7+]: {', '.join(tokens)}")
    
    if near:
        tokens = [f"{n.get('token', '?')} ({n['weight']:.2f})" for n in near]
        lines.append(f"Near [0.5-0.7]: {', '.join(tokens)}")
    
    if far:
        tokens = [f"{n.get('token', '?')} ({n['weight']:.2f})" for n in far]
        lines.append(f"Far [<0.5]: {', '.join(tokens)}")
    
    return "\n".join(lines)
