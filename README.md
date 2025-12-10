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
```

### Two Ways, Same Protocol (DocumentStructure)

**Way 1: Manual (full control)**

```python
from invariant_sdk.tools.agent import DocumentStructure

# Input data
text = "Module X depends on Library Y. Library Y has vulnerability."

# Create structure manually
structure = DocumentStructure(
    cuts=[32, 60],
    validation_quotes=["Library Y.", "vulnerability."],
    relations=["IMP"],
    symbols=[]
)

# Ingest
engine.ingest("doc1", text, structure)

# Query
engine.evolve()
results = engine.resonate("vulnerabilities")
```

**Way 2: Automatic (LLM does it)**

```python
from invariant_sdk.tools import StructuralAgent

# Input data
text = "Module X depends on Library Y. Library Y has vulnerability."

# LLM creates DocumentStructure automatically
agent = StructuralAgent(engine, llm=my_llm)
agent.digest("doc1", text)  # Triple validation

# Smart search
results = agent.search("impact of vulnerabilities")
```

**Same protocol, different creation method.**

## What Makes This Different

**1. LLM Output Validation**
- Catches hallucinations: if LLM says text ends at position 100, we verify the quote actually appears there
- Triple-check: numbers + text + logic must all align
- Invalid structures rejected before storage

**2. Hybrid Search (Vector + Graph)**
- Vector search finds semantic matches ("vulnerability" ≈ "security flaw")
- Graph search follows logical links (A→B, B→C implies A→C)
- Combined: find related concepts AND their logical relationships

**3. Adaptive Thresholds**
- No hardcoded similarity scores
- k-sigma calibration: system learns what "similar enough" means from your data
- Automatically filters noise without manual tuning

## API

| Method | Description |
|--------|-------------|
| `ingest(source, text, structure)` | Validated ingestion with triple validation |
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
