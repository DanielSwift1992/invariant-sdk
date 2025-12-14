# HALO SPEC — Semantic DNS (Ghost Edges)

**Layer:** L3 (Service / Projection)  
**Status:** NORMATIVE (protocol + payload shapes)  
**Depends on:** `SPEC_V3.md`, `INVARIANTS.md`, `.crystal` ABI  

---

## 0. Purpose

Produce the **effect of a Unified Crystal** without ingesting private text.

**Halo Node** is a read‑only projection over a frozen global `.crystal`:

- Input: a public **address** (`hash8`)
- Output: the frozen neighbor list (Halo) + **degree_total** (for Mass)

No text. No inference. No “smart resolve”. No adaptive behavior.

---

## 1. Invariants (Halo‑Specific)

This protocol is valid iff it respects:

- **I. Identity:** canonical identity is Merkle(L0). Truncations are only L3 addresses.
- **II. Closure:** edges are truth‑carriers (exist / not exist). Weights are conductivity only.
- **V. Separation:** Halo Node never runs Liquid inference (no LLM, no tokenization, no “meaning” ops).
- **No‑Compromise (derived):** any lossy truncation must be explicit (`truncated=true`) and never masquerade as the full neighborhood.

---

## 2. Identity vs Addressing

### 2.1 Canonical Identity

Canonical identity is the full 32‑byte Merkle SHA‑256:

- `hash32 = Merkle(structure)` (L0)

### 2.2 L3 Addresses (Index Keys)

Storage and APIs may use truncated prefixes **only as addresses**:

- `hash16`: first 16 bytes of `hash32`
- `hash8`: first 8 bytes of `hash32`

**Invariant:** `hash8`/`hash16` are not identity proofs; collisions are possible in principle.

**String encoding:** all `hash*` fields are lowercase hex of the raw bytes (no “0x” prefix).

Halo protocol is v3+ only (Merkle addressing).

---

## 3. Core Objects

### 3.1 Public vs Private Nodes

- **Public node:** token exists in the global Crystal → has an address.
- **Private node:** absent from global Crystal → never sent to Halo Node.

Halo Node must be safe to query with arbitrary addresses; it must never require client text.

### 3.2 Halo

For a public node `u`, Halo is its frozen neighborhood:

```
Halo(u) = [(v_i, w_i)]  where v_i ∈ N(u)
```

Where:
- `v_i` are neighbor public nodes (by address)
- `w_i` is the frozen signed edge weight (conductivity)

**Weights are not probabilities.** Path existence is truth (Closure); weights only rank/propagate signal.

### 3.3 Degree Total (Required for Mass)

Halo responses must expose:

- `degree_total(u) = |N(u)|` (in the stored Crystal, before any L3 filters)

This is required to compute Mass (INVARIANTS: Topological Mass):

```
Mass(u) = 1 / log(2 + degree_total(u))
```

Without `degree_total`, clients cannot classify Gas vs Solid deterministically.

### 3.4 Ghost Edges

Edges imported from Halo into local graphs are **Ghost Edges**:

- ring = `λ` (derived / overlay)
- provenance = `halo:<crystal_id>`

Ghost Edges may participate in ranking/search but must not overwrite local σ‑truth.

---

## 4. Halo Service API (Read‑Only)

Halo Node is a **static asset**:

- stateless
- deterministic (byte‑stable for the same `.crystal`)
- no randomness at runtime
- no adaptive policy (no “smart defaults” that change meaning)

### 4.1 `/v1/meta`

`GET /v1/meta`

Response:
```json
{
  "crystal_id": "qwen_full_v3:v3",
  "version": 3,
  "n_labels": 150000,
  "n_edges": 282619922,
  "threshold": 0.2627612352371216,
  "mean_mass": 0.2597428560256958
}
```

Clients must not mix Halos across different `crystal_id`.

### 4.2 Deterministic Ordering (Canonical Neighbor List)

Halo Node must return neighbors in a **canonical order** which is stable for a given `crystal_id`.

**Normative (runtime):**
- canonical order is the stored CSR row order in the `.crystal` (Halo Node must not re‑sort)
- `cursor` offsets are defined over this stored order

**Recommended (forge / build-time):**
- store each CSR row in descending `abs(weight)` so the first page is the strongest signal
- tie‑break may use a fixed deterministic key (e.g. `target_idx` ascending)

This keeps the server “dumb” (pure projection) while keeping pagination useful.

