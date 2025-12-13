"""
sdk/crystal.py — Crystal Graph for Topological Semantic Search

Uses mined LLM weights (crystal graph) for pure topology-based search,
replacing vector embeddings with graph traversal.
"""
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Set


# ============================================================================
# BPE DECODER
# ============================================================================

def _bytes_to_unicode():
    """GPT-2/Qwen byte encoder mapping (256 bytes → Unicode)."""
    bs = list(range(ord("!"), ord("~")+1)) + \
         list(range(ord("¡"), ord("¬")+1)) + \
         list(range(ord("®"), ord("ÿ")+1))
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8 + n)
            n += 1
    cs = [chr(n) for n in cs]
    return dict(zip(cs, bs))

_UNICODE_TO_BYTE = _bytes_to_unicode()


def decode_bpe_token(token: str) -> str:
    """Decode a byte-level BPE token to readable UTF-8 string."""
    if token.startswith('Ġ'):
        prefix = ' '
        token = token[1:]
    else:
        prefix = ''
    
    try:
        byte_values = []
        for char in token:
            if char in _UNICODE_TO_BYTE:
                byte_values.append(_UNICODE_TO_BYTE[char])
            else:
                byte_values.extend(char.encode('utf-8'))
        decoded = bytes(byte_values).decode('utf-8', errors='replace')
        return prefix + decoded
    except Exception:
        return prefix + token


# ============================================================================
# CRYSTAL GRAPH
# ============================================================================

