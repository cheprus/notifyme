.PHONY: help install install-dev clean lint test build sign dmg release run stop restart

PYTHON ?= /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
PIP    ?= $(PYTHON) -m pip

help:
	@echo "NotifyMe — make targets:"
	@echo "  make install       — install runtime deps (pip install -e .)"
	@echo "  make install-dev   — install dev deps (pytest, ruff, pyinstaller)"
	@echo "  make lint          — ruff + mypy"
	@echo "  make test          — pytest"
	@echo "  make clean         — remove build/, dist/, __pycache__, *.pyc"
	@echo "  make build         — PyInstaller → dist/NotifyMe.app"
	@echo "  make sign          — codesign dist/NotifyMe.app"
	@echo "  make dmg           — create DMG"
	@echo "  make release       — build + sign + install + DMG"
	@echo "  make run           — start app from /Applications"
	@echo "  make stop          — stop app"
	@echo "  make restart       — stop + run"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check src
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest -v

clean:
	rm -rf build dist src/__pycache__ tests/__pycache__
	find src tests -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find src tests -name "*.pyc" -delete 2>/dev/null || true

build: clean
	$(PYTHON) scripts/build.py

sign:
	$(PYTHON) scripts/sign.py

dmg: sign
	$(PYTHON) scripts/dmg.py

release: build sign dmg install
	$(PYTHON) scripts/install.py

run:
	open -a /Applications/NotifyMe.app

stop:
	@pkill -f "/Applications/NotifyMe.app/Contents/MacOS/NotifyMe" || true
	@rm -f /tmp/notifyme.lock

restart: stop run
