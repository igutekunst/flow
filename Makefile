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
	flow login admin_bootstrap_token_change_me
	flow agent create
	flow add "Hello from the CLI!"
	flow events 