# 🌐 SuperCortex Flow

**A privacy-preserving, decentralized append-only pub/sub messaging system with unguessable 256-bit addressing**

SuperCortex Flow is a proof-of-concept implementation of a revolutionary messaging paradigm that combines **BitTorrent-style decentralization** with **Signal-level privacy**, using novel cryptographic addressing to enable private, scalable communication without central control.

## 🎯 Vision: Global Decentralized Messaging

### Core Innovation: 256-bit Unguessable Message IDs
- Messages addressed by **256-bit unguessable IDs** with hierarchical structure
- **Organization isolation** with random 64-bit org IDs
- **Topic-based subscriptions** with cryptographic nonces
- **No enumeration attacks** - you can't discover messages without prior knowledge
- **Privacy-first**: Only those with topic access can subscribe to related messages

### Privacy Model
```
Traditional:  Subscribe to "bitcoin" → Everyone sees your interest
SuperCortex:  Subscribe to "a7f3d89c2b1e4068.3f8a2b1c.d9e7f6a2" → Requires cryptographic proof
```

### 256-bit Address Structure
```
┌─────────────┬─────────────┬─────────────┬─────────────────┐
│ 64-bit      │ 32-bit      │ 32-bit      │ 128-bit         │
│ random org  │ topic hash  │ topic nonce │ random          │
└─────────────┴─────────────┴─────────────┴─────────────────┘

Example: a7f3d89c2b1e4068.3f8a2b1c.d9e7f6a2.{128-bit-collision-resistant}
```

### Full Vision Features
- **🔗 DHT-based routing** forming organic mesh networks based on demand
- **🛡️ Zero-knowledge proofs** for subscription authentication  
- **⚡ Multiple transports** (HTTP, WebSockets, libp2p)
- **🔐 End-to-end encryption** with group key management
- **📊 Reputation-based peer discovery** and abuse prevention
- **🌍 Truly decentralized** - no central servers, companies, or points of failure

## 🏗️ Current Implementation (PoC)

**Status**: Localhost development prototype implementing core concepts

### What's Working Now
- ✅ **256-bit event addressing** with org + topic + cryptographic nonces
- ✅ **Organization management** with random IDs and local aliases
- ✅ **Topic-based messaging** with hierarchical structure
- ✅ **Real-time WebSocket streaming** for instant event delivery
- ✅ **Cryptographic topic isolation** - can't guess other topics
- ✅ **Selective topic sharing** without revealing org structure
- ✅ **Netcat-style streaming** for automation and scripting
- ✅ **Token-based authentication** and agent management
- ✅ **Binary-safe message bodies** with base64 encoding
- ✅ **PostgreSQL persistence** for development testing

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Tool      │    │  FastAPI Backend │    │   PostgreSQL    │
│   `flow`        │◄──►│  Port 2222       │◄──►│   Database      │
│  256-bit IDs    │    │  WebSocket +     │    │  Binary Events  │
│  Topic Mgmt     │    │  HTTP REST API   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Start the System
```bash
docker compose up -d
```

### 2. Install CLI
```bash
make install-cli-only
```

### 3. Setup & Authentication
```bash
# Login with interactive prompts
flow login
# Server URL [http://localhost:2222]: 
# Token: admin_bootstrap_token_change_me

# Create your organization (gets random 64-bit ID)
flow config create-org --alias "my-backend"
# ✓ Created organization: a7f3d89c2b1e4068 (alias: my-backend)
# ✓ Set as default organization
#   Token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
#   Topic Key: f3a8d2c1e9b70456...
```

### 4. Topic-Based Messaging
```bash
# Send events to specific topics
flow add "Database connection failed" --topic logs.errors
flow add "User john@example.com logged in" --topic auth.success
flow add "Payment processed: $129.99" --topic payments.completed

# Watch topics in real-time (WebSocket streaming)
flow watch logs.errors      # Only database error logs
flow watch auth             # All authentication events  
flow watch payments         # All payment events
```

### 5. Share Topics Securely
```bash
# Generate shareable prefix for specific topic
flow share-topic logs.errors
# ✓ Shareable prefix for 'logs.errors':
#   a7f3d89c2b1e40683f8a2b1cd9e7f6a2

# Recipients can watch your shared topic
flow watch a7f3d89c2b1e40683f8a2b1cd9e7f6a2
# They can ONLY see logs.errors events, nothing else
```

## 🔧 Advanced Usage

### Organization Management
```bash
# View current configuration
flow config show
# Current configuration:
#   Server: http://localhost:2222
#   Default Org: a7f3d89c2b1e4068
#   Org Aliases:
#     my-backend: a7f3d89c2b1e4068
#     frontend: e2a6b9d4f1c87053

# Create additional orgs with aliases
flow config create-org --alias "frontend"
flow config create-org --alias "mobile-app"

# Switch between organizations
flow config set-org frontend
```

### Netcat-Style Streaming
```bash
# Stream raw event bodies to stdout (perfect for piping)
flow nc -l logs.errors | grep "timeout" | logger -t "flow-alerts"

# Send continuous input as events
tail -f /var/log/app.log | flow nc logs.events
echo "System startup complete" | flow nc system.status

# Real-time log processing pipeline
flow nc -l sensor.temperature | \
  jq 'select(.temp > 85)' | \
  flow nc alerts.overheating
```

