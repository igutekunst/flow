# SuperCortex Flow

Event ingestion system with FastAPI backend and CLI for localhost testing.

## Quick Start

1. **Start the system:**
   ```bash
   docker compose up -d
   ```

2. **Install CLI:**
   ```bash
   make install-cli-only
   ```

3. **Login and test:**
   ```bash
   flow login admin_bootstrap_token_change_me
   flow agent create
   flow add "Hello world!"
   flow events
   ```

## Architecture

- **Raw byte stream** with layered structure: `{agent_id, timestamp, body}`
- **Token-based auth** - Admin can create new agents
- **Docker Compose** deployment with PostgreSQL
- **Localhost ready** for immediate testing

## CLI Usage

```bash
flow login <token>              # Login with admin or agent token
flow agent create               # Create new agent (admin only)
flow add "message"              # Add event to stream
flow events                     # List recent events
```

## Components

- **Backend**: FastAPI service on port 2222
- **Database**: PostgreSQL on port 5432 (internal)
- **CLI**: `flow` command for interaction
- **Library**: Python client for programmatic access

## Default Admin Token

`admin_bootstrap_token_change_me` 