#!/usr/bin/env bash
set -euo pipefail

echo "Invariant SDK (Halo-first) install"

command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

cd python
pip install -e .
cd ..

python3 -c "from invariant_sdk import HaloClient, load_crystal; print('✓ SDK ready:', HaloClient, load_crystal)"