### 4.3 Single Lookup (Paginated, Exact‑Capable)

`GET /v1/halo/{hash8}`

Query params (L3 transport only; not physics):
- `cursor` (optional, default `0`): 0‑based offset in the canonical neighbor list
- `limit` (optional): max number of neighbors to return in this page
- `min_abs_weight` (optional, default `0.0`): drop neighbors with `abs(weight) < min_abs_weight`

**Important:** `min_abs_weight` is a projection knob; it must not change `degree_total`.
`limit` may be `0` to request **meta only** (existence/degree without payload).

Response:
```json
{
  "crystal_id": "qwen_full_v3:v3",
  "hash8": "e3b0c44298fc1c14",
  "exists": true,
  "collision_count": 1,
  "meta": {
    "degree_total": 15420,
    "cursor": 0,
    "returned": 500,
    "truncated": true,
    "next_cursor": 500
  },
  "neighbors": [
    {"hash8": "a1b2...", "weight": 0.73},
    {"hash8": "c3d4...", "weight": -0.61}
  ]
}
```

If `exists=false`, then:
- `meta.degree_total = 0`
- `neighbors = []`
- `truncated = false`

#### Collision Semantics (`hash8` is an address)

If `collision_count > 1`, the address corresponds to multiple canonical IDs.
Halo Node must return a deterministic **merge**:

- The neighbor set is the union of all underlying neighborhoods.
- If the same neighbor appears multiple times, keep the edge with maximal `abs(weight)` (preserving its sign).
- `meta.degree_total` refers to the merged unique neighbor count (before `min_abs_weight` and pagination).

### 4.4 Batch Lookup (k‑Anonymity, Paginated)

`POST /v1/halo`

Request:
```json
{
  "nodes": [
    {"hash8": "aaaaaaaaaaaaaaaa", "cursor": 0},
    {"hash8": "bbbbbbbbbbbbbbbb", "cursor": 0}
  ],
  "limit": 500,
  "min_abs_weight": 0.0
}
```

Response:
```json
{
  "crystal_id": "qwen_full_v3:v3",
  "results": {
    "aaaaaaaaaaaaaaaa": {
      "exists": true,
      "collision_count": 1,
      "meta": {"degree_total": 10, "cursor": 0, "returned": 10, "truncated": false, "next_cursor": null},
      "neighbors": [{"hash8": "....", "weight": 0.8}]
    },
    "bbbbbbbbbbbbbbbb": {
      "exists": false,
      "collision_count": 0,
      "meta": {"degree_total": 0, "cursor": 0, "returned": 0, "truncated": false, "next_cursor": null},
      "neighbors": []
    }
  }
}
```

Batching is a privacy mechanism: clients may add decoy addresses. Halo Node must treat all nodes independently (stateless).

---

## 5. Exact vs Projected Use (No‑Compromise Rule)

Halo is defined over the **full** neighborhood in the stored Crystal.

- If `truncated=true`, the client is holding a **projection**, not the full set `N(u)`.
- Any algorithm that depends on the full set (Mass, Jaccard connectivity, exact interference) must fetch pages until `truncated=false`.

This is the explicit boundary between **exact physics** (Ice) and **projection/transport** (L3).

---

## 6. Atoms and Molecules (Client‑Side Only)

### 6.1 Atom

An **Atom** is one public token address (`hash8`). Halo Node serves halos for atoms only.

### 6.2 Molecule (Trajectory)

A **Molecule** is a deterministic composition of multiple atoms (a short trajectory of `hash8` values).

Molecules are client‑side only. Halo Node never creates new node IDs and never tokenizes client text.

### 6.3 MDL Decomposition (No‑Compromise)

Given a surface word `w`, find a covering by public atoms that minimizes the number of parts (Compression / Energy invariant).

Determinism requirements:
- decomposition must be purely algorithmic (no RNG, no thresholds)
- if multiple decompositions have equal minimum parts, use a fixed tie‑break rule (e.g., lexicographic by `hash8` sequence)

Whitespace marker tokens (BPE) are model‑relative; clients must enforce:
- only the first atom of a surface word may be a “word‑begin” token (e.g., `Ġ...`, `▁...`)
- interior atoms must be non‑word‑begin tokens

---

## 7. Molecule Halo Composition (Client‑Side Physics)

Given halos for atoms `u_1..u_n`, clients may apply explicit operators:

1) **Interference (AND / Intersection)**  
   Keep only neighbors that appear in **all** halos:
   \[
   w(v) = \prod_i w_i(v)
   \]

2) **Blend (OR / Superposition)**  
   Take the union of neighbors:
   \[
   w(v) = \frac{1}{n}\sum_i w_i(v)
   \]

**No hidden defaults:** operator choice must be explicit at the client API boundary.

---

## 8. Build‑Time Determinism (Crystal Mining Requirement)

Halo Node’s determinism is only as strong as the determinism of the `.crystal` forge.

Normative requirement for v3+ mining:
- given identical model weights + vocab + forge parameters, output `.crystal` must be byte‑stable
- no RNG/seed may influence which edges exist
- any statistical thresholds (e.g., k‑sigma) must be computed via a deterministic measurement protocol

How that protocol is implemented is part of the mining pipeline spec, not Halo runtime.

---

## Annex A: Local Overlay Format (σ-Facts)

**Status:** NORMATIVE

### A.1 Purpose

Local Overlay files (`.overlay.jsonl`) store **σ-facts** (observations from user documents) that layer on top of the global **α-crystal** (axioms).

This implements **Separation Law (Invariant V):** Crystal (α / read-only) is physically separated from Overlay (σ / read-write).

### A.2 File Format

JSON Lines format. Each line is a valid JSON object with an `op` field.

**Location Convention:**
- User-global: `~/.invariant/global.overlay.jsonl`
- Project-local: `./.invariant/overlay.jsonl`

SDK loads overlays in cascade order (later overrides earlier).

### A.3 Operations

#### `add` — Add Local Edge

```json
{"op": "add", "src": "<hash8>", "tgt": "<hash8>", "w": 1.0, "ring": "sigma", "doc": "readme.md", "line": 42, "ctx_hash": "a1b2c3d4"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | ✓ | `"add"` |
| `src` | string | ✓ | Source node hash8 |
| `tgt` | string | ✓ | Target node hash8 |
| `w` | float | ✓ | Edge weight (typically 1.0 for facts) |
| `ring` | string | — | Ring classification: `"sigma"` (default), `"lambda"`, `"eta"` |
| `doc` | string | — | Source document path (provenance) |
| `line` | int | — | Line number (1-indexed) in source document |
| `ctx_hash` | string | — | Semantic checksum of anchor window (8 hex chars) for integrity verification. See **Anchor Integrity Protocol** in INVARIANTS.md |

#### `sub` — Suppress Global Edge

Hides an edge from global crystal results.

```json
{"op": "sub", "src": "<hash8>", "tgt": "<hash8>", "reason": "context_is_code"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | ✓ | `"sub"` |
| `src` | string | ✓ | Source node hash8 |
| `tgt` | string | ✓ | Target node hash8 |
| `reason` | string | — | Human-readable reason |

#### `def` — Define Label

Associates a custom human label with a hash8.

```json
{"op": "def", "node": "<hash8>", "label": "MyProject", "type": "anchor"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `op` | string | ✓ | `"def"` |
| `node` | string | ✓ | Node hash8 |
| `label` | string | ✓ | Human-readable label |
| `type` | string | — | Node classification (`"anchor"`, `"link"`) |

### A.4 Hierarchy Law (Conflict Resolution)

When an edge exists in both global crystal and local overlay:

$$\text{Local } \sigma \text{ beats Global } \alpha$$

| Source | Ring | Priority |
|--------|------|----------|
| Local overlay (σ) | Observation | **HIGH** |
| Global crystal (α) | Axiom | LOW |

**Rationale:** User's observation of their own data is truth. Global statistics are context.

### A.5 Example Overlay File

```jsonl
# Project knowledge overlay
{"op": "def", "node": "032fb9ee6fb5620d", "label": "MyProject"}
{"op": "add", "src": "032fb9ee6fb5620d", "tgt": "8a4e7f3b21c9d0e5", "w": 1.0, "ring": "sigma", "doc": "README.md", "line": 15, "ctx_hash": "e5f6a7b8"}
{"op": "sub", "src": "8a4e7f3b21c9d0e5", "tgt": "coffee_related_hash", "reason": "java_is_language_not_coffee"}
```

### A.6 Git Integration

Overlay files are **text-based and human-readable** by design:
- Can be committed to version control
- Changes are visible in standard diff tools
- Enables "Git for Knowledge" workflow

---

*"The Crystal is the map. The Overlay is your notes on the map."*

