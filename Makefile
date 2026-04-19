UV ?= uv

.PHONY: lock sync test

lock:
	$(UV) lock

sync:
	$(UV) sync

test:
	$(UV) run python -m unittest discover tests