class CrystalGraph:
    """
    Topological semantic graph mined from LLM weights.
    
    Replaces vector embeddings with pure graph-based search.
    """
    
    def __init__(self, tank_path: Path):
        """Load crystal graph from .tank file."""
        self.path = Path(tank_path)
        
        with open(self.path, encoding='utf-8') as f:
            tank = json.load(f)
        
        self.edges = tank.get("edges", [])
        self.labels = tank.get("labels", {})
        self.metadata = tank.get("metadata", {})
        
        # Build indexes
        self._build_indexes()
    
    def _build_indexes(self):
        """Build adjacency lists and label lookup for fast traversal."""
        import math
        
        # Adjacency: source → [(target, relation, weight)]
        self.outgoing: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        self.incoming: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        
        for e in self.edges:
            self.outgoing[e["source"]].append((e["target"], e["relation"], e["weight"]))
            self.incoming[e["target"]].append((e["source"], e["relation"], e["weight"]))
        
        # Label → hash lookup (for query matching)
        self.label_to_hash: Dict[str, str] = {}
        self.decoded_labels: Dict[str, str] = {}
        
        for h, label in self.labels.items():
            # Store decoded label
            decoded = decode_bpe_token(label).strip().lower()
            self.decoded_labels[h] = decoded
            
            # Multiple index entries for flexible matching
            self.label_to_hash[decoded] = h
            
            # Also index without space
            clean = label.replace("Ġ", "").lower()
            if clean != decoded:
                self.label_to_hash[clean] = h
        
        # Compute Topological Mass (Shannon Information Content)
        # 
        # From Information Theory: I(w) = -log P(w)
        # In graph: P(w) ∝ degree(w) (probability of random walk)
        # Therefore: Mass(w) = 1 / log(2 + degree)
        #
        # High degree = frequent = low information = GAS (transparent)
        # Low degree = rare = high information = SOLID (anchor)
        #
        self._node_mass: Dict[str, float] = {}
        total_mass = 0.0
        
        for h in self.labels:
            degree = len(self.outgoing.get(h, [])) + len(self.incoming.get(h, []))
            mass = 1.0 / math.log(2 + degree)  # log(2+d) to avoid log(1)=0
            self._node_mass[h] = mass
            total_mass += mass
        
        # Mean mass = threshold for "solid" vs "gas" (derived from graph statistics)
        self.mean_mass = total_mass / len(self.labels) if self.labels else 0.5
    
    def get_label(self, h: str) -> str:
        """Get decoded label for a hash."""
        if h in self.decoded_labels:
            return self.decoded_labels[h]
        if h in self.labels:
            return decode_bpe_token(self.labels[h]).strip()
        return h[:8]
    
    def find_nodes(self, query: str, max_matches: int = 10) -> List[str]:
        """
        Find node hashes matching a query string.
        
        Returns list of matching node hashes, prioritized by match quality:
        1. Exact match
        2. Prefix match
        3. Contains match
        """
        q = query.lower().strip()
        if not q:
            return []
        
        exact = []
        prefix = []
        contains = []
        
        for label, h in self.label_to_hash.items():
            if label == q:
                exact.append(h)
            elif label.startswith(q):
                prefix.append(h)
            elif q in label:
                contains.append(h)
        
        # Combine: exact first, then prefix, then contains
        result = exact + prefix + contains
        return result[:max_matches]
    
    def expand(self, 
               seed_nodes: List[str], 
               depth: int = 2,
               relations: Optional[Set[str]] = None) -> Dict[str, float]:
        """
        Expand from seed nodes using BFS.
        
        Returns dict of {node_hash: relevance_score}.
        Score decays with distance from seed.
        """
        if relations is None:
            relations = {"IMP", "DEF"}  # Default: implications and definitions
        
        visited: Dict[str, float] = {}
        
        # Initialize seeds with score 1.0
        frontier = [(node, 1.0, 0) for node in seed_nodes]
        
        while frontier:
            node, score, current_depth = frontier.pop(0)
            
            # Skip if already visited with higher score
            if node in visited and visited[node] >= score:
                continue
            
            visited[node] = score
            
            # Stop if max depth reached
            if current_depth >= depth:
                continue
            
            # Expand outgoing edges
            for target, rel, weight in self.outgoing.get(node, []):
                if rel in relations and target not in visited:
                    # Score decays with distance, weighted by edge weight
                    new_score = score * weight * 0.5
                    if new_score > 0.01:  # Threshold to avoid tiny scores
                        frontier.append((target, new_score, current_depth + 1))
        
        return visited
    
    def search(self, query: str, top_k: int = 20, depth: int = 2) -> List[Tuple[str, float]]:
        """
        Topological search: find related concepts for a query.
        
        Returns list of (node_hash, relevance_score) pairs.
        """
        # 1. Find seed nodes matching query
        seeds = self.find_nodes(query, max_matches=5)
        
        if not seeds:
            # Try word-by-word matching for multi-word queries
            words = query.lower().split()
            for word in words:
                if len(word) > 2:  # Skip short words
                    seeds.extend(self.find_nodes(word, max_matches=2))
        
        if not seeds:
            return []
        
        # 2. Expand from seeds
        expanded = self.expand(seeds, depth=depth)
        
        # 3. Sort by score
        results = [(h, score) for h, score in expanded.items()]
        results.sort(key=lambda x: -x[1])
        
        return results[:top_k]
    
    def get_related_words(self, query: str, top_k: int = 10) -> List[str]:
        """Get human-readable related words for a query."""
        results = self.search(query, top_k=top_k)
        words = []
        for h, score in results:
            label = self.get_label(h)
            if label and len(label) > 1:  # Skip single chars
                words.append(label)
        return words
    
    # ========================================================================
    # SECOND-ORDER TOPOLOGY (L0-Compliant Closure at Depth 2)
    # ========================================================================
    
    def _get_all_neighbors(self, word: str) -> Set[str]:
        """
        Get all neighbors for a word, aggregating from all matching BPE tokens.
        
        This handles BPE fragmentation: 'programming' might match 'program', 'ming'.
        We union all their neighbors.
        """
        neighbors = set()
        
        # Find all tokens matching this word
        nodes = self.find_nodes(word, max_matches=10)
        
        for h in nodes:
            # Add outgoing neighbors
            for n, _, _ in self.outgoing.get(h, []):
                neighbors.add(n)
            # Add incoming neighbors  
            for n, _, _ in self.incoming.get(h, []):
                neighbors.add(n)
        
        return neighbors
    
    def connection_strength(self, word1: str, word2: str) -> float:
        """
        Pure Topological Connection Metric (0.0 - 1.0).
        
        Implements Invariant II (Closure) at depth 2:
        1. Direct Edge (First Order): A → B
        2. Shared Neighbors (Second Order): ∃C: A → C ∧ C → B
        
        Works at WORD level, aggregating all matching BPE tokens.
        """
        # Get all matching hashes
        hashes1 = self.find_nodes(word1, max_matches=5)
        hashes2 = self.find_nodes(word2, max_matches=5)
        
        if not hashes1 or not hashes2:
            return 0.0
        
        # 1. First Order: Check direct edges between any pair
        for h1 in hashes1:
            for h2 in hashes2:
                if h1 == h2:
                    return 1.0  # Same token
                for t, _, w in self.outgoing.get(h1, []):
                    if t == h2:
                        return w
                for t, _, w in self.outgoing.get(h2, []):
                    if t == h1:
                        return w
        
        # 2. Second Order: Aggregate neighbors from all matching tokens
        neighbors_a = self._get_all_neighbors(word1)
        neighbors_b = self._get_all_neighbors(word2)
        
        if not neighbors_a or not neighbors_b:
            return 0.0
        
        # Jaccard similarity on neighbor sets
        common = neighbors_a & neighbors_b
        
        if not common:
            return 0.0
        
        union_size = len(neighbors_a | neighbors_b)
        return len(common) / union_size
    
    def get_word_mass(self, word: str) -> float:
        """
        Get Topological Mass of a word.
        
        Mass = 1 / log(2 + degree)
        Heavy words (low degree) have high mass → solid anchors
        Light words (high degree) have low mass → gas, transparent
        """
        nodes = self.find_nodes(word, max_matches=1)
        if not nodes:
            return 0.0  # Unknown word = no mass
        
        h = nodes[0]
        return self._node_mass.get(h, 0.0)
    
    def smart_split(self, text: str) -> List[str]:
        """
        Pure Mathematical Topological Segmentation.
        
        Theory (L0-compliant):
        - Text is a trajectory through semantic manifold
        - Only "solid" nodes (mass > mean_mass) serve as anchors
        - "Gas" nodes (high degree, low mass) are transparent
        - Cut occurs where Connectivity = 0 (topological disconnect between solid anchors)
        
        No thresholds, no heuristics — pure physics.
        """
        words = text.split()
        if len(words) <= 1:
            return [text]
        
        # Step 1: Identify HEAVY anchors only (solid nodes, not gas)
        anchors = []  # [(word_index, clean_word)]
        for i, word in enumerate(words):
            clean = word.lower().strip('.,!?;:"\'()[]{}')
            if not clean:
                continue
            
            # Only include if word has mass > mean (it's "solid")
            mass = self.get_word_mass(clean)
            if mass > self.mean_mass:
                anchors.append((i, clean))
        
        if len(anchors) < 2:
            return [text]
        
        # Step 2: Compute connectivity profile for each anchor pair
        bonds = []
        for j in range(len(anchors) - 1):
            idx1, word1 = anchors[j]
            idx2, word2 = anchors[j + 1]
            strength = self.connection_strength(word1, word2)
            bonds.append((idx1, idx2, strength))
        
        # Step 3: Find topological disconnects (Connectivity = 0)
        # Mathematical criterion: cut where there's NO path in the manifold
        cut_points = []
        
        for j, (idx1, idx2, bond) in enumerate(bonds):
            # Pure mathematical criterion: ZERO connectivity = disconnect
            if bond == 0.0:
                # Cut at the midpoint of the vacuum between anchors
                mid_point = (idx1 + idx2) // 2 + 1
                cut_points.append(mid_point)
        
        if not cut_points:
            return [text]  # Fully connected — no cuts
        
        # Step 4: Apply cuts
        segments = []
        prev = 0
        for cut in cut_points:
            segment = ' '.join(words[prev:cut]).strip()
            if segment:
                segments.append(segment)
            prev = cut
        
        # Final segment
        final = ' '.join(words[prev:]).strip()
        if final:
            segments.append(final)
        
        return segments if segments else [text]


# ============================================================================
# ZERO-START PROXY CLASSES
# ============================================================================

class _IdxToTokenProxy:
    """Dict-like proxy for idx→token lookup via vocab index."""
    
    def __init__(self, crystal):
        self._crystal = crystal
    
    def __getitem__(self, idx: int) -> str:
        token = self._crystal._get_token_by_idx(idx)
        if token is None:
            raise KeyError(idx)
        return token
    
    def get(self, idx: int, default=None) -> str:
        token = self._crystal._get_token_by_idx(idx)
        return token if token is not None else default
    
    def __contains__(self, idx: int) -> bool:
        return 0 <= idx < self._crystal.n_labels
    
    def __len__(self) -> int:
        return self._crystal.n_labels


class _TokenToIdxProxy:
    """Dict-like proxy for token→idx lookup via vocab index."""
    
    def __init__(self, crystal):
        self._crystal = crystal
    
    def __getitem__(self, token: str) -> int:
        idx = self._crystal._get_idx_by_token(token)
        if idx < 0:
            raise KeyError(token)
        return idx
    
    def get(self, token: str, default=None) -> int:
        idx = self._crystal._get_idx_by_token(token)
        return idx if idx >= 0 else default
    
    def __contains__(self, token: str) -> bool:
        return self._crystal._get_idx_by_token(token) >= 0
    
    def __len__(self) -> int:
        return self._crystal.n_labels


