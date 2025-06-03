# Flow PubSub CLI

[![PyPI version](https://badge.fury.io/py/flow-pubsub-cli.svg)](https://pypi.org/project/flow-pubsub-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/flow-pubsub-cli.svg)](https://pypi.org/project/flow-pubsub-cli/)

A command-line client for **SuperCortex Flow** - a privacy-preserving, decentralized append-only pub/sub messaging system with unguessable 256-bit addressing.

## Features

- **🔐 Privacy-First Messaging**: Uses 256-bit unguessable message IDs with hierarchical structure
- **🏢 Organization Management**: Create and manage organizations with random 64-bit IDs  
- **📡 Topic-Based Subscriptions**: Subscribe to specific topics with cryptographic isolation
- **⚡ Real-time Streaming**: WebSocket-based event streaming for instant delivery
- **🔧 Automation-Friendly**: Netcat-style streaming for scripting and automation
- **🛡️ Cryptographic Security**: No enumeration attacks - can't discover messages without prior knowledge

## Installation

```bash
pip install flow-pubsub-cli
```

## Quick Start

### 1. Connect to a Flow Server

```bash
# Login with interactive prompts
flow login
# Server URL [http://localhost:2222]: 
# Token: your_auth_token_here
```

### 2. Create Organization

```bash
# Create your organization (gets random 64-bit ID)
flow config create-org --alias "my-backend"
# ✓ Created organization: a7f3d89c2b1e4068 (alias: my-backend)
```

### 3. Send and Receive Messages

```bash
# Send events to specific topics
flow add "Database connection failed" --topic logs.errors
flow add "User login successful" --topic auth.success

# Watch topics in real-time (WebSocket streaming)
flow watch logs.errors      # Only database error logs
flow watch auth             # All authentication events
```

## Core Commands

### Authentication & Configuration

```bash
flow login                           # Interactive login
flow config show                     # View current configuration
flow config create-org --alias name  # Create new organization
flow config set-org alias           # Switch organizations
```

### Messaging

```bash
flow add "message" --topic path      # Send event to topic
flow watch topic.path               # Watch topic in real-time
flow nc -l topic.path               # Netcat-style streaming
```

### Topic Sharing

```bash
flow share-topic logs.errors        # Generate shareable topic prefix
# Recipients can watch: flow watch a7f3d89c2b1e40683f8a2b1cd9e7f6a2
```

## Advanced Usage

### Netcat-Style Streaming

Perfect for automation and scripting:

```bash
# Stream events to stdout
flow nc -l logs.errors | grep "timeout" | logger -t "flow-alerts"

# Send continuous input as events  
tail -f /var/log/app.log | flow nc logs.events
echo "System startup complete" | flow nc system.status
```

### Cross-Organization Communication

```bash
# Alice shares her error logs
alice$ flow share-topic backend.errors
# Share: a7f3d89c.8f2a1b3c.d9e7f6a2

# Bob monitors Alice's errors (only this topic, nothing else)
bob$ flow watch a7f3d89c.8f2a1b3c.d9e7f6a2
```

### Automation Scripts

```bash
# Microservice error monitoring
#!/bin/bash
flow nc -l services.errors | while read error; do
  echo "$(date): $error" >> /var/log/flow-errors.log
  if echo "$error" | grep -q "CRITICAL"; then
    mail -s "Critical Error" admin@company.com <<< "$error"
  fi
done
```

## 256-bit Address Structure

SuperCortex Flow uses a unique addressing scheme for privacy:

```
┌─────────────┬─────────────┬─────────────┬─────────────────┐
│ 64-bit      │ 32-bit      │ 32-bit      │ 128-bit         │
│ random org  │ topic hash  │ topic nonce │ random          │
└─────────────┴─────────────┴─────────────┴─────────────────┘

Example: a7f3d89c2b1e4068.3f8a2b1c.d9e7f6a2.{128-bit-collision-resistant}
```

### Privacy Benefits

- **No enumeration attacks**: Can't discover messages without prior knowledge
- **Cryptographic isolation**: Each topic has unique nonces
- **Selective sharing**: Share specific topics without revealing org structure
- **Organization privacy**: Random 64-bit org IDs are unguessable

## Requirements

- Python 3.8+
- Access to a SuperCortex Flow server

## Dependencies

- `click>=8.1.0` - Command-line interface framework
- `requests>=2.31.0` - HTTP client for API calls
- `websockets>=12.0` - WebSocket client for real-time streaming

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Related Projects

- [SuperCortex Flow](https://github.com/igutekunst/flow) - The complete SuperCortex Flow system including server implementation

## Contributing

This is part of the SuperCortex Flow project. Please see the main repository for contribution guidelines. 