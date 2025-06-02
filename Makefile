.PHONY: build install-cli test

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

install-cli:
	cd lib && pip install -e .
	cd cli && pip install -e .

install-cli-only:
	cd cli && pip install -e .

test-flow:
	@echo "Testing basic flow..."
	@echo "⚠️  Note: Login is now interactive. Run manually:"
	@echo "  flow login  # Enter server URL and token when prompted"
	@echo "  flow agent create"
	@echo "  flow add \"Hello from the CLI!\""
	@echo "  flow watch <prefix>  # Watch for events with specific prefix" 