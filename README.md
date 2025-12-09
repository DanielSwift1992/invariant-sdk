# Invariant SDK

**Deterministic Knowledge Engine** — Connect your data, not just store it.

## Install

```bash
make install
```

Prerequisites: Python 3.9+, Rust ([rustup.rs](https://rustup.rs))

## Quick Start

```python
from invariant_sdk import InvariantEngine, SearchMode

engine = InvariantEngine("./data")

# Ingest
engine.observe("doc1", "Module X depends on Library Y")
engine.observe("doc2", "Library Y has a vulnerability")

# Link (Rust-accelerated)
engine.crystallize(method="hnsw")

# Infer
engine.evolve()  # Derives: X → vulnerable

# Search
results = engine.resonate("affected modules", mode=SearchMode.BINOCULAR)
```

## API

| Method | Description |
|--------|-------------|
| `observe(source, text)` | Ingest document |
| `crystallize(method)` | Auto-link similar blocks |
| `evolve()` | Run logical inference |
| `resonate(query, mode)` | Search with interference |
| `forget(source)` | Delete document |

## Structure

```
invariant-sdk/
├── kernel/          # Rust (crystallize_all, crystallize_hnsw)
├── python/          # Python SDK
├── Makefile
└── install.sh
```
