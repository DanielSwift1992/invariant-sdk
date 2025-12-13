# Invariant SDK (Halo)

Halo-first client/runtime for Invariant OS v3:

- Canonical Merkle hashing (Identity)
- v3+ `.crystal` reader (BinaryCrystal + zero-start indexes)
- `HaloClient` (Semantic DNS / Ghost edges)

## Install

```bash
pip install -e invariant-sdk/python
```

## Quick Start

```python
from invariant_sdk import HaloClient

halo = HaloClient("http://127.0.0.1:8080")

# Resolve surface concept -> public atoms (hash8 addresses).
atoms = halo.resolve_concept("pytorch")

# Explicit operators (no hidden defaults):
neighbors_or = halo.get_concept_halo("pytorch", mode="blend")               # OR / superposition
neighbors_and = halo.get_concept_halo("python torch", mode="interference")  # AND / intersection
```

Halos are cached permanently under `~/.invariant/halo/<crystal_id>/`.

## Local Crystal (Optional)

```python
from invariant_sdk import load_crystal

crystal = load_crystal("output/qwen/qwen_full_v3.crystal")
```

Requires the companion files:
- `output/qwen/qwen_full_v3.index`
- `output/qwen/qwen_full_v3.vocab.idx`

## Sidecar v2 (Optional)

```bash
python crystal-miner/sidecar.py ingest --halo http://127.0.0.1:8080 my_private_docs/
python crystal-miner/sidecar.py query --halo http://127.0.0.1:8080 "gpu requirements"
```

## Notes

- Halo servers are read-only: no text, no inference — only `hash8 → neighbors`.
- If you want privacy, batch decoys client-side; the protocol remains stateless.

## License

MIT
