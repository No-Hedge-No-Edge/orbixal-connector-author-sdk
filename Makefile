UV ?= uv

.PHONY: lock sync sync-contracts check-contracts test build

lock:
	$(UV) lock

sync:
	$(UV) sync

sync-contracts:
	python3 scripts/sync_canonical_contracts.py

check-contracts:
	python3 scripts/sync_canonical_contracts.py --check

test:
	$(UV) run python -m unittest discover tests

build:
	$(UV) build
