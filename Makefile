.PHONY: up down build dev clean logs

# ── One-command startup ──

up: ## Start all services with docker-compose
	@cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d
	@echo ""
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║        Credit Intel is now running!          ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║  Frontend:   http://localhost:3000           ║"
	@echo "║  Backend:    http://localhost:8080           ║"
	@echo "║  AI Engine:  http://localhost:8000           ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║  Demo cases are pre-loaded automatically.   ║"
	@echo "║  Data persists across restarts.              ║"
	@echo "╚══════════════════════════════════════════════╝"

down: ## Stop all services
	docker compose down

build: ## Rebuild all images
	docker compose build

dev: ## Start with live logs
	@cp -n .env.example .env 2>/dev/null || true
	docker compose up --build

clean: ## Stop services and remove data volume
	docker compose down -v
	@echo "All data cleared."

logs: ## Follow logs from all services
	docker compose logs -f

# ── Local development (no Docker) ──

dev-backend: ## Run Go backend locally
	cd backend-go && DATA_ROOT=./data DB_PATH=./data/credit-intel.db go run ./cmd/server

dev-ai: ## Run AI engine locally
	cd ai-engine && DATA_ROOT=./data uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run frontend locally
	cd frontend && npm run dev

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
