#!/bin/bash
set -e

echo "╔══════════════════════════════════════╗"
echo "║    Invariant SDK Installation        ║"
echo "╚══════════════════════════════════════╝"

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 required"; exit 1; }
command -v cargo >/dev/null 2>&1 || { echo "❌ Rust required (https://rustup.rs)"; exit 1; }
echo "✓ Prerequisites OK"

# Get script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Install maturin
pip install maturin --quiet

# Build kernel
echo "Building Rust kernel..."
cd kernel && maturin develop --release --features python
cd ..

# Install SDK
echo "Installing Python SDK..."
cd python && pip install -e .
cd ..

# Verify
python3 -c "from invariant_sdk import InvariantEngine; print('✓ InvariantEngine ready')"

echo ""
echo "✅ Installation Complete!"
echo ""
echo "Quick Start:"
echo "  from invariant_sdk import InvariantEngine"
echo "  engine = InvariantEngine('./data')"
