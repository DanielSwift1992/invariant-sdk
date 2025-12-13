#!/usr/bin/env python3
"""
cli.py — Invariant CLI (inv)

Commands:
  inv ingest <path>   Ingest documents into local overlay
  inv ask <query>     Ask a question using global + local knowledge
  inv info            Show current overlay status
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Set

# Import SDK components
try:
    from .halo import hash8_hex
    from .overlay import OverlayGraph, find_overlays
    from .physics import HaloPhysics
except ImportError:
    # Running as standalone script
    from invariant_sdk.halo import hash8_hex
    from invariant_sdk.overlay import OverlayGraph, find_overlays
    from invariant_sdk.physics import HaloPhysics


# Default server
DEFAULT_SERVER = "http://165.22.145.158:8080"


def tokenize_simple(text: str) -> List[str]:
    """
    Simple tokenizer: extract words, lowercase.
    
    Uses word boundaries, filters short words.
    """
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return words


def tokenize_with_positions(text: str) -> List[tuple]:
    """
    Tokenize text with position tracking for provenance.
    
    Returns: [(word, line, char_start, char_end), ...]
    
    Theory: Store coordinates, not content (MDL/Invariant III).
    """
    results = []
    lines = text.split('\n')
    char_offset = 0
    
    for line_num, line in enumerate(lines, 1):
        for match in re.finditer(r'\b[a-zA-Z]{3,}\b', line):
            word = match.group().lower()
            char_start = char_offset + match.start()
            char_end = char_offset + match.end()
            results.append((word, line_num, char_start, char_end))
        char_offset += len(line) + 1  # +1 for newline
    
    return results


def compute_ctx_hash(tokens_with_pos: List[tuple], anchor_idx: int, k: int = 2) -> str:
    """
    Compute semantic checksum for anchor (Anchor Integrity Protocol).
    
    Args:
        tokens_with_pos: List of (word, line, char_start, char_end)
        anchor_idx: Index of anchor word in the list
        k: Window size (±k words around anchor)
    
    Returns:
        8 hex characters of SHA-256 hash of normalized anchor window
    
    Theory: This is the "DNA" of the σ-fact. If context changes, hash changes.
    Used for drift detection and self-healing.
    """
    import hashlib
    
    # Get window [anchor_idx - k, anchor_idx + k]
    start = max(0, anchor_idx - k)
    end = min(len(tokens_with_pos), anchor_idx + k + 1)
    
    # Extract words
    window_words = [tokens_with_pos[i][0] for i in range(start, end)]
    
    # Normalize: lowercase, join with single space
    normalized = ' '.join(w.lower() for w in window_words)
    
    # Hash and truncate to 8 hex chars
    h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
    
    return h


def get_anchors(
    client: HaloPhysics, 
    words: List[str], 
    min_mass: float = None,
    max_words: int = 100,  # Limit to avoid timeout
) -> List[tuple]:
    """
    Find anchor words (solid phase) from a list.
    
    Optimized: deduplicates words and limits batch size.
    
    Returns: [(word, hash8, mass), ...]
    """
    import math
    
    if min_mass is None:
        min_mass = client.mean_mass
    
    # Deduplicate and limit
    unique_words = list(dict.fromkeys(words))[:max_words]
    
    anchors = []
    checked: Set[str] = set()
    
    # Build candidates
    candidates_map = {}  # hash8 -> word
    for word in unique_words:
        h8 = hash8_hex(f"Ġ{word}")
        if h8 not in checked:
            candidates_map[h8] = word
            checked.add(h8)
    
    # Batch query (use get_halo_pages if available, else single queries with limit)
    # For now, do limited single queries
    for h8, word in list(candidates_map.items())[:50]:  # Limit to 50 checks
        try:
            result = client._client.get_halo_page(h8, limit=1)
            neighbors = result.get("neighbors", [])
            degree = result.get("meta", {}).get("degree_total", len(neighbors))
            
            if len(neighbors) > 0 or degree > 0:
                # Use neighbor count as proxy for degree if not provided
                if degree == 0:
                    degree = len(neighbors) * 100  # Approximate
                mass = 1.0 / math.log(2 + degree)
                if mass >= min_mass:
                    anchors.append((word, h8, mass))
        except Exception:
            continue
    
    return anchors


def cmd_ingest(args: argparse.Namespace) -> int:
    """Ingest documents into local overlay."""
    input_path = Path(args.path)
    output_path = Path(args.output) if args.output else Path("./.invariant/overlay.jsonl")
    
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        return 1
    
    print(f"Invariant Ingest")
    print(f"  Source: {input_path}")
    print(f"  Output: {output_path}")
    print()
    
    # Connect to server
    print("Connecting to crystal server...")
    client = HaloPhysics(args.server, auto_discover_overlay=False)
    print(f"  Crystal: {client.crystal_id}")
    print(f"  Mean mass: {client.mean_mass:.4f}")
    print()
    
    # Collect files
    if input_path.is_file():
        files = [input_path]
    else:
        files = list(input_path.rglob("*.txt")) + list(input_path.rglob("*.md"))
    
    print(f"Found {len(files)} files to process")
    print()
    
    # Create overlay
    overlay = OverlayGraph()
    total_edges = 0
    
    for file_path in files:
        print(f"Processing: {file_path.name}")
        
        try:
            text = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"  Error reading: {e}")
            continue
        
        # Tokenize WITH positions for provenance tracking (Invariant III: MDL)
        tokens_with_pos = tokenize_with_positions(text)
        
        # Get list of words to check for anchors
        words = [w for w, _, _, _ in tokens_with_pos]
        anchors = get_anchors(client, words)
        anchor_words = {w for w, _, _ in anchors}
        
        # Filter to only anchor tokens (with their positions)
        anchor_tokens = [(w, line, cs, ce) for w, line, cs, ce in tokens_with_pos 
                         if w in anchor_words]
        
        print(f"  Words: {len(words)}, Anchors: {len(anchor_tokens)}")
        
        if len(anchor_tokens) < 2:
            print(f"  Skipping (too few anchors)")
            continue
        
        # Create edges between consecutive anchors with provenance coordinates
        doc_name = str(file_path.relative_to(input_path) if input_path.is_dir() else file_path.name)
        
        # Build index map: anchor token index -> position in tokens_with_pos
        anchor_indices = []
        for i, (w, _, _, _) in enumerate(tokens_with_pos):
            if w in anchor_words:
                anchor_indices.append(i)
        
        for i in range(len(anchor_indices) - 1):
            src_idx = anchor_indices[i]
            tgt_idx = anchor_indices[i + 1]
            
            src_word, src_line, _, _ = tokens_with_pos[src_idx]
            tgt_word, tgt_line, _, _ = tokens_with_pos[tgt_idx]
            
            src_hash = hash8_hex(f"Ġ{src_word}")
            tgt_hash = hash8_hex(f"Ġ{tgt_word}")
            
            # Compute ctx_hash for target anchor (hash of word ±2 words)
            ctx_hash = compute_ctx_hash(tokens_with_pos, tgt_idx, k=2)
            
            overlay.add_edge(
                src_hash, tgt_hash, 
                weight=1.0, 
                doc=doc_name,
                ring="sigma",
                line=tgt_line,  # Line of target anchor
                ctx_hash=ctx_hash
            )
            overlay.define_label(src_hash, src_word)
            overlay.define_label(tgt_hash, tgt_word)
            total_edges += 1
        
        print(f"  Added {len(anchor_indices) - 1} edges with integrity")
    
    # Save overlay
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path)
    
    print()
    print(f"Done!")
    print(f"  Total edges: {total_edges}")
    print(f"  Total labels: {len(overlay.labels)}")
    print(f"  Overlay saved: {output_path}")
    
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify if an assertion has σ-proof (documentary evidence)."""
    subject = args.subject
    obj = args.object
    
    print("Invariant Verify (σ-proof check)")
    print(f"  Subject: \"{subject}\"")
    print(f"  Object: \"{obj}\"")
    print()
    
    # Connect to server with overlay
    client = HaloPhysics(args.server, auto_discover_overlay=True)
    
    if not client._overlay:
        print("❌ No overlay found.")
        print()
        print("Create one with: inv ingest ./docs")
        return 1
    
    print(f"  Crystal: {client.crystal_id}")
    print(f"  Overlay: {client._overlay.n_edges} edges, {len(client._overlay.labels)} labels")
    print()
    
    # Run verification
    result = client.verify(subject, obj)
    
    # Pretty-print result
    print("=" * 50)
    if result.proven:
        print("✓ σ-PROVEN")
        print("=" * 50)
        print()
        print("This assertion is supported by documentary evidence.")
        print()
        if result.sources:
            print("Sources:")
            for i, src in enumerate(result.sources, 1):
                print(f"  {i}. {src}")
        print()
        if result.path:
            print("Path (with provenance):")
            for edge in result.path:
                tgt_label = client._overlay.get_label(edge.get("hash8", "")) or edge.get("hash8", "")[:8]
                doc = edge.get("doc", "?")
                line = edge.get("line", "?")
                snippet = edge.get("snippet", "")
                
                print(f"  → {tgt_label}")
                print(f"      📄 {doc}:{line}")
                if snippet:
                    print(f"      \"{snippet}\"")
    else:
        print("❌ UNVERIFIED (η = hypothesis)")
        print("=" * 50)
        print()
        print(result.message)
        print()
        print("Subject hash:", result.subject_hash[:12] + "...")
        print("Object hash:", result.object_hash[:12] + "...")
        print()
        
        # Show what global crystal knows (context, not proof)
        try:
            concept = client.resolve(subject)
            if concept.halo:
                print("Global crystal context (α, not proof):")
                for n in concept.halo[:5]:
                    token = n.get("token", n.get("hash8", "")[:8])
                    weight = n.get("weight", 0)
                    print(f"  - {token} (w={weight:.2f})")
        except Exception:
            pass
        
        print()
        print("To add documentary evidence: inv ingest <path-to-documents>")
    
    # Show conflicts if any
    if result.conflicts:
        print()
        print("⚠️  CONFLICTS DETECTED:")
        for conflict in result.conflicts:
            e1 = conflict.get("edge1", {})
            e2 = conflict.get("edge2", {})
            print(f"  - {e1.get('doc', '?')} says {e1.get('weight', 0)}")
            print(f"    vs {e2.get('doc', '?')} says {e2.get('weight', 0)}")
    
    print()
    return 0 if result.proven else 2