### Cross-Organization Communication
```bash
# Alice shares her error logs
alice$ flow share-topic backend.errors
# Share: a7f3d89c.8f2a1b3c.d9e7f6a2

# Bob monitors Alice's errors
bob$ flow watch a7f3d89c.8f2a1b3c.d9e7f6a2
# Bob can ONLY see backend.errors, not alice's other topics

# Alice continues using simple syntax
alice$ flow add "Redis connection timeout" --topic backend.errors
alice$ flow watch backend       # All backend events
```

### Automation & Scripting
```bash
# Microservice error monitoring
#!/bin/bash
flow nc -l services.errors | while read error; do
  echo "$(date): $error" >> /var/log/flow-errors.log
  if echo "$error" | grep -q "CRITICAL"; then
    mail -s "Critical Error" admin@company.com <<< "$error"
  fi
done

# IoT sensor data collection
#!/bin/bash
while true; do
  temp=$(sensors | awk '/Core 0/ {print $3}' | tr -d '+°C')
  echo "{\"temperature\": $temp, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" | \
    flow nc sensors.temperature
  sleep 30
done
```

## 🔒 Security Model

### 256-bit Privacy Protection
```
Your Org: a7f3d89c2b1e4068  (64-bit random - unguessable)
├── logs.errors  → 3f8a2b1c.d9e7f6a2  (unique nonce per topic)
├── auth.login   → 8c4a1f9e.5b2d8a7c  (can't guess from other topics)
└── payments.*   → 9e2f7d1a.3c8f2b4e  (cryptographically isolated)
```

### Current PoC Security
- **Random organization IDs** prevent org enumeration
- **Cryptographic topic nonces** prevent topic guessing
- **Selective sharing** - share specific topics without revealing org structure
- **No event listing** - you can only access events by computed prefix
- **Token-based authentication** for development

### Full Vision Security
- **Zero-knowledge proofs** for subscription requests
- **DHT-based routing** with no central points of failure  
- **End-to-end encryption** with forward secrecy
- **Reputation scoring** and abuse prevention
- **No metadata leakage** about subscriber interests

## 🎯 Use Cases

### Privacy-Critical Communication
```bash
# Whistleblower networks - Sources share via unguessable topic IDs
source$ flow share-topic evidence.corruption
# Share: 3d7a9f2c1b8e5047.a2f8d1c9.e7b6a3f5

recipient$ flow nc -l 3d7a9f2c1b8e5047.a2f8d1c9.e7b6a3f5 | gpg --encrypt
```

### Decentralized Applications
```bash
# Private social networks - No company can deplatform or surveil
flow add "Meeting at 3pm in room 204" --topic group.private-chat
flow share-topic group.announcements  # Share with new members

# IoT device coordination - Sensors sharing data without central aggregation
flow nc -l home.sensors | jq '.temperature' | flow nc weather.indoor-temp
```

### Development & Monitoring
```bash
# Microservice debugging across teams
flow share-topic backend.database-errors  # Share with DBA team
flow share-topic frontend.api-errors      # Share with API team

# Real-time deployment monitoring
flow nc -l deploy.production | grep "ERROR" | slack-notify
```

## 🔬 Development

### Default Credentials
- **Admin Token**: `admin_bootstrap_token_change_me`
- **Backend**: http://localhost:2222
- **Database**: PostgreSQL (internal to Docker)

### Development Commands
```bash
make build              # Build Docker images
make up                 # Start services  
make down               # Stop services
make logs               # View backend logs
make install-cli-only   # Install CLI tools
```

### Testing the System
```bash
# Terminal 1: Watch events
flow config create-org --alias test
flow watch logs.errors

# Terminal 2: Send events
flow add "Test error message" --topic logs.errors
flow add "Another test" --topic logs.debug

# Terminal 3: Netcat streaming
echo "Streaming test" | flow nc logs.stream
flow nc -l logs.stream
```

## 🎨 CLI Reference

### Configuration Commands
```bash
flow config create-org [--alias NAME]    # Create new organization
flow config show                         # Show current config
flow config set-org ALIAS               # Switch default org
```

### Messaging Commands
```bash
flow add MESSAGE [--topic PATH]         # Send event to topic
flow watch TOPIC_OR_PREFIX              # Watch events (WebSocket)
flow watch TOPIC --poll                 # Watch events (polling fallback)
flow get EVENT_ID                       # Retrieve specific event
```

### Sharing Commands
```bash
flow share-topic TOPIC [--copy]         # Generate shareable prefix
```

### Netcat Commands
```bash
flow nc -l TOPIC_OR_PREFIX              # Stream event bodies to stdout
flow nc TOPIC                           # Send stdin as events
```

### Legacy Commands
```bash
flow agent create                       # Create agent (admin only)
flow login                             # Interactive login
```

## 🚧 Roadmap to Full Vision

### Phase 1: Core Protocol (Current)
- [x] 256-bit unguessable ID generation
- [x] Organization + topic-based addressing
- [x] Cryptographic topic isolation
- [x] Real-time WebSocket streaming
- [x] Selective topic sharing

### Phase 2: Decentralization
- [ ] DHT-based peer discovery
- [ ] Inter-node message routing
- [ ] Subscription forwarding
- [ ] Network topology management

### Phase 3: Advanced Privacy
- [ ] Zero-knowledge subscription proofs
- [ ] End-to-end encryption
- [ ] Forward secrecy
- [ ] Metadata protection

### Phase 4: Production Ready
- [ ] Multiple transport layers
- [ ] Reputation systems
- [ ] Abuse prevention
- [ ] Performance optimization

---

**This is experimental software implementing novel cryptographic networking concepts. Use for research and development only.** 