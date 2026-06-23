SHELL := /bin/bash

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PYTEST := $(VENV)/bin/pytest

.PHONY: help init install build test check-temporal install-temporal-macos run-temporal run-api run-worker run-sandbox firecracker-smoke clean

help:
	@echo "Available targets:"
	@echo "  make init               Create virtualenv, install dev dependencies, and install Temporal CLI"
	@echo "  make install            Install package with dev dependencies into existing virtualenv"
	@echo "  make build              Build source and wheel distributions"
	@echo "  make test               Run test suite"
	@echo "  make check-temporal     Check whether Temporal CLI is installed"
	@echo "  make install-temporal-macos"
	@echo "                          Install Temporal CLI with Homebrew"
	@echo "  make run-temporal       Run local Temporal dev server"
	@echo "  make run-api            Run FastAPI app locally"
	@echo "  make run-worker         Run Temporal worker locally"
	@echo "  make run-sandbox        Run sandbox executor API locally"
	@echo "  make firecracker-smoke  Run Firecracker host smoke checks"
	@echo "  make clean              Stop local dev processes and remove generated files"

# Bootstrap a fresh local environment for end-to-end testing.
init:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"
	$(MAKE) install-temporal-macos

# Refresh Python dependencies inside an existing virtualenv.
install:
	$(VENV_PYTHON) -m pip install -e ".[dev]"

# Build both source and wheel distributions from the installed project.
build: install
	$(VENV_PYTHON) -m pip install build
	$(VENV_PYTHON) -m build

# Run the local test suite.
test:
	$(PYTEST)

# Fail fast when the Temporal CLI is missing.
check-temporal:
	@command -v temporal >/dev/null || { \
		echo "Temporal CLI is not installed."; \
		echo "Install it with: make install-temporal-macos"; \
		echo "Or see: https://docs.temporal.io/cli"; \
		exit 1; \
	}
	@temporal --version

# Install the Temporal CLI on macOS with Homebrew.
install-temporal-macos:
	brew install temporal

# Start the local Temporal dev server and UI.
run-temporal: check-temporal
	temporal server start-dev --namespace default

# Start FastAPI without creating Temporal workflows.
run-api:
	TANGO_TEMPORAL_START_ENABLED=false $(UVICORN) app.main:app --reload --host 127.0.0.1 --port 8000

# Start the Temporal worker that executes workflow activities.
run-worker:
	$(VENV_PYTHON) -m app.worker

# Start the local sandbox executor API used by the worker.
run-sandbox:
	$(UVICORN) sandbox_executor.server:app --reload --host 127.0.0.1 --port 8080

# Run Firecracker readiness checks on a Linux/KVM sandbox host, not local macOS.
firecracker-smoke:
	spikes/firecracker_smoke/run.sh

# Stop local dev processes and remove generated build/cache files.
clean:
	@echo "Stopping local dev processes if running..."
	@pkill -f "temporal server start-dev" 2>/dev/null || true
	@pkill -f "python.*-m app.worker" 2>/dev/null || true
	@pkill -f "uvicorn sandbox_executor.server:app" 2>/dev/null || true
	@pkill -f "uvicorn app.main:app" 2>/dev/null || true
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
