.PHONY: help install install-dev clean lint typecheck test ci \
        build sign install-app dmg release \
        run stop restart logs reset-tcc

PYTHON ?= /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
PIP    ?= $(PYTHON) -m pip

APP_NAME    := NotifyMe
DIST_APP    := dist/$(APP_NAME).app
INSTALL_APP := /Applications/$(APP_NAME).app
DMG         := $(APP_NAME).dmg
STAMP       := .build-stamp

# ---------- help ----------

help:
	@echo "NotifyMe — make targets:"
	@echo ""
	@echo "  Setup:"
	@echo "    make install       — install runtime deps (pip install -e .)"
	@echo "    make install-dev   — install dev deps"
	@echo ""
	@echo "  Dev:"
	@echo "    make lint          — ruff check"
	@echo "    make fmt           — ruff format"
	@echo "    make typecheck     — mypy src"
	@echo "    make test          — pytest"
	@echo "    make ci            — lint + typecheck + test (no build)"
	@echo "    make clean         — remove build/, dist/, caches, stamps"
	@echo ""
	@echo "  Build:"
	@echo "    make build         — PyInstaller → dist/$(APP_NAME).app"
	@echo "    make sign          — build + fix symlinks + codesign dist/"
	@echo "    make install-app   — sign + copy to /Applications + sign + start"
	@echo "    make dmg           — sign + create $(DMG)"
	@echo "    make release       — install-app + dmg (build подтянется)"
	@echo ""
	@echo "  Run:"
	@echo "    make run           — start app from /Applications"
	@echo "    make stop          — stop app"
	@echo "    make restart       — stop + run"
	@echo "    make logs          — tail /tmp/notifyme_debug.log"
	@echo "    make reset-tcc     — tccutil reset Calendar"

# ---------- Setup ----------

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -r requirements-dev.txt

# ---------- Quality ----------

lint:
	$(PYTHON) -m ruff check src tests

fmt:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

typecheck:
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest -v

ci: lint typecheck test

# ---------- Clean ----------

clean:
	rm -rf build dist installer
	rm -f $(DMG) $(APP_NAME).spec nohup.out $(STAMP)
	rm -rf src/__pycache__ tests/__pycache__ scripts/__pycache__
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find src tests -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find src tests -name "*.pyc" -delete 2>/dev/null || true

# ---------- Build (sentinel, чтобы не пересобирать 4 раза) ----------

$(STAMP): $(shell find src -name '*.py') scripts/build.py pyproject.toml
	$(PYTHON) scripts/build.py
	@touch $(STAMP)

build: $(STAMP)

sign: $(STAMP)
	$(PYTHON) scripts/sign.py

install-app: sign
	$(PYTHON) scripts/install.py

dmg: sign
	$(PYTHON) scripts/dmg.py

release: install-app dmg
	@echo ""
	@echo "✅ Release done: $(DIST_APP), $(INSTALL_APP), $(DMG)"

# ---------- Run ----------

run:
	open -a $(INSTALL_APP)

stop:
	@pkill -f "$(INSTALL_APP)/Contents/MacOS/$(APP_NAME)" || true
	@rm -f /tmp/notifyme.lock

restart: stop run

logs:
	tail -f /tmp/notifyme_debug.log

reset-tcc:
	tccutil reset Calendar com.chep.notifyme
	@echo "TCC reset. Next 'make release' will prompt for Calendar access."
