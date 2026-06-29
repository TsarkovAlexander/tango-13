SHELL := /bin/bash

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PYTEST := $(VENV)/bin/pytest
AWS_REGION ?= us-east-1
MICROVM_ARTIFACT ?= dist/tango-microvm.zip
LAMBDA_BROKER_ARTIFACT ?= dist/tango-broker-lambda.zip
MICROVM_S3_URI ?= s3://tango-test-569813798269-us-east-1-microvm-artifacts/tango-microvm.zip
MICROVM_IMAGE_NAME ?= tango-sandbox-executor
MICROVM_IMAGE_ARN ?= arn:aws:lambda:$(AWS_REGION):569813798269:microvm-image:$(MICROVM_IMAGE_NAME)
MICROVM_BASE_IMAGE_ARN ?= arn:aws:lambda:$(AWS_REGION):aws:microvm-image:al2023-1
MICROVM_BUILD_ROLE_ARN ?= arn:aws:iam::569813798269:role/tango-test-microvm-build
MICROVM_LOG_GROUP_NAME ?= /aws/lambda/microvms/tango-sandbox-executor

.PHONY: help init install build test check-temporal install-temporal-macos run-temporal run-api run-worker run-sandbox run-microvm-broker package-microvm package-lambda-broker upload-microvm-artifact create-microvm-image update-microvm-image clean

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
	@echo "  make run-microvm-broker Run Lambda MicroVM broker API locally"
	@echo "  make package-microvm    Package Lambda MicroVM sandbox artifact"
	@echo "  make package-lambda-broker"
	@echo "                          Package broker Lambda function artifact"
	@echo "  make create-microvm-image"
	@echo "                          Upload artifact and create AWS Lambda MicroVM image"
	@echo "  make update-microvm-image"
	@echo "                          Upload artifact and update existing AWS Lambda MicroVM image"
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

run-microvm-broker:
	$(UVICORN) sandbox_executor.microvm_broker:app --reload --host 127.0.0.1 --port 8081

package-microvm:
	$(PYTHON) -m scripts.package_microvm_artifact --output "$(MICROVM_ARTIFACT)"

package-lambda-broker:
	$(PYTHON) -m scripts.package_lambda_broker --output "$(LAMBDA_BROKER_ARTIFACT)"

upload-microvm-artifact: package-microvm
	@test -n "$(MICROVM_S3_URI)" || { echo "Set MICROVM_S3_URI=s3://bucket/key.zip"; exit 1; }
	aws s3 cp "$(MICROVM_ARTIFACT)" "$(MICROVM_S3_URI)" --region "$(AWS_REGION)"

create-microvm-image: upload-microvm-artifact
	@test -n "$(MICROVM_BUILD_ROLE_ARN)" || { echo "Set MICROVM_BUILD_ROLE_ARN=arn:aws:iam::569813798269:role/RoleName"; exit 1; }
	@test -n "$(MICROVM_LOG_GROUP_NAME)" || { echo "Set MICROVM_LOG_GROUP_NAME=/aws/lambda/microvms/LogGroupName"; exit 1; }
	aws lambda-microvms create-microvm-image \
		--region "$(AWS_REGION)" \
		--name "$(MICROVM_IMAGE_NAME)" \
		--code-artifact "uri=$(MICROVM_S3_URI)" \
		--base-image-arn "$(MICROVM_BASE_IMAGE_ARN)" \
		--build-role-arn "$(MICROVM_BUILD_ROLE_ARN)" \
		--logging '{"cloudWatch":{"logGroup":"$(MICROVM_LOG_GROUP_NAME)"}}'

update-microvm-image: upload-microvm-artifact
	@test -n "$(MICROVM_IMAGE_ARN)" || { echo "Set MICROVM_IMAGE_ARN=arn:aws:lambda:$(AWS_REGION):569813798269:microvm-image:Name"; exit 1; }
	@test -n "$(MICROVM_BUILD_ROLE_ARN)" || { echo "Set MICROVM_BUILD_ROLE_ARN=arn:aws:iam::569813798269:role/RoleName"; exit 1; }
	@test -n "$(MICROVM_LOG_GROUP_NAME)" || { echo "Set MICROVM_LOG_GROUP_NAME=/aws/lambda/microvms/LogGroupName"; exit 1; }
	aws lambda-microvms update-microvm-image \
		--region "$(AWS_REGION)" \
		--image-identifier "$(MICROVM_IMAGE_ARN)" \
		--code-artifact "uri=$(MICROVM_S3_URI)" \
		--base-image-arn "$(MICROVM_BASE_IMAGE_ARN)" \
		--build-role-arn "$(MICROVM_BUILD_ROLE_ARN)" \
		--logging '{"cloudWatch":{"logGroup":"$(MICROVM_LOG_GROUP_NAME)"}}'

# Stop local dev processes and remove generated build/cache files.
clean:
	@echo "Stopping local dev processes if running..."
	@pkill -f "temporal server start-dev" 2>/dev/null || true
	@pkill -f "python.*-m app.worker" 2>/dev/null || true
	@pkill -f "uvicorn sandbox_executor.server:app" 2>/dev/null || true
	@pkill -f "uvicorn sandbox_executor.microvm_broker:app" 2>/dev/null || true
	@pkill -f "uvicorn app.main:app" 2>/dev/null || true
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