# ============================================================================
# BINARY CRYSTAL (mmap + CSR Index for O(1) access)
# ============================================================================

class BinaryCrystal:
    """
    Zero-copy binary crystal reader using mmap + CSR index.
    
    RAM usage: ~50MB (index only) vs 26GB for loading all edges.
    Access: O(1) per node lookup.
    
    File format:
      .crystal - binary edges file
      .index   - CSR offset index (auto-built if missing)
    """
    
    def __init__(self, crystal_path: Path):
        import struct
        import mmap
        import numpy as np
        
        self.path = Path(crystal_path)
        self.index_path = self.path.with_suffix('.index')
        self.vocab_idx_path = self.path.with_suffix('.vocab.idx')
        
        # Open crystal file with mmap
        self.file = open(self.path, 'rb')
        self.mm = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        
        # Read header
        self.mm.seek(0)
        magic = self.mm.read(4)
        if magic != b'CRYS':
            raise ValueError(f"Invalid magic: {magic}")
        
        self.version = struct.unpack('<I', self.mm.read(4))[0]
        if self.version < 3:
            raise ValueError(f"Unsupported crystal version: {self.version} (v3+ required)")
        self.n_labels = struct.unpack('<I', self.mm.read(4))[0]
        self.n_edges = struct.unpack('<I', self.mm.read(4))[0]
        self.threshold = struct.unpack('<f', self.mm.read(4))[0]

        # Header size and frozen mean_mass (v3+)
        self._header_size = 24
        self.mean_mass = struct.unpack('<f', self.mm.read(4))[0]
        
        # Try Zero-Start with vocab index (INSTANT)
        if self.vocab_idx_path.exists():
            self._load_vocab_index()
            self._use_vocab_index = True
            print(f"  Zero-Start: {self.n_labels:,} labels via vocab index")
        else:
            # Fallback: slow parsing
            self._use_vocab_index = False
            self._fallback_load_labels(struct)
        
        # Load CSR index for edges
        self.offsets = None
        if self.index_path.exists():
            self._load_index()
        
        # mean_mass is frozen in the v3 header (no legacy heuristics).
    
    def _load_vocab_index(self):
        """Load vocab index for O(1)/O(log N) token access."""
        import struct
        import numpy as np
        
        with open(self.vocab_idx_path, 'rb') as f:
            magic = f.read(4)
            if magic != b'VIDX':
                raise ValueError(f"Invalid vocab index magic: {magic}")
            
            n_labels = struct.unpack('<I', f.read(4))[0]
            self.edge_section_offset = struct.unpack('<Q', f.read(8))[0]
            
            # ID Table marker
            marker = f.read(4)
            if marker != b'IDTB':
                raise ValueError(f"Expected IDTB, got {marker}")
            
            # Read ID table as numpy array (offset, length pairs)
            # Each entry: 8 bytes offset + 4 bytes length = 12 bytes
            id_table_bytes = f.read(n_labels * 12)
            self._id_table = np.frombuffer(id_table_bytes, dtype=[
                ('offset', '<u8'), ('length', '<u4')
            ])
            
            # Hash Table marker
            marker = f.read(4)
            if marker != b'HTBL':
                raise ValueError(f"Expected HTBL, got {marker}")
            
            # Read hash table as numpy array (hash, id pairs)
            # Each entry: 8 bytes hash + 4 bytes id = 12 bytes
            hash_table_bytes = f.read(n_labels * 12)
            self._hash_table = np.frombuffer(hash_table_bytes, dtype=[
                ('hash', '<u8'), ('id', '<u4')
            ])
        
        # Empty dicts for compatibility (will be populated on demand)
        self.labels = {}
        self.decoded_labels = {}
        self.label_to_hash = {}
        self._token_cache = {}  # LRU-like cache for frequently accessed tokens
    
    def _fallback_load_labels(self, struct):
        """Fallback: parse all labels (slow, for when vocab.idx doesn't exist)."""
        print(f"  Fallback: parsing {self.n_labels:,} labels...")
        
        self.labels = {}
        self.decoded_labels = {}
        self.label_to_hash = {}
        self.idx_to_token = {}
        self.token_to_idx = {}
        
        self.mm.seek(self._header_size)  # After header
        
        for idx in range(self.n_labels):
            h = self.mm.read(16)
            h_hex = h.hex()
            token_len = struct.unpack('<H', self.mm.read(2))[0]
            token = self.mm.read(token_len).decode('utf-8')
            
            self.idx_to_token[idx] = token
            self.token_to_idx[token] = idx
            self.labels[h_hex] = token
            
            decoded = decode_bpe_token(token).strip().lower()
            self.decoded_labels[h_hex] = decoded
            self.label_to_hash[decoded] = h_hex
        
        self.edge_section_offset = self.mm.tell()
        self._use_vocab_index = False
    
    @property
    def idx_to_token(self) -> Dict[int, str]:
        """Get token by ID. O(1) with vocab index."""
        if hasattr(self, '_idx_to_token_dict'):
            return self._idx_to_token_dict
        # Return proxy object for zero-start mode
        return _IdxToTokenProxy(self)
    
    @idx_to_token.setter
    def idx_to_token(self, value):
        self._idx_to_token_dict = value
    
    @property
    def token_to_idx(self) -> Dict[str, int]:
        """Get ID by token. O(log N) with vocab index."""
        if hasattr(self, '_token_to_idx_dict'):
            return self._token_to_idx_dict
        # Return proxy object for zero-start mode
        return _TokenToIdxProxy(self)
    
    @token_to_idx.setter  
    def token_to_idx(self, value):
        self._token_to_idx_dict = value
    
    def _get_token_by_idx(self, idx: int) -> str:
        """Read token from crystal file by ID. O(1)."""
        if idx < 0 or idx >= self.n_labels:
            return None
        
        # Check cache
        if idx in self._token_cache:
            return self._token_cache[idx]
        
        # Read from file via offset table
        offset = int(self._id_table[idx]['offset'])
        length = int(self._id_table[idx]['length'])
        
        self.mm.seek(offset)
        token = self.mm.read(length).decode('utf-8')
        
        # Cache (limit size)
        if len(self._token_cache) < 10000:
            self._token_cache[idx] = token
        
        return token
    
    def _get_idx_by_token(self, token: str) -> int:
        """Find ID by token via binary search. O(log N)."""
        import struct
        import numpy as np
        
        from .merkle import get_token_hash_bytes

        h_int = struct.unpack('<Q', get_token_hash_bytes(token)[:8])[0]
        
        # Binary search in sorted hash table
        hashes = self._hash_table['hash']
        idx = np.searchsorted(hashes, h_int)
        
        # Check for match (may need to handle collisions)
        if idx < len(hashes) and hashes[idx] == h_int:
            return int(self._hash_table[idx]['id'])
        
        return -1  # Not found
    
    def _parse_labels_and_cache(self, struct):
        """Parse labels from binary and save to cache."""
        import pickle
        
        print(f"  Parsing {self.n_labels:,} labels (first run, will cache)...")
        
        self.labels: Dict[str, str] = {}
        self.decoded_labels: Dict[str, str] = {}
        self.label_to_hash: Dict[str, str] = {}
        self.idx_to_token: Dict[int, str] = {}
        self.token_to_idx: Dict[str, int] = {}
        
        # Seek to labels section (after header)
        self.mm.seek(self._header_size)
        
        for idx in range(self.n_labels):
            h = self.mm.read(16)
            h_hex = h.hex()
            token_len = struct.unpack('<H', self.mm.read(2))[0]
            token = self.mm.read(token_len).decode('utf-8')
            
            self.idx_to_token[idx] = token
            self.token_to_idx[token] = idx
            self.labels[h_hex] = token
            
            decoded = decode_bpe_token(token).strip().lower()
            self.decoded_labels[h_hex] = decoded
            self.label_to_hash[decoded] = h_hex
        
        self.edge_section_offset = self.mm.tell()
        
        # Save cache
        try:
            cache = {
                'idx_to_token': self.idx_to_token,
                'token_to_idx': self.token_to_idx,
                'labels': self.labels,
                'decoded_labels': self.decoded_labels,
                'label_to_hash': self.label_to_hash,
                'edge_section_offset': self.edge_section_offset,
            }
            with open(self.cache_path, 'wb') as f:
                pickle.dump(cache, f)
            print(f"  Saved labels cache to {self.cache_path.name}")
        except Exception as e:
            print(f"  Warning: Could not save cache: {e}")
    
    def _load_index(self):
        """Load CSR index for O(1) access."""
        import struct
        import numpy as np
        
        with open(self.index_path, 'rb') as f:
            magic = f.read(4)
            if magic != b'CIDX':
                return
            
            n_nodes = struct.unpack('<I', f.read(4))[0]
            edge_offset = struct.unpack('<Q', f.read(8))[0]
            self.offsets = np.fromfile(f, dtype=np.uint64, count=n_nodes + 1)
    
    def close(self):
        """Close mmap and file."""
        if self.mm:
            self.mm.close()
        if self.file:
            self.file.close()
    
    def find_nodes(self, query: str, max_matches: int = 10) -> List[str]:
        """Find node hashes matching query."""
        q = query.lower().strip()
        if not q:
            return []
        
        results = []
        for label, h in self.label_to_hash.items():
            if q in label:
                results.append(h)
                if len(results) >= max_matches:
                    break
        return results
    
    def get_label(self, h: str) -> str:
        """Get decoded label for hash."""
        return self.decoded_labels.get(h, h[:8])
    
    def _get_raw_edges(self, idx: int) -> List[Tuple[int, float]]:
        """Get edges for token index using mmap."""
        import struct
        import numpy as np
        
        if self.offsets is None or idx >= len(self.offsets) - 1:
            return []
        
        start = int(self.offsets[idx])
        end = int(self.offsets[idx + 1])
        
        if start >= end:
            return []
        
        edges = []
        self.mm.seek(start)
        n_edges = (end - start) // 10
        
        for _ in range(n_edges):
            data = self.mm.read(10)
            if len(data) < 10:
                break
            src, tgt = struct.unpack('<II', data[:8])
            weight = np.frombuffer(data[8:10], dtype=np.float16)[0]
            if src == idx:
                edges.append((tgt, float(weight)))
        
        return edges
    
    def get_related_words(self, query: str, top_k: int = 10) -> List[str]:
        """Get related words via direct edges (sorted by weight)."""
        # Find starting tokens
        words = query.lower().split()
        all_edges = []
        start_indices = set()
        
        for word in words:
            for prefix in ['Ġ', '']:
                token = prefix + word
                if token in self.token_to_idx:
                    idx = self.token_to_idx[token]
                    start_indices.add(idx)
                    # Get edges for this token
                    edges = self._get_raw_edges(idx)
                    for tgt, weight in edges:
                        if tgt not in start_indices:
                            all_edges.append((tgt, weight, idx))
                    break
        
        if not all_edges:
            return []
        
        # Sort by weight, deduplicate
        all_edges.sort(key=lambda x: -x[1])
        seen = set()
        results = []
        
        for tgt, weight, src in all_edges:
            if tgt in seen:
                continue
            seen.add(tgt)
            
            token = self.idx_to_token.get(tgt)
            if token:
                decoded = decode_bpe_token(token).strip()
                if decoded and len(decoded) > 1:
                    results.append(decoded)
                    if len(results) >= top_k:
                        break
        
        return results
    
    def _get_mass(self, idx: int) -> float:
        """Get Shannon Information mass of token."""
        import math
        
        if self.offsets is None or idx >= len(self.offsets) - 1:
            return 0.5
        
        start = int(self.offsets[idx])
        end = int(self.offsets[idx + 1])
        degree = (end - start) // 10
        return 1.0 / math.log(2 + degree)
    
    def get_word_mass(self, word: str) -> float:
        """Get mass for a word (for smart_split compatibility)."""
        for prefix in ['Ġ', '']:
            token = prefix + word.lower()
            if token in self.token_to_idx:
                return self._get_mass(self.token_to_idx[token])
        return 0.0
    
    def get_word_degree(self, word: str) -> int:
        """
        Get degree (number of edges) for a word.
        
        Handles BPE token prefixes internally.
        """
        for prefix in ['Ġ', '']:
            token = prefix + word.lower()
            if token in self.token_to_idx:
                idx = self.token_to_idx[token]
                if self.offsets is not None and idx < len(self.offsets) - 1:
                    start = int(self.offsets[idx])
                    end = int(self.offsets[idx + 1])
                    return (end - start) // 10  # 10 bytes per edge
        return 0
    
    def get_word_neighbors(self, word: str, limit: int = 30) -> list:
        """
        Get neighbor tokens for a word.
        
        Returns: List of (neighbor_word, weight) tuples.
        Handles BPE prefixes internally.
        """
        for prefix in ['Ġ', '']:
            token = prefix + word.lower()
            if token in self.token_to_idx:
                idx = self.token_to_idx[token]
                edges = self._get_raw_edges(idx)
                results = []
                for n, w in edges[:limit]:
                    neighbor_token = self.idx_to_token.get(n, '')
                    # Decode BPE: remove Ġ prefix
                    clean = neighbor_token.replace('Ġ', '').replace('ġ', '')
                    if clean and len(clean) > 0:
                        results.append((clean, w))
                return results
        return []
    
    def connection_strength(self, word1: str, word2: str) -> float:
        """Compute Jaccard similarity between neighbor sets."""
        idx1 = self.token_to_idx.get('Ġ' + word1.lower()) or self.token_to_idx.get(word1.lower())
        idx2 = self.token_to_idx.get('Ġ' + word2.lower()) or self.token_to_idx.get(word2.lower())
        
        if idx1 is None or idx2 is None:
            return 0.0
        
        neighbors_a = set(n for n, _ in self._get_raw_edges(idx1))
        neighbors_b = set(n for n, _ in self._get_raw_edges(idx2))
        
        if not neighbors_a or not neighbors_b:
            return 0.0
        
        intersection = len(neighbors_a & neighbors_b)
        union = len(neighbors_a | neighbors_b)
        
        return intersection / union if union > 0 else 0.0
    
    def smart_split(self, text: str) -> List[str]:
        """Topological segmentation using mass-based anchors."""
        words = text.split()
        if len(words) <= 1:
            return [text]
        
        # Find solid anchors
        anchors = []
        for i, word in enumerate(words):
            clean = ''.join(c for c in word.lower() if c.isalnum())
            if not clean:
                continue
            mass = self.get_word_mass(clean)
            if mass > self.mean_mass:
                anchors.append((i, clean))
        
        if len(anchors) < 2:
            return [text]
        
        # Find topological disconnects (Connectivity = 0)
        cut_points = []
        for j in range(len(anchors) - 1):
            idx1, word1 = anchors[j]
            idx2, word2 = anchors[j + 1]
            strength = self.connection_strength(word1, word2)

            if strength == 0.0:
                mid_point = (idx1 + idx2) // 2 + 1
                cut_points.append(mid_point)
        
        if not cut_points:
            return [text]
        
        # Apply cuts
        segments = []
        prev = 0
        for cut in cut_points:
            segment = ' '.join(words[prev:cut]).strip()
            if segment:
                segments.append(segment)
            prev = cut
        
        final = ' '.join(words[prev:]).strip()
        if final:
            segments.append(final)
        
        return segments if segments else [text]


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def load_crystal(path: Path) -> 'CrystalGraph':
    """
    Load crystal graph, auto-detecting format:
    - .crystal → BinaryCrystal (mmap, O(1) access)
    - .tank    → CrystalGraph (JSON, loads all into RAM)
    """
    path = Path(path)
    
    if path.suffix == '.crystal':
        return BinaryCrystal(path)
    else:
        return CrystalGraph(path)
