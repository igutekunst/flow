# 🌐 Global Append-Only Pub/Sub Log Protocol

## Overview

A decentralized, privacy-preserving, append-only pub/sub log where messages are addressed by large, unguessable IDs. Messages can be selectively shared by revealing prefixes of these IDs. The network forms an organic routing mesh based on demand-driven prefix subscriptions.

## ✉️ Message Format

Each message is represented as a **3-tuple**:

```json
{
  "id": "string (UUID or 128+ bit hex)",
  "timestamp": "ISO8601 UTC timestamp",
  "body": "base64-encoded binary payload"
}
```

* `id` — A unique identifier for the message. Must be at least 128 bits of entropy.
* `timestamp` — Time of publication in UTC.
* `body` — Arbitrary binary content, base64-encoded. May be encrypted or plain text.

## 🌐 Transport

### Canonical Initial Transport (PoC)

* Protocol: HTTP/1.1
* Encoding: JSON
* Payloads: base64-encoded body field

### Endpoints

* `POST /msg` — Submit a new message
* `GET /msg/<id>` — Retrieve message by full ID
* `POST /subscribe` — Subscribe to a prefix with proof

## 🔑 Subscriptions

### Subscription Request

```json
{
  "prefix": "hex string prefix (min 64 bits)",
  "proof": "base64 or hex string proving knowledge of full ID under this prefix"
}
```

* Prefix length must meet a minimum threshold (e.g. 64 bits).
* Proof can be a hash of a known full ID starting with the prefix.

### Server Behavior

* If server has matching messages: respond immediately with them.
* If not:

  * Stores the subscription.
  * Optionally forwards the subscription using DHT-based routing.

## 🧭 Routing

* Routing is based on **DHT-like lookup** (e.g., Kademlia-style XOR distance to prefix).
* Each server maintains a routing table of known peer interests by prefix.
* Subscriptions may be **forwarded to closer nodes** in the DHT overlay.
* Future messages matching a known prefix are relayed to interested peers.

## 💾 Storage

* Messages are stored in an **append-only** fashion.
* Indexed by `id` (optionally hashed for key-value store compatibility).
* Servers may discard old messages unless configured otherwise.

## 🔒 Privacy Model

* Message IDs are unguessable (128-bit+ entropy).
* No enumeration of message space is allowed.
* Subscriptions must include a proof of knowledge.
* Messages may be encrypted; content is opaque to servers by default.

## 🚫 Abuse Prevention

* Servers reject subscriptions below the minimum prefix length.
* No broad prefix scans allowed (e.g., length < 64 bits).
* Additional rate limits, scoring, and trust layers can be added incrementally.

## 🧩 Optional Future Features

* Encrypted group messaging and key management
* Zero-knowledge proofs for prefix possession
* Merkle-indexed logs for tamper evidence
* Multiple transport layers (libp2p, WebSockets, etc.)
* Reputation-based peer discovery

## 📘 Summary

This protocol defines a decentralized messaging and subscription system built around unguessable identifiers and prefix-based access. It ensures that messages are only visible to those with sufficient prior knowledge, forming the basis for private, scalable pub/sub communication without central control.

Initial PoC will use HTTP + JSON with base64-encoded binary bodies, DHT routing, and simple proof-based subscription mechanics.
