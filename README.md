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

# Ingest (Conservation Law validated)
engine.ingest("doc1", ["Module X depends on Library Y", "Library Y has vulnerability"])

# Link (Rust-accelerated)
engine.crystallize()

# Infer (Transitivity)
engine.evolve()  # Derives: X → vulnerable

# Search
results = engine.resonate("affected modules", mode=SearchMode.BINOCULAR)
```

## Automated Ingestion (with LLM)

```python
from invariant_sdk.tools import StructuralAgent

def my_llm(prompt: str) -> str:
    return openai.chat(...).content

agent = StructuralAgent(engine, llm=my_llm)
agent.digest("doc1", raw_text)  # 2 LLM calls: segment + classify
```

## For AI Agents

```python
from invariant_sdk import get_prompt

system_prompt = get_prompt()  # Full operator prompt
api_only = get_prompt("api")  # Just API reference
```

## API

| Method | Description |
|--------|-------------|
| `ingest(source, data, cuts)` | Validated ingestion |
| `observe(source, text)` | Quick ingestion (auto-split) |
| `resonate(query, mode)` | Search with interference |
| `crystallize(threshold)` | Auto-link similar blocks |
| `evolve()` | Run logical inference |
| `forget(source)` | Delete document |
| `get_prompt()` | Operator prompt for AI agents |

## Structure

```
invariant-sdk/
├── kernel/          # Rust (crystallize_all, crystallize_hnsw)
├── python/          # Python SDK
│   └── invariant_sdk/
│       ├── engine.py       # Core engine
│       ├── tools/          # StructuralAgent
│       └── operator_prompt.md
├── Makefile
└── install.sh
```

## License

MIT
