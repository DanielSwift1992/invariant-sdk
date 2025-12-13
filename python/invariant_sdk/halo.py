"""
halo.py — Halo client (Semantic DNS).

Client-side helper to fetch and cache Halos from a read-only Halo server.
Uses only stdlib (urllib) to avoid new dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .merkle import get_token_hash_bytes


def hash8_hex_merkle(token: str) -> str:
    """Canonical address (v3+): first 8 bytes of Merkle(token)."""
    return get_token_hash_bytes(token)[:8].hex()


def hash8_hex(token: str) -> str:
    """hash8 address for a token (v3+ Merkle)."""
    return hash8_hex_merkle(token)


@dataclass
class HaloClient:
    """
    Read-only Halo client with permanent local cache.

    Parameters:
      base_url: Halo server root, e.g. "http://127.0.0.1:8080"
      crystal_id: optional expected crystal_id; if None, fetched lazily.
      cache_dir: directory for halo cache (default ~/.invariant/halo)
      timeout_s: network timeout in seconds.
    """

    base_url: str
    crystal_id: Optional[str] = None
    cache_dir: Optional[Path] = None
    timeout_s: float = 2.0
    word_begin_markers: tuple[str, ...] = ("Ġ", "▁")

    def __post_init__(self):
        # Cache is L3 convenience only; must not break physics if unavailable.
        self._cache_disabled = False
        if self.cache_dir is None:
            self.cache_dir = Path.home() / ".invariant" / "halo"
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Fall back to no-cache mode if home dir is locked down.
            self._cache_disabled = True
            self.cache_dir = None
        self._version: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_meta(self) -> Dict:
        """Fetch /v1/meta once and cache crystal_id."""
        meta = self._get_json("/v1/meta")
        if meta and not self.crystal_id:
            self.crystal_id = meta.get("crystal_id")
        if meta:
            try:
                self._version = int(meta.get("version") or 1)
            except Exception:
                self._version = 1
            if self._version < 3:
                raise ValueError(f"Halo requires v3+ server/crystal, got version={self._version}")
        return meta or {}

    def get_halo_page(
        self,
        hash8: str,
        *,
        cursor: int = 0,
        limit: int = 500,
        min_abs_weight: float = 0.0,
    ) -> Dict:
        """
        Fetch a single page for a public node address.

        Returns the server response object:
          {crystal_id, hash8, exists, collision_count, meta, neighbors}
        """
        hash8 = hash8.lower()
        q = f"?cursor={int(cursor)}&limit={int(limit)}&min_abs_weight={float(min_abs_weight)}"
        resp = self._get_json(f"/v1/halo/{hash8}{q}") or {}
        if resp and not self.crystal_id:
            self.crystal_id = resp.get("crystal_id")
        return resp

    def get_halo_pages(
        self,
        hashes: Iterable[str],
        *,
        cursor: int = 0,
        limit: int = 500,
        min_abs_weight: float = 0.0,
        cursors: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Dict]:
        """
        Batch halo lookup (paginated).

        Returns mapping: hash8 -> {exists, collision_count, meta, neighbors}.
        """
        # Updated server expects nodes as objects: [{"hash8": "...", "cursor": 0}]
        nodes = []
        for h in hashes:
            h = h.lower()
            c = int(cursors.get(h, cursor)) if cursors else int(cursor)
            nodes.append({"hash8": h, "cursor": c})

        payload = {"nodes": nodes, "limit": int(limit), "min_abs_weight": float(min_abs_weight)}
        resp = self._post_json("/v1/halo", payload) or {}
        if resp and not self.crystal_id:
            self.crystal_id = resp.get("crystal_id")
        return resp.get("results") or {}

    def get_halo_meta(self, hash8: str) -> Dict:
        """Meta-only lookup (exists + degree_total) using limit=0."""
        return self.get_halo_page(hash8, cursor=0, limit=0, min_abs_weight=0.0)

    def get_labels_batch(self, hashes: Iterable[str]) -> Dict[str, Optional[str]]:
        """
        Batch reverse lookup: hash8 -> token string (human-readable label).
        
        Uses /v1/labels endpoint added in halo_server v3.
        Falls back to showing hash prefix if endpoint unavailable.
        """
        hashes_list = list(hashes)
        if not hashes_list:
            return {}
        
        try:
            payload = {"hashes": hashes_list}
            resp = self._post_json("/v1/labels", payload) or {}
            labels = resp.get("labels") or {}
            # Decode BPE tokens (remove Ġ prefix)
            cleaned = {}
            for h8, token in labels.items():
                if token:
                    cleaned[h8] = token.replace("Ġ", "").replace("ġ", "").strip()
                else:
                    cleaned[h8] = None
            return cleaned
        except Exception:
            # Fallback: return hash prefixes
            return {h: None for h in hashes_list}

    def get_halo_exact(
        self,
        hash8: str,
        *,
        min_abs_weight: float = 0.0,
        page_limit: int = 4096,
    ) -> Dict:
        """
        Fetch the full (untruncated) Halo for an address by paging until complete.

        This is required for exact set-physics (Mass, Jaccard, exact interference).
        """
        hash8 = hash8.lower()
        if min_abs_weight == 0.0:
            cached = self._read_cache(hash8)
            if cached is not None:
                return cached

        first = self.get_halo_page(hash8, cursor=0, limit=0, min_abs_weight=0.0) or {}
        if not first.get("exists"):
            out = {
                "crystal_id": first.get("crystal_id") or self.crystal_id,
                "hash8": hash8,
                "exists": False,
                "collision_count": 0,
                "meta": {"degree_total": 0, "cursor": 0, "returned": 0, "truncated": False, "next_cursor": None},
                "neighbors": [],
            }
            if min_abs_weight == 0.0:
                self._write_cache(hash8, out)
            return out

        cursor = 0
        neighbors: List[Dict] = []
        degree_total = int((first.get("meta") or {}).get("degree_total") or 0)
        collision_count = int(first.get("collision_count") or 1)

        while True:
            page = self.get_halo_page(
                hash8,
                cursor=cursor,
                limit=int(page_limit),
                min_abs_weight=float(min_abs_weight),
            )
            meta = page.get("meta") or {}
            neighbors.extend(page.get("neighbors") or [])
            next_cursor = meta.get("next_cursor")
            if next_cursor is None:
                break
            cursor = int(next_cursor)

        out = {
            "crystal_id": first.get("crystal_id") or self.crystal_id,
            "hash8": hash8,
            "exists": True,
            "collision_count": collision_count,
            "meta": {"degree_total": degree_total, "cursor": 0, "returned": len(neighbors), "truncated": False, "next_cursor": None},
            "neighbors": neighbors,
        }
        if min_abs_weight == 0.0:
            self._write_cache(hash8, out)
        return out

    def resolve_word(self, word: str) -> Optional[str]:
        """
        Resolve a plain surface word to a public atom address.

        Rule (deterministic):
          prefer a word-begin token (e.g. Ġword / ▁word) if it exists, else plain word.
        """
        if self._version is None:
            self.get_meta()
        candidates = self.candidates_for_word(word, markers=self.word_begin_markers)
        meta = self.get_halo_pages(candidates, limit=0)
        for h in candidates:
            if (meta.get(h) or {}).get("exists"):
                return h
        return None

    # ------------------------------------------------------------------
    # Molecules / Trajectories
    # ------------------------------------------------------------------

    def resolve_concept(
        self,
        text: str,
        *,
        min_abs_weight: float = 0.0,
    ) -> List[str]:
        """
        Resolve a concept (word or short phrase) to a list of public atomic hash8s.

        Physics:
        - Atoms are existing public tokens (single hash8).
        - If a surface word is not an atom, we deterministically decompose it
          into the smallest MDL set of atoms whose concatenation matches the word.
        - No BPE-specific assumptions are baked into the server.

        Returns:
          [] if no public decomposition exists.
        """
        if self._version is None:
            self.get_meta()
        # Split on whitespace: each part is its own trajectory element.
        words = [w.strip().lower() for w in text.split() if w.strip()]
        atoms: List[str] = []
        for w in words:
            h = self.resolve_word(w)
            if h:
                atoms.append(h)
                continue
            atoms.extend(self._resolve_molecule_word(w))
        return atoms

    def get_concept_halo(
        self,
        text: str,
        mode: str,
        *,
        min_abs_weight: float = 0.0,
        page_limit: int = 4096,
        blend_op: str = "mean",
    ) -> List[Dict]:
        """
        Get a Halo for a concept (atom or molecule).

        - Single atom: returns its halo directly.
        - Multiple atoms:
            - mode="interference": constructive interference halo
              (intersection via multiplication of weights; TEXT_TOPOLOGY_SPEC §20.1).
            - mode="blend": virtual-token blend halo (union via additive superposition;
              TEXT_TOPOLOGY_SPEC §20.2).

        No hidden defaults: `mode` must be explicit.
        """
        atoms = self.resolve_concept(text, min_abs_weight=min_abs_weight)
        if not atoms:
            return []
        mode = (mode or "").lower().strip()

        per_atom: List[List[Dict]] = []
        for h in atoms:
            exact = self.get_halo_exact(h, min_abs_weight=min_abs_weight, page_limit=page_limit)
            per_atom.append(exact.get("neighbors") or [])
        if len(per_atom) == 1:
            return per_atom[0]
        if mode == "interference":
            return self._interference_halo(per_atom)
        if mode == "blend":
            return self._blend_halo(per_atom, op=blend_op)
        raise ValueError(f"Unknown mode: {mode!r} (expected 'interference' or 'blend')")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_molecule_word(self, word: str) -> List[str]:
        """
        Deterministically decompose a surface word into atoms.

        Steps:
          1) Enumerate all substrings.
          2) Keep those that resolve to public atoms.
          3) Find minimal-part coverings of the full word (MDL / compression).
          4) Break ties deterministically (lexicographic by hash8 trajectory).
        """
        w = word.strip().lower()
        if not w:
            return []

        L = len(w)

        # Collect candidates for all substrings.
        #
        # Token boundary rule:
        # - Only the first token of a word may carry a leading word-begin marker (Ġ/▁/...).
        # - Interior tokens must not.
        substr_to_cands: Dict[tuple, List[str]] = {}
        all_cands: List[str] = []
        for i in range(L):
            for j in range(i + 1, L + 1):
                sub = w[i:j]
                if i == 0:
                    cands = self.candidates_for_word(sub, markers=self.word_begin_markers)
                else:
                    # interior: no leading whitespace token
                    cands = [hash8_hex(sub)]
                substr_to_cands[(i, j)] = cands
                all_cands.extend(cands)

        # Batch meta lookup once (existence only).
        all_cands = list(dict.fromkeys([c.lower() for c in all_cands]))
        meta = self.get_halo_pages(all_cands, limit=0)

        # Build resolvable segments: (start, end, hash8)
        segments: Dict[int, List[tuple]] = {}
        for (i, j), cands in substr_to_cands.items():
            if i == 0:
                # Prefer any word-begin atom if present (in marker order), else plain.
                begin_candidates = cands[:-1]
                plain = cands[-1]
                chosen = None
                for begin in begin_candidates:
                    if (meta.get(begin) or {}).get("exists"):
                        chosen = begin
                        break
                if chosen is None and (meta.get(plain) or {}).get("exists"):
                    chosen = plain
                if chosen is not None:
                    segments.setdefault(i, []).append((j, chosen))
            else:
                h = cands[0]
                if (meta.get(h) or {}).get("exists"):
                    segments.setdefault(i, []).append((j, h))

        if not segments:
            return []

        # DP over positions (acyclic, increasing end): minimize parts, then lexicographic.
        best: List[Optional[List[str]]] = [None] * (L + 1)
        best[0] = []
        for pos in range(L):
            cur = best[pos]
            if cur is None:
                continue
            for end, h in segments.get(pos, []):
                cand = cur + [h]
                prev = best[end]
                if prev is None or len(cand) < len(prev) or (len(cand) == len(prev) and tuple(cand) < tuple(prev)):
                    best[end] = cand

        return best[L] or []

    @staticmethod
    def _interference_halo(per_atom_halos: List[List[Dict]]) -> List[Dict]:
        """Constructive interference halo (intersection with weight multiplication)."""
        if not per_atom_halos:
            return []
        maps = []
        for h in per_atom_halos:
            m = {nb["hash8"]: float(nb["weight"]) for nb in h if "hash8" in nb and "weight" in nb}
            maps.append(m)
        common = set(maps[0].keys())
        for m in maps[1:]:
            common &= set(m.keys())
        if not common:
            return []

        out = []
        for nb in common:
            w_prod = 1.0
            for m in maps:
                w_prod *= m[nb]
            out.append({"hash8": nb, "weight": w_prod})
        out.sort(key=lambda x: -abs(float(x["weight"])))
        return out

    @staticmethod
    def _blend_halo(per_atom_halos: List[List[Dict]], op: str = "mean") -> List[Dict]:
        """
        Virtual-token blend halo (union via additive superposition).

        op:
          - "mean": average weight over atoms (missing => 0)
          - "sum":  sum of weights over atoms (missing => 0)
          - "max":  max |weight| over atoms (keeps sign of max contributor)
        """
        if not per_atom_halos:
            return []
        op = (op or "mean").lower().strip()

        maps = []
        all_nodes = set()
        for h in per_atom_halos:
            m = {nb["hash8"]: float(nb["weight"]) for nb in h if "hash8" in nb and "weight" in nb}
            maps.append(m)
            all_nodes |= set(m.keys())

        out = []
        for nb in all_nodes:
            vals = [m.get(nb, 0.0) for m in maps]
            if op == "sum":
                w = float(sum(vals))
            elif op == "mean":
                w = float(sum(vals) / max(1, len(vals)))
            elif op == "max":
                w = float(max(vals, key=lambda x: abs(x)))
            else:
                raise ValueError(f"Unknown blend_op: {op!r} (expected 'mean', 'sum', 'max')")
            out.append({"hash8": nb, "weight": w})

        out.sort(key=lambda x: -abs(float(x["weight"])))
        return out

    @classmethod
    def _interference_strength(cls, per_atom_halos: List[List[Dict]]) -> float:
        """Scalar strength of interference halo (sum of |Π w_i|)."""
        halo = cls._interference_halo(per_atom_halos)
        return float(sum(abs(float(nb["weight"])) for nb in halo))

    @staticmethod
    def candidates_for_word(word: str, *, markers: tuple[str, ...] = ("Ġ", "▁")) -> List[str]:
        """
        Deterministic candidates matching BinaryCrystal prefixing.
        """
        w = word.strip().lower()
        toks = [m + w for m in markers if m] + [w]
        return [hash8_hex_merkle(t) for t in toks]

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_root(self) -> Path:
        if self._cache_disabled or self.cache_dir is None:
            return Path()  # dummy; callers must handle disabled mode
        if not self.crystal_id:
            # lazy pinning
            self.get_meta()
        cid = self.crystal_id or "unknown"
        root = self.cache_dir / cid
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._cache_disabled = True
            return Path()
        return root

    def _cache_path(self, hash8: str) -> Path:
        root = self._cache_root()
        return root / f"{hash8}.json"

    def _read_cache(self, hash8: str) -> Optional[Dict]:
        if self._cache_disabled or self.cache_dir is None:
            return None
        p = self._cache_path(hash8)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def _write_cache(self, hash8: str, payload: Dict):
        if self._cache_disabled or self.cache_dir is None:
            return
        p = self._cache_path(hash8)
        try:
            p.write_text(json.dumps(payload))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _get_json(self, path: str) -> Optional[Dict]:
        url = self.base_url.rstrip("/") + path
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _post_json(self, path: str, payload: Dict) -> Optional[Dict]:
        url = self.base_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None
