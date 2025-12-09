# Invariant SDK

**Deterministic Knowledge Engine** — Connect your data, not just store it.

## Install

```bash
make install
```

Prerequisites: Python 3.9+, Rust ([rustup.rs](https://rustup.rs))

## Quick Start

```python
from invariant_sdk import InvariantEngine

engine = InvariantEngine("./data")

# Ingest with LLM-provided cuts (Conservation Law validated)
text = "Module X depends on Library Y. Library Y has vulnerability."
engine.ingest("doc1", text, cuts=[32])  # LLM returns positions only

# Or use StructuralAgent for full automation
from invariant_sdk.tools import StructuralAgent

agent = StructuralAgent(engine, llm=my_llm)
agent.digest("doc2", raw_text)  # 2 LLM calls: segment + classify

# Smart Search (with Query Decomposition)
results = agent.search("impact of vulnerabilities on X")
# Decomposes -> ["impact of vulnerabilities", "X"] -> Intersection

# Infer (Transitivity)
engine.evolve()  # Derives: X → vulnerable

# Search
results = engine.resonate("affected modules")
```

## L0 Principles

1. **Conservation Law**: Every character from source appears in exactly one block
2. **Membrane Law**: Invalid data is rejected, never stored
3. **LLM as Discriminator**: LLM returns positions/labels, not text

## API

| Method | Description |
|--------|-------------|
| `ingest(source, text, cuts)` | Validated ingestion (cuts from LLM) |
| `observe(source, text)` | Quick ingestion (auto-split) |
| `resonate(query, mode)` | Search with interference |
| `crystallize(threshold)` | Auto-link similar blocks |
| `evolve()` | Run logical inference |
| `forget(source)` | Delete document |
| `get_prompt()` | Operator prompt for AI agents |

## For AI Agents

```python
from invariant_sdk import get_prompt

system_prompt = get_prompt()  # Full operator prompt
```

## Structure

```
invariant-sdk/
├── kernel/          # Rust (crystallize_hnsw)
├── python/
│   └── invariant_sdk/
│       ├── engine.py           # Core engine
│       ├── tools/agent.py      # StructuralAgent
│       └── operator_prompt.md  # AI agent instructions
└── Makefile
```

## License

MIT
