.PHONY: help setup setup-api setup-web dev dev-api dev-web seed test clean prod-stack prod-stack-down eval-demo

PYTHON ?= $(shell command -v python3.11 || command -v python3)

help:
	@echo "TenderAudit Makefile targets:"
	@echo "  setup          Install Python deps + npm deps + create dirs"
	@echo "  setup-api      Create Python venv and install api/requirements.txt"
	@echo "  setup-web      Run npm install in web/"
	@echo "  dev            Run API (port 8001) + web (port 3001) concurrently"
	@echo "  dev-api        Run API only on :8001"
	@echo "  dev-web        Run web only on :3001"
	@echo "  seed           Download seed tender PDFs then generate synthetic bidder bundles"
	@echo "  eval-demo      Upload tender + bidder ZIPs and print compliance matrix"
	@echo "  test           Run pytest on api/tests/"
	@echo "  prod-stack     Start Postgres + MinIO via docker-compose"
	@echo "  prod-stack-down  Stop docker-compose services"
	@echo "  clean          Remove data/ node_modules and venv"

setup: setup-api setup-web
	mkdir -p data/blobs data/certs

setup-api:
	cd api && $(PYTHON) -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt

setup-web:
	cd web && npm install

dev:
	@echo "Starting API on :8001 and web on :3001 — Ctrl+C to stop both"
	@(trap 'kill 0' INT; \
	  api/.venv/bin/uvicorn api.main:app --reload --port 8001 & \
	  cd web && npm run dev & \
	  wait)

dev-api:
	api/.venv/bin/uvicorn api.main:app --reload --port 8001

dev-web:
	cd web && npm run dev

seed:
	api/.venv/bin/python scripts/fetch_seed_pdfs.py
	api/.venv/bin/python scripts/gen_bidder_bundle.py

test:
	api/.venv/bin/pytest api/tests/ -v

eval-demo:
	@echo "=== TenderAudit Demo: Uploading tender + bidder ZIPs and printing compliance matrix ==="
	@API_URL=$${API_URL:-http://localhost:8001}; \
	for tender_dir in seed/bidders/*/; do \
	  tender=$$(basename $$tender_dir); \
	  echo ""; \
	  echo "--- Tender: $$tender ---"; \
	  for bidder_dir in $$tender_dir*/; do \
	    bidder=$$(basename $$bidder_dir); \
	    echo "  Bidder $$bidder:"; \
	    curl -s -X POST "$$API_URL/api/evaluate" \
	      -F "tender=@seed/pdfs/$${tender}.pdf" \
	      -F "bidder_dir=$$bidder_dir" \
	      2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); [print('    ',c['id'],c['name'],'->', 'PASS' if c.get('pass') else 'FAIL', c.get('note','')) for c in d.get('criteria',[])]" 2>/dev/null || echo "    (API not running — run: make dev-api)"; \
	  done; \
	done
	@echo ""
	@echo "=== Matrix complete. Run 'make dev' and open http://localhost:3001 for the visual matrix ==="

prod-stack:
	docker-compose up -d
	@echo "Postgres on :5433, MinIO on :9002 (console :9003), Adminer on :8081"

prod-stack-down:
	docker-compose down

clean:
	rm -rf data web/node_modules api/.venv
