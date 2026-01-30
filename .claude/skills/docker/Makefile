# Docker Skill - Testing
#
# Usage:
#   make test      # Run all tests
#   make clean     # Remove test artifacts

TEST_DIR := test-app
IMAGE_NAME := docker-skill-test

.PHONY: all test clean setup build-dev build-prod test-dev test-prod

help:
	@echo "Docker Skill Test Commands:"
	@echo "  make test       - Run all tests (setup, build, verify)"
	@echo "  make clean      - Remove test artifacts"
	@echo "  make setup      - Create test FastAPI app"
	@echo "  make build-dev  - Build development image"
	@echo "  make build-prod - Build production image"

# === Full Test ===

test: setup build-dev build-prod test-dev test-prod clean
	@echo "✓ All Docker skill tests passed"

# === Setup Test App ===

setup:
	@echo "Creating test FastAPI app..."
	@mkdir -p $(TEST_DIR)/src/app
	@echo 'fastapi>=0.115.0\nuvicorn[standard]>=0.32.0' > $(TEST_DIR)/requirements.txt
	@echo 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/health/live")\ndef live():\n    return {"status": "ok"}\n\n@app.get("/health/ready")\ndef ready():\n    return {"status": "ok"}' > $(TEST_DIR)/src/app/main.py
	@touch $(TEST_DIR)/src/app/__init__.py $(TEST_DIR)/src/__init__.py
	@cp templates/python/Dockerfile $(TEST_DIR)/Dockerfile
	@# Fix paths for src layout
	@sed -i '' 's|app.main:app|src.app.main:app|g' $(TEST_DIR)/Dockerfile 2>/dev/null || \
		sed -i 's|app.main:app|src.app.main:app|g' $(TEST_DIR)/Dockerfile
	@cp templates/python/dockerignore $(TEST_DIR)/.dockerignore
	@echo "  ✓ Test app created"

# === Build ===

build-dev:
	@echo "Building development image..."
	@cd $(TEST_DIR) && docker build --target dev -t $(IMAGE_NAME):dev . -q
	@echo "  ✓ Dev image built"

build-prod:
	@echo "Building production image..."
	@cd $(TEST_DIR) && docker build --target production -t $(IMAGE_NAME):prod . -q
	@echo "  ✓ Production image built"

# === Test Images ===

test-dev:
	@echo "Testing development image..."
	@docker run -d --name $(IMAGE_NAME)-dev-test -p 8001:8000 $(IMAGE_NAME):dev > /dev/null
	@sleep 8
	@curl -sf http://localhost:8001/health/live > /dev/null || (docker rm -f $(IMAGE_NAME)-dev-test > /dev/null; echo "FAIL: Dev health check"; exit 1)
	@docker rm -f $(IMAGE_NAME)-dev-test > /dev/null
	@echo "  ✓ Dev image health check passed"

test-prod:
	@echo "Testing production image..."
	@docker run -d --name $(IMAGE_NAME)-prod-test -p 8002:8000 $(IMAGE_NAME):prod > /dev/null
	@sleep 12
	@curl -sf http://localhost:8002/health/live > /dev/null || (docker rm -f $(IMAGE_NAME)-prod-test > /dev/null; echo "FAIL: Prod health check"; exit 1)
	@docker rm -f $(IMAGE_NAME)-prod-test > /dev/null
	@echo "  ✓ Production image health check passed"

# === Cleanup ===

clean:
	@echo "Cleaning up..."
	@rm -rf $(TEST_DIR)
	@docker rmi $(IMAGE_NAME):dev $(IMAGE_NAME):prod 2>/dev/null || true
	@docker rm -f $(IMAGE_NAME)-dev-test $(IMAGE_NAME)-prod-test 2>/dev/null || true
	@echo "  ✓ Cleanup complete"
