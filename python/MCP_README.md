# Invariant MCP Server

**Semantic Kernel for LLM Agents**

## Quick Start

### 1. Install

```bash
pip install invariant-sdk
```

### 2. Configure ANY MCP Client

Works with: **Cursor, Claude Desktop, Windsurf, Cline, any MCP client.**

Generic MCP config:

```json
{
  "mcpServers": {
    "invariant": {
      "command": "invariant-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

**That's it.** One command, all clients.

### 3. Index Your Project

```bash
cd /path/to/your/project
inv ingest ./src
```

From your project directory:

```bash
inv ingest ./src
# or
inv ingest .
```

This creates `.invariant/overlay.jsonl` with semantic knowledge.

---

## Available Tools

### `status`
Check Invariant connection and overlay stats.

```
> status()
{
  "crystal_id": "qwen_exact_v3:v3",
  "mean_mass": 0.2649,
  "overlay_edges": 1247,
  "overlay_docs": 5
}
```

### `locate(issue_text, max_results?)`
**The main search tool.** Find relevant files by pasting error messages, function names, or any text.

**USE INSTEAD OF:** `grep -rn`, `rg`, `find` (repo-wide searches)

```
> locate("separability_matrix")
{
  "files": [
    {
      "file": "separable.py",
      "score": 2.0,
      "occurrences": [
        {"line": 32, "content": "from .separable import separability_matrix"},
        {"line": 293, "content": "def separability_matrix(transform):"}
      ]
    }
  ]
}
```

### `list_docs()`
List all indexed documents with stats.

```
> list_docs()
{
  "total_documents": 15,
  "total_edges": 3247,
  "documents": [
    {"doc": "engine.py", "edges": 892, "concepts": 127}
  ]
}
```

### `scoped_grep(pattern, files, max_matches?)`
Search for EXACT pattern in specific files. **Use after locate()** to refine search.

```
> scoped_grep("ASCIIValidator", "validators.py,test_validators.py")
{
  "matches": [
    {"file": "validators.py", "line": 45, "content": "class ASCIIUsernameValidator:"}
  ]
}
```

### `semantic_map(file_path)`
Get semantic skeleton of a file — anchors, connections, structure.

**Much cheaper than reading the whole file.**

```
> semantic_map("auth.py")
{
  "anchors": [
    {"word": "user", "mass": 0.38, "phase": "solid"},
    {"word": "token", "mass": 0.35, "phase": "solid"}
  ],
  "edges": [
    {"src": "user", "tgt": "authenticate", "line": 45},
    {"src": "authenticate", "tgt": "token", "line": 47}
  ]
}
```

### `prove_path(source, target)`
**Anti-hallucination tool.** Check if connection exists before making claims.

```
> prove_path("User", "Database")
{
  "exists": true,
  "ring": "sigma",
  "path": ["User", "save", "Database"],
  "provenance": "models.py:123"
}
```

- `ring: sigma` = proven from your documents
- `ring: lambda` = global knowledge (may not apply to your context)
- `exists: false` = no proof found — don't make the claim!

### `list_conflicts()`
Find contradictions in your documents.

```
> list_conflicts()
{
  "conflicts": [
    {
      "old": {"doc": "contract_v1.pdf", "line": 15},
      "new": {"doc": "contract_v2.pdf", "line": 22},
      "target": "price"
    }
  ]
}
```

### `context(doc, line, ctx_hash?)`
Get semantic context with self-healing.

```
> context("config.py", 42, "a1b2c3d4")
{
  "status": "fresh",       // or "relocated" or "broken"
  "actual_line": 42,
  "content": "DB_TIMEOUT = 30..."
}
```

### `ingest(file_path)`
Add a file to the knowledge base.

```
> ingest("new_module.py")
{
  "success": true,
  "edges": 47,
  "anchors": 23
}
```

---

## Why LLM Will Use This

**Economics:**

| Action | Cost | Risk |
|--------|------|------|
| Read 1000 lines | High (tokens) | Hallucination |
| `prove_path(A, B)` | Low | Guaranteed answer |

LLM chooses Invariant not because we ask, but because **it's cheaper and safer**.

---

## Environment Variables

- `INVARIANT_SERVER` — Halo server URL (default: `https://orb.invarianthub.com`)

---

## Deployment Options

### Local (Default)
Just run in your project. Overlay lives in `.invariant/`.

### Team (Git)
Commit `.invariant/overlay.jsonl` to version control.
Everyone gets the same semantic knowledge.

### Cloud (Future)
Deploy Halo server + overlay storage. Coming soon.

---

## Theory

See `docs/INVARIANTS.md` for the physics:

- **σ-facts** = grounded in documents (provable)
- **α-axioms** = global crystal (background knowledge)
- **ctx_hash** = semantic checksum for drift detection
- **Bisection Law** = each query should cut uncertainty in half

*"Invariant is not RAG. It's a Semantic OS."*
