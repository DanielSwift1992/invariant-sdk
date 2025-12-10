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
from invariant_sdk.tools import StructuralAgent

engine = InvariantEngine("./data")

# Provide your LLM function
def my_llm(prompt: str) -> str:
    # Your LLM API call here
    return response

agent = StructuralAgent(engine, llm=my_llm)
```

### Digest Text (Streaming Protocol)

```python
text = """
Module X depends on Library Y. 
Library Y has a critical vulnerability.
Therefore Module X is at risk.
"""

# LLM extracts structure via quotes
# chunk_size: adjust for your LLM's context window (default 8000)
blocks = agent.digest("security_report", text, chunk_size=4000)
print(f"Created {blocks} blocks")

# Run inference
engine.evolve()

# Search
results = engine.resonate("vulnerabilities")
```

### How It Works

1. **Chunking**: Text split into ~8000 char chunks
2. **LLM Analysis**: Identifies blocks using exact quotes
3. **Validation**: Python verifies quote positions exist
4. **Storage**: Blocks stored with logical edges

### LLM Protocol

LLM receives text and returns JSON:
```json
{
  "blocks": [
    {
      "start_quote": "Module X depends",
      "end_quote": "Library Y.",
      "logic": "ORIGIN",
      "concepts": [{"name": "Module_X", "type": "DEF"}]
    },
    {
      "start_quote": "Library Y has",
      "end_quote": "vulnerability.",
      "logic": "IMP",
      "concepts": [{"name": "vulnerability", "type": "DEF"}]
    }
  ]
}
```

## API

| Method | Description |
|--------|-------------|
| `agent.digest(source, text)` | Stream text via LLM |
| `engine.resonate(query, mode)` | Search (VECTOR/MERKLE/BINOCULAR) |
| `engine.evolve()` | Run logical inference |
| `engine.forget(source)` | Delete document |
| `get_prompt()` | Operator prompt for AI agents |

## Logic Relations

| Relation | Meaning | Example |
|----------|---------|---------|
| `ORIGIN` | First block | Start of document |
| `IMP` | A implies B | "therefore", "because" |
| `NOT` | A contradicts B | "but", "however" |
| `EQUALS` | A = B | "means", "is defined as" |
| `GATE` | A conditions B | "if", "when" |

## For AI Agents

```python
from invariant_sdk import get_prompt

system_prompt = get_prompt()  # Full operator instructions
```

## Structure

```
invariant-sdk/
├── kernel/              # Rust (crystallize, merkle)
├── python/
│   └── invariant_sdk/
│       ├── engine.py           # Core engine
│       ├── tools/agent.py      # StructuralAgent
│       └── operator_prompt.md  # AI agent instructions
└── Makefile
```

## License

MIT
