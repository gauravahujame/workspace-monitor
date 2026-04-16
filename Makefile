.PHONY: install install-dev install-web test lint format clean build publish help

PYTHON := python3
PIP := pip3

help:
	@echo "Workspace Monitor - Available Commands:"
	@echo "  make install      - Install package"
	@echo "  make install-dev  - Install with dev dependencies"
	@echo "  make install-web  - Install with web dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters (ruff, mypy)"
	@echo "  make format       - Format code with black"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make build        - Build distribution packages"
	@echo "  make publish      - Publish to PyPI"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev,web]"

install-web:
	$(PIP) install -e ".[web]"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/workspace_monitor

format:
	black src/
	ruff format src/

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	$(PYTHON) -m build

publish: build
	$(PYTHON) -m twine upload dist/*

dev-server:
	$(PYTHON) -m workspace_monitor.cli server --port 8765

scan:
	$(PYTHON) -m workspace_monitor.cli scan

list:
	$(PYTHON) -m workspace_monitor.cli list
