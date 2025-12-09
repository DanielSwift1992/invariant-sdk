.PHONY: install build test clean help

help:
	@echo "Invariant SDK"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "  install   Build kernel + install SDK"
	@echo "  build     Build Rust kernel only"
	@echo "  test      Verify installation"
	@echo "  clean     Remove build artifacts"

install:
	@echo "Installing Invariant SDK..."
	pip install maturin --quiet
	cd kernel && maturin develop --release --features python
	cd python && pip install -e .
	@echo ""
	@echo "✅ Done! Try: python3 -c 'from invariant_sdk import InvariantEngine'"

build:
	cd kernel && maturin develop --release --features python

test:
	@python3 -c "import invariant_kernel; print('✓ Kernel:', invariant_kernel.__name__)"
	@python3 -c "from invariant_sdk import InvariantEngine; print('✓ SDK: InvariantEngine')"
	@echo "All tests passed!"

clean:
	rm -rf kernel/target
	rm -rf python/*.egg-info
	rm -rf python/build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
