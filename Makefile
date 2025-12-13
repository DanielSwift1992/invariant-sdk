.PHONY: install build test clean help

help:
	@echo "Invariant SDK (Halo-first)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "  install   Install Python SDK (Halo)"
	@echo "  build     (legacy) no-op"
	@echo "  test      Verify Halo imports"
	@echo "  clean     Remove build artifacts"

install:
	@echo "Installing Invariant SDK (Halo)..."
	cd python && pip install -e .
	@echo ""
	@echo "✅ Done! Try: python3 -c 'from invariant_sdk import HaloClient'"

test:
	@python3 -c "from invariant_sdk import HaloClient, load_crystal; print('✓ SDK:', HaloClient, load_crystal)"
	@echo "All tests passed!"

clean:
	rm -rf python/*.egg-info
	rm -rf python/build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
build:
	@echo "Kernel build is not part of the Halo-first SDK."