def cmd_ask(args: argparse.Namespace) -> int:
    """Ask a question using global + local knowledge."""
    query = args.query
    
    print(f"Invariant Ask")
    print(f"  Query: \"{query}\"")
    print()
    
    # Connect to server with overlay
    client = HaloPhysics(args.server, auto_discover_overlay=True)
    
    overlay_info = ""
    if client._overlay:
        overlay_info = f" + overlay({client._overlay.n_edges} local edges)"
    
    print(f"  Crystal: {client.crystal_id}{overlay_info}")
    print()
    
    # Tokenize query
    words = tokenize_simple(query)
    if not words:
        print("No recognizable words in query")
        return 1
    
    # Find anchors in query
    anchors = get_anchors(client, words, min_mass=0)  # Lower threshold for query
    
    if not anchors:
        print("No anchors found for query words")
        return 1
    
    print(f"Query anchors: {', '.join(w for w, _, _ in anchors)}")
    print()
    
    # Resolve each anchor and find intersection
    concepts = []
    for word, h8, mass in anchors[:3]:  # Limit to 3 for speed
        concept = client.resolve(word)
        if concept.halo:
            concepts.append((word, concept))
            print(f"  {word}: {len(concept.halo)} neighbors (mass={mass:.3f})")
    
    if not concepts:
        print("Could not resolve query")
        return 1
    
    print()
    
    # If multiple concepts, focus (intersect) them
    if len(concepts) > 1:
        print("Focusing (intersection)...")
        result = concepts[0][1]
        for word, concept in concepts[1:]:
            result = result.focus(concept)
        print(f"  Result: {len(result.halo)} shared neighbors")
    else:
        result = concepts[0][1]
    
    print()
    print("=" * 50)
    print("Results:")
    print("=" * 50)
    
    if not result.halo:
        print("No connections found.")
        print()
        print("Try expanding context with: inv ask --mode blend \"...\"")
        return 0
    
    # Show top results with labels from overlay
    for i, neighbor in enumerate(result.halo[:10]):
        h8 = neighbor.get("hash8", "")
        weight = neighbor.get("weight", 0)
        
        # Check for custom label
        label = h8[:12]
        if client._overlay:
            custom_label = client._overlay.get_label(h8)
            if custom_label:
                label = f"{custom_label} ({h8[:8]})"
        
        # Check if this is a local edge
        source = "global"
        if client._overlay and any(
            e.tgt == h8 for edges in client._overlay.edges.values() for e in edges
        ):
            source = "LOCAL"
        
        print(f"  {i+1}. {label} (w={weight:.3f}) [{source}]")
    
    print()
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show current overlay status."""
    print("Invariant Info")
    print()
    
    # Find overlays
    overlays = find_overlays()
    
    if not overlays:
        print("No overlay files found.")
        print()
        print("Create one with: inv ingest ./docs")
        return 0
    
    print(f"Found {len(overlays)} overlay file(s):")
    print()
    
    for path in overlays:
        overlay = OverlayGraph.load(path)
        print(f"  {path}")
        print(f"    Edges: {overlay.n_edges}")
        print(f"    Labels: {len(overlay.labels)}")
        print(f"    Suppressed: {len(overlay.suppressed)}")
        print()
    
    # Show combined stats
    if len(overlays) > 1:
        combined = OverlayGraph.load_cascade(overlays)
        print("Combined:")
        print(f"  Total edges: {combined.n_edges}")
        print(f"  Total labels: {len(combined.labels)}")
    
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """Start web UI server."""
    from .ui import run_ui
    
    overlay_path = Path(args.overlay) if args.overlay else None
    run_ui(port=args.port, server=args.server, overlay_path=overlay_path)
    return 0


def main() -> int:
    """Main entry point for inv CLI."""
    parser = argparse.ArgumentParser(
        prog="inv",
        description="Invariant CLI — Structural Knowledge Management"
    )
    parser.add_argument(
        "--server", "-s",
        default=DEFAULT_SERVER,
        help=f"Halo server URL (default: {DEFAULT_SERVER})"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # ingest command
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest documents into local overlay"
    )
    ingest_parser.add_argument(
        "path",
        help="Path to file or directory to ingest"
    )
    ingest_parser.add_argument(
        "--output", "-o",
        help="Output overlay file (default: ./.invariant/overlay.jsonl)"
    )
    
    # ask command
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask a question using global + local knowledge"
    )
    ask_parser.add_argument(
        "query",
        help="Question to ask"
    )
    ask_parser.add_argument(
        "--mode", "-m",
        choices=["focus", "blend"],
        default="focus",
        help="Composition mode for multi-word queries"
    )
    
    # info command
    subparsers.add_parser(
        "info",
        help="Show current overlay status"
    )
    
    # verify command
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify if an assertion has σ-proof (documentary evidence)"
    )
    verify_parser.add_argument(
        "subject",
        help="Subject of assertion (e.g., 'contract')"
    )
    verify_parser.add_argument(
        "object",
        help="Object of assertion (e.g., '5 years')"
    )
    
    # ui command
    ui_parser = subparsers.add_parser(
        "ui",
        help="Start web UI server"
    )
    ui_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="HTTP port (default: 8080)"
    )
    ui_parser.add_argument(
        "--overlay", "-o",
        help="Overlay file path"
    )
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        return cmd_ingest(args)
    elif args.command == "ask":
        return cmd_ask(args)
    elif args.command == "info":
        return cmd_info(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "ui":
        return cmd_ui(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

