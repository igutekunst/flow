# 🌐 SuperCortex Flow

**A privacy-preserving, decentralized append-only pub/sub messaging system with unguessable addressing**

SuperCortex Flow is a proof-of-concept implementation of a revolutionary messaging paradigm that combines **BitTorrent-style decentralization** with **Signal-level privacy**, using novel cryptographic addressing to enable private, scalable communication without central control.

## 🎯 Vision: Global Decentralized Messaging

### Core Innovation: Unguessable Message IDs
- Messages addressed by **128+ bit unguessable IDs** (not topics like "sports" or "news")
- **Prefix-based subscriptions** with proof-of-knowledge requirements
- **No enumeration attacks** - you can't discover messages without prior knowledge
- **Privacy-first**: Only those with partial ID knowledge can subscribe to related messages

### Privacy Model
```
Traditional:  Subscribe to "bitcoin" → Everyone sees your interest
SuperCortex:  Subscribe to prefix "6973616163000000" → Requires proving you know a real message ID
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
- ✅ **Event ingestion** with unguessable 128-bit IDs
- ✅ **Prefix-based filtering** with 64-bit mandatory padding
- ✅ **Token-based authentication** and agent management
- ✅ **Real-time prefix watching** via CLI
- ✅ **Binary-safe message bodies** with base64 encoding
- ✅ **PostgreSQL persistence** for development testing

### Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Tool      │    │  FastAPI Backend │    │   PostgreSQL    │
│   `flow`        │◄──►│  Port 2222       │◄──►│   Database      │
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

### 3. Authentication & Basic Usage
```bash
# Login with interactive prompts
flow login
# Server URL [http://localhost:2222]: 
# Token: [hidden input]

# Create a new agent (gets its own token)
flow agent create

# Add events with prefix-based addressing
flow add "Hello world!" -p isaac
flow add "Secret message" -p alice

# Watch for events matching a prefix (requires 64-bit minimum)
flow watch isaac     # Watches for events with "isaac" prefix
flow watch alice     # Watches for events with "alice" prefix
```

### 4. Understanding Prefix-Based Addressing
```bash
# When you add an event with prefix "isaac":
flow add "test" -p isaac
# ✓ Event added (prefix: isaac): 6973616163000000474854190288ec9f

# The ID starts with padded prefix: 6973616163000000 (isaac + null padding)
# Only those who know to watch "isaac" will see this event
# No one can discover this by scanning - they need prior knowledge
```

## 🔧 Components

### Backend (FastAPI)
- **Event ingestion API** with 128-bit ID generation
- **Prefix-based filtering** with mandatory 64-bit padding
- **Agent authentication** system
- **Real-time event watching** endpoints

### CLI (`flow` command)
```bash
flow login                      # Interactive login (prompts for server & token)
flow agent create               # Create new agent (admin only)
flow add "message" -p <prefix>  # Add event with optional prefix
flow watch <prefix>             # Real-time prefix-based filtering
flow get <event_id>             # Retrieve specific event
```

### Python Library
```python
from supercortex_flow import FlowClient

client = FlowClient(token="your_token")
result = client.add_event("Hello from Python!")
agent = client.create_agent()  # Get new agent ID and token
```

## 🔐 Security Model

### Current PoC Security
- **Token-based authentication** for development
- **64-bit minimum prefix length** prevents broad scanning
- **Unguessable IDs** prevent message enumeration
- **No event listing** - you can only access events by ID or prefix watch

### Full Vision Security
- **Zero-knowledge proofs** for subscription requests
- **DHT-based routing** with no central points of failure  
- **End-to-end encryption** with forward secrecy
- **Reputation scoring** and abuse prevention
- **No metadata leakage** about subscriber interests

## 🎯 Use Cases

### Privacy-Critical Communication
- **Whistleblower networks** - Sources can share via unguessable IDs
- **Activist coordination** - Organizing without revealing participant lists
- **Corporate intelligence** - Sharing sensitive information with verified recipients

### Decentralized Applications
- **Private social networks** - No company can deplatform or surveil
- **Distributed marketplaces** - Trading without central oversight
- **IoT device coordination** - Sensors sharing data without central aggregation

### Research & Development
- **Privacy protocol research** - Testing new cryptographic approaches
- **Decentralized systems** - Building mesh networks and DHT overlays
- **Anti-surveillance technology** - Developing censorship-resistant communication

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
make test-flow          # Test basic CLI workflow
```

## 🚧 Roadmap to Full Vision

### Phase 1: Core Protocol (Current)
- [x] Unguessable ID generation
- [x] Prefix-based filtering
- [x] Basic authentication
- [x] RESTful API design

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