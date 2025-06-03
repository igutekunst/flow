import requests
import asyncio
import websockets
import json
import hashlib
import hmac
import secrets
import urllib.parse
from typing import Optional, Dict, List, Callable, AsyncGenerator, Any, Union
from datetime import datetime
import threading
import time
from pathlib import Path
import aiohttp


class FlowError(Exception):
    """Base exception for Flow operations"""
    pass


class FlowAuthError(FlowError):
    """Authentication related errors"""
    pass


class FlowConnectionError(FlowError):
    """Connection related errors"""
    pass


class FlowConfig:
    """Configuration management for Flow client"""
    
    # Standard config locations (same as CLI)
    DEFAULT_CONFIG_DIR = Path.home() / ".flow"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
    DEFAULT_TOKEN_FILE = DEFAULT_CONFIG_DIR / "token"
    DEFAULT_CLIENT_SECRET_FILE = DEFAULT_CONFIG_DIR / "client_secret"
    
    def __init__(self, server: str = None, token: str = None, org_id: str = None, client_secret: str = None):
        self.server = server or "http://localhost:2222"
        self.token = token
        self.org_id = org_id
        self.client_secret = client_secret
        self.org_aliases = {}
        self.prefix_aliases = {}
    
    @classmethod
    def load(cls, config_path: str = None):
        """Load configuration from standard locations or custom path
        
        Args:
            config_path: Optional custom path to config file. If None, uses standard location.
        
        Returns:
            FlowConfig instance with loaded configuration
        """
        config = cls()
        
        if config_path:
            # Load from custom path
            config_file = Path(config_path)
            if config_file.exists():
                config_data = json.loads(config_file.read_text())
                config._apply_config_data(config_data)
            
            # For custom path, assume token and secret are in same directory
            config_dir = config_file.parent
            token_file = config_dir / "token"
            secret_file = config_dir / "client_secret"
        else:
            # Load from standard locations
            config_file = cls.DEFAULT_CONFIG_FILE
            token_file = cls.DEFAULT_TOKEN_FILE
            secret_file = cls.DEFAULT_CLIENT_SECRET_FILE
            
            if config_file.exists():
                config_data = json.loads(config_file.read_text())
                config._apply_config_data(config_data)
        
        # Load token
        if token_file.exists():
            config.token = token_file.read_text().strip()
        
        # Load client secret
        if secret_file.exists():
            config.client_secret = secret_file.read_text().strip()
        
        return config
    
    def _apply_config_data(self, config_data: dict):
        """Apply configuration data from JSON"""
        self.server = config_data.get("base_url", self.server)
        self.org_id = config_data.get("default_org_id", self.org_id)
        self.org_aliases = config_data.get("org_aliases", {})
        self.prefix_aliases = config_data.get("prefix_aliases", {})
    
    def save(self, config_path: str = None):
        """Save configuration to file
        
        Args:
            config_path: Optional custom path to config file. If None, uses standard location.
        """
        if config_path:
            config_file = Path(config_path)
            config_dir = config_file.parent
            token_file = config_dir / "token"
            secret_file = config_dir / "client_secret"
        else:
            config_file = self.DEFAULT_CONFIG_FILE
            config_dir = self.DEFAULT_CONFIG_DIR
            token_file = self.DEFAULT_TOKEN_FILE
            secret_file = self.DEFAULT_CLIENT_SECRET_FILE
        
        # Ensure directory exists
        config_dir.mkdir(exist_ok=True)
        
        # Save main config
        config_data = {
            "base_url": self.server,
            "default_org_id": self.org_id,
            "org_aliases": self.org_aliases,
            "prefix_aliases": self.prefix_aliases
        }
        
        # Remove None values
        config_data = {k: v for k, v in config_data.items() if v is not None}
        
        config_file.write_text(json.dumps(config_data, indent=2))
        
        # Save token with secure permissions
        if self.token:
            token_file.write_text(self.token)
            token_file.chmod(0o600)
        
        # Save client secret with secure permissions
        if self.client_secret:
            secret_file.write_text(self.client_secret)
            secret_file.chmod(0o600)
    
    def add_org_alias(self, alias: str, org_id: str):
        """Add an organization alias"""
        self.org_aliases[alias] = org_id
    
    def add_prefix_alias(self, alias: str, hex_prefix: str):
        """Add a prefix alias"""
        self.prefix_aliases[alias] = hex_prefix.lower()
    
    def resolve_org_alias(self, alias: str) -> Optional[str]:
        """Resolve organization alias to org ID"""
        return self.org_aliases.get(alias)
    
    def resolve_prefix_alias(self, alias: str) -> Optional[str]:
        """Resolve prefix alias to hex prefix"""
        return self.prefix_aliases.get(alias)


class FlowEvent:
    """Represents a Flow event"""
    
    def __init__(self, id: str, body: str, timestamp: str, agent_id: str, body_length: int = None):
        self.id = id
        self.body = body
        self.timestamp = timestamp
        self.agent_id = agent_id
        self.body_length = body_length or len(body)


class TopicWatcher:
    """Manages watching a specific topic"""
    
    def __init__(self, client: 'FlowClient', topic_or_prefix: str, callback: Callable[[FlowEvent], None] = None):
        self.client = client
        self.topic_or_prefix = topic_or_prefix
        self.callback = callback
        self._running = False
        self._task = None
    
    def start(self):
        """Start watching (non-blocking)"""
        if self._running:
            return
        
        self._running = True
        if asyncio.iscoroutinefunction(self.callback):
            # Async callback
            self._task = asyncio.create_task(self._watch_async())
        else:
            # Sync callback, run in thread
            self._task = threading.Thread(target=self._watch_sync)
            self._task.start()
    
    def stop(self):
        """Stop watching"""
        self._running = False
        if self._task:
            if isinstance(self._task, threading.Thread):
                self._task.join()
            else:
                self._task.cancel()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    async def _watch_async(self):
        """Async watching implementation"""
        async for event in self.client.stream_topic(self.topic_or_prefix):
            if not self._running:
                break
            if self.callback:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(event)
                else:
                    self.callback(event)
    
    def _watch_sync(self):
        """Sync watching implementation"""
        # Run async generator in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._watch_async())
        finally:
            loop.close()


class Topic:
    """Convenience wrapper for topic operations"""
    
    def __init__(self, client: 'FlowClient', topic_path: str):
        self.client = client
        self.topic_path = topic_path
    
    def send(self, body: str) -> str:
        """Send event to this topic (sync)"""
        return self.client.send_event(body, topic=self.topic_path)
    
    async def send_async(self, body: str) -> str:
        """Send event to this topic (async)"""
        return await self.client.send_event_async(body, topic=self.topic_path)
    
    def get_history(self, limit: int = 100, since: str = None) -> List[FlowEvent]:
        """Get topic history (sync)"""
        return self.client.get_history(self.topic_path, limit=limit, since=since)
    
    async def get_history_async(self, limit: int = 100, since: str = None) -> List[FlowEvent]:
        """Get topic history (async)"""
        return await self.client.get_history_async(self.topic_path, limit=limit, since=since)
    
    def watch(self, callback: Callable[[FlowEvent], None] = None) -> TopicWatcher:
        """Watch this topic"""
        return self.client.watch_topic(self.topic_path, callback=callback)
    
    def stream(self) -> AsyncGenerator[FlowEvent, None]:
        """Stream events from this topic (async generator)"""
        return self.client.stream_topic(self.topic_path)
    
    def share(self) -> str:
        """Get shareable prefix for this topic"""
        return self.client.share_topic(self.topic_path)


class FlowClient:
    """Main Flow client with sync/async support"""
    
    def __init__(self, config: FlowConfig = None, server: str = None, token: str = None):
        if config:
            self.config = config
        else:
            self.config = FlowConfig(server=server, token=token)
        
        self.session = requests.Session()
        if self.config.token:
            self.session.headers.update({"Authorization": f"Bearer {self.config.token}"})
        
        self._websocket = None
        self._ws_lock = asyncio.Lock()
        self._watchers = {}
        self._aiohttp_session = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_async()
    
    def close(self):
        """Close client and cleanup resources"""
        # Stop all watchers
        for watcher in list(self._watchers.values()):
            watcher.stop()
        self._watchers.clear()
    
    async def close_async(self):
        """Close client and cleanup resources (async)"""
        # Close WebSocket
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
        
        # Close aiohttp session
        if self._aiohttp_session:
            await self._aiohttp_session.close()
            self._aiohttp_session = None
        
        # Stop all watchers
        for watcher in list(self._watchers.values()):
            watcher.stop()
        self._watchers.clear()
    
    def set_token(self, token: str):
        """Set authentication token"""
        self.config.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    # Cryptographic helpers
    def _derive_topic_key(self, client_secret: str) -> bytes:
        """Derive topic key from client secret"""
        salt = b"supercortex_flow_topic_key_derivation_v1"
        return hmac.new(salt, client_secret.encode('utf-8'), hashlib.sha256).digest()
    
    def _generate_topic_hash(self, topic_path: str) -> str:
        """Generate 32-bit hash of topic path"""
        return hashlib.sha256(topic_path.encode('utf-8')).digest()[:4].hex()
    
    def _generate_topic_nonce(self, topic_key: bytes, topic_path: str) -> str:
        """Generate deterministic 32-bit nonce for topic"""
        return hmac.new(topic_key, topic_path.encode('utf-8'), hashlib.sha256).digest()[:4].hex()
    
    def _compute_topic_prefix(self, org_id: str, topic_path: str, client_secret: str) -> str:
        """Compute full topic prefix"""
        topic_key = self._derive_topic_key(client_secret)
        topic_hash = self._generate_topic_hash(topic_path)
        topic_nonce = self._generate_topic_nonce(topic_key, topic_path)
        return f"{org_id}{topic_hash}{topic_nonce}"
    
    def _resolve_topic_or_prefix(self, topic_or_prefix: str) -> str:
        """Resolve topic path to hex prefix"""
        # Check if it's a prefix alias first
        if hasattr(self.config, 'prefix_aliases'):
            prefix_alias = self.config.resolve_prefix_alias(topic_or_prefix)
            if prefix_alias:
                return prefix_alias
        
        # If it looks like a hex prefix, use as-is
        if all(c in '0123456789abcdefABCDEF' for c in topic_or_prefix) and len(topic_or_prefix) >= 16:
            return topic_or_prefix.lower()
        
        # Must be a topic path - compute prefix
        if not self.config.org_id or not self.config.client_secret:
            raise FlowError("Organization ID and client secret required for topic paths")
        
        return self._compute_topic_prefix(self.config.org_id, topic_or_prefix, self.config.client_secret)
    
    async def _get_aiohttp_session(self):
        """Get or create aiohttp session"""
        if self._aiohttp_session is None or self._aiohttp_session.closed:
            headers = {}
            if self.config.token:
                headers["Authorization"] = f"Bearer {self.config.token}"
            self._aiohttp_session = aiohttp.ClientSession(headers=headers)
        return self._aiohttp_session
    
    async def _make_request_async(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """Make async HTTP request to Flow server"""
        if not self.config.token:
            raise FlowAuthError("No authentication token set")
        
        url = f"{self.config.server.rstrip('/')}{endpoint}"
        session = await self._get_aiohttp_session()
        
        try:
            if method == "POST":
                async with session.post(url, json=data, params=params) as response:
                    return await self._handle_response(response)
            elif method == "GET":
                async with session.get(url, params=params) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
        except aiohttp.ClientError as e:
            raise FlowConnectionError(f"Connection error: {e}")
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> dict:
        """Handle aiohttp response"""
        if not response.ok:
            try:
                error_data = await response.json()
                error_detail = error_data.get("detail", "Unknown error")
            except:
                error_detail = await response.text()
            
            if response.status == 401:
                raise FlowAuthError(f"Authentication failed: {error_detail}")
            elif response.status >= 500:
                raise FlowConnectionError(f"Server error: {error_detail}")
            else:
                raise FlowError(f"HTTP {response.status}: {error_detail}")
        
        return await response.json()
    
    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """Make HTTP request to Flow server (sync)"""
        if not self.config.token:
            raise FlowAuthError("No authentication token set")
        
        url = f"{self.config.server.rstrip('/')}{endpoint}"
        
        try:
            if method == "POST":
                response = self.session.post(url, json=data, params=params)
            elif method == "GET":
                response = self.session.get(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if not response.ok:
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                except:
                    error_detail = response.text
                
                if response.status_code == 401:
                    raise FlowAuthError(f"Authentication failed: {error_detail}")
                elif response.status_code >= 500:
                    raise FlowConnectionError(f"Server error: {error_detail}")
                else:
                    raise FlowError(f"HTTP {response.status_code}: {error_detail}")
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            raise FlowConnectionError(f"Connection error: {e}")
    
    # Organization management
    def create_organization(self, alias: str = None) -> str:
        """Create new organization (sync)"""
        result = self._make_request("POST", "/agents", {})
        org_id = result["id"]
        
        # Generate client secret if not set
        if not self.config.client_secret:
            self.config.client_secret = secrets.token_hex(32)
        
        # Set as default
        self.config.org_id = org_id
        
        return org_id
    
    async def create_organization_async(self, alias: str = None) -> str:
        """Create new organization (async)"""
        result = await self._make_request_async("POST", "/agents", {})
        org_id = result["id"]
        
        # Generate client secret if not set
        if not self.config.client_secret:
            self.config.client_secret = secrets.token_hex(32)
        
        # Set as default
        self.config.org_id = org_id
        
        return org_id
    
    def set_default_organization(self, org_id: str):
        """Set default organization"""
        self.config.org_id = org_id
    
    # Event operations
    def send_event(self, body: str, topic: str = None) -> str:
        """Send event (sync)"""
        data = {"body": body}
        if topic:
            data["topic_path"] = topic
        
        result = self._make_request("POST", "/events", data)
        return result["id"]
    
    async def send_event_async(self, body: str, topic: str = None) -> str:
        """Send event (async)"""
        data = {"body": body}
        if topic:
            data["topic_path"] = topic
        
        result = await self._make_request_async("POST", "/events", data)
        return result["id"]
    
    def get_event(self, event_id: str) -> FlowEvent:
        """Get specific event by ID (sync)"""
        result = self._make_request("GET", f"/events/{event_id}")
        return FlowEvent(
            id=result["id"],
            body=result["body"],
            timestamp=result["timestamp"],
            agent_id=result["agent_id"],
            body_length=result.get("body_length")
        )
    
    async def get_event_async(self, event_id: str) -> FlowEvent:
        """Get specific event by ID (async)"""
        result = await self._make_request_async("GET", f"/events/{event_id}")
        return FlowEvent(
            id=result["id"],
            body=result["body"],
            timestamp=result["timestamp"],
            agent_id=result["agent_id"],
            body_length=result.get("body_length")
        )
    
    def get_history(self, topic_or_prefix: str, limit: int = 100, since: str = None) -> List[FlowEvent]:
        """Get event history (sync)"""
        prefix = self._resolve_topic_or_prefix(topic_or_prefix)
        
        params = {"prefix": prefix, "limit": limit}
        if since:
            params["since"] = since
        
        result = self._make_request("GET", "/events/watch", params=params)
        
        events = []
        for event_data in result.get("events", []):
            events.append(FlowEvent(
                id=event_data["id"],
                body=event_data.get("body", ""),
                timestamp=event_data["timestamp"],
                agent_id=event_data["agent_id"],
                body_length=event_data.get("body_length")
            ))
        
        return events
    
    async def get_history_async(self, topic_or_prefix: str, limit: int = 100, since: str = None) -> List[FlowEvent]:
        """Get event history (async)"""
        prefix = self._resolve_topic_or_prefix(topic_or_prefix)
        
        params = {"prefix": prefix, "limit": limit}
        if since:
            params["since"] = since
        
        result = await self._make_request_async("GET", "/events/watch", params=params)
        
        events = []
        for event_data in result.get("events", []):
            events.append(FlowEvent(
                id=event_data["id"],
                body=event_data.get("body", ""),
                timestamp=event_data["timestamp"],
                agent_id=event_data["agent_id"],
                body_length=event_data.get("body_length")
            ))
        
        return events
    
    # Topic sharing
    def share_topic(self, topic_path: str) -> str:
        """Generate shareable prefix for topic"""
        if not self.config.org_id or not self.config.client_secret:
            raise FlowError("Organization ID and client secret required")
        
        return self._compute_topic_prefix(self.config.org_id, topic_path, self.config.client_secret)
    
    # Watching and streaming
    def watch_topic(self, topic_or_prefix: str, callback: Callable[[FlowEvent], None] = None) -> TopicWatcher:
        """Watch topic for new events"""
        watcher = TopicWatcher(self, topic_or_prefix, callback)
        self._watchers[topic_or_prefix] = watcher
        return watcher
    
    async def stream_topic(self, topic_or_prefix: str) -> AsyncGenerator[FlowEvent, None]:
        """Stream events from topic (async generator)"""
        prefix = self._resolve_topic_or_prefix(topic_or_prefix)
        
        # Get WebSocket connection
        websocket = await self._get_websocket(prefix)
        
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_sender(websocket))
            
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        if data.get("type") == "connected":
                            # Server confirms connection
                            continue
                        elif data.get("type") == "heartbeat":
                            # Server heartbeat - just continue
                            continue
                        elif data.get("type") == "pong":
                            # Response to our ping - just continue
                            continue
                        
                        # This is an event - CLI shows events don't have "type" field
                        if "timestamp" in data and "agent_id" in data and "id" in data:
                            # WebSocket only sends metadata, need to fetch full event for body
                            event_id = data["id"]
                            
                            try:
                                # Fetch full event to get body (like CLI does)
                                full_event = await self.get_event_async(event_id)
                                yield full_event
                                
                            except Exception:
                                # If we can't get the full event, yield with metadata only
                                yield FlowEvent(
                                    id=data["id"],
                                    body="",  # No body available
                                    timestamp=data["timestamp"],
                                    agent_id=data["agent_id"],
                                    body_length=data.get("body_length", 0)
                                )
                        
                    except json.JSONDecodeError:
                        continue  # Skip invalid messages
                    except KeyError:
                        continue  # Skip messages with missing fields
                        
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                    
        except websockets.exceptions.ConnectionClosed:
            raise FlowConnectionError("WebSocket connection closed")
    
    async def _get_websocket(self, prefix: str = None):
        """Get or create WebSocket connection"""
        async with self._ws_lock:
            if self._websocket is None or self._websocket.closed:
                ws_url = self.config.server.replace('http://', 'ws://').replace('https://', 'wss://')
                
                # Build query parameters like CLI does
                query_params = {"token": self.config.token}
                if prefix:
                    query_params["prefix"] = prefix
                
                query_string = urllib.parse.urlencode(query_params)
                full_ws_url = f"{ws_url}/events/watch_ws?{query_string}"
                
                try:
                    self._websocket = await websockets.connect(full_ws_url, ping_interval=20, ping_timeout=10)
                except Exception as e:
                    raise FlowConnectionError(f"Failed to connect WebSocket: {e}")
            
            return self._websocket
    
    async def _heartbeat_sender(self, websocket):
        """Send periodic heartbeats to keep connection alive"""
        try:
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                try:
                    heartbeat_msg = {
                        "type": "ping", 
                        "timestamp": datetime.utcnow().isoformat() + 'Z'
                    }
                    await websocket.send(json.dumps(heartbeat_msg))
                except websockets.exceptions.ConnectionClosed:
                    break
        except asyncio.CancelledError:
            pass
    
    # Convenience methods
    def topic(self, topic_path: str) -> Topic:
        """Get Topic object for convenient operations"""
        return Topic(self, topic_path)
    
    def add_org_alias(self, alias: str, org_id: str = None):
        """Add organization alias (uses current org if org_id not specified)"""
        if org_id is None:
            org_id = self.config.org_id
        if not org_id:
            raise FlowError("No organization ID specified and no default organization set")
        self.config.add_org_alias(alias, org_id)
    
    def add_prefix_alias(self, alias: str, hex_prefix: str):
        """Add prefix alias for easy topic sharing"""
        self.config.add_prefix_alias(alias, hex_prefix)
    
    def save_config(self, config_path: str = None):
        """Save current configuration to file"""
        self.config.save(config_path)
    
    def show_config(self) -> dict:
        """Get current configuration as dictionary"""
        return {
            "server": self.config.server,
            "org_id": self.config.org_id,
            "has_token": bool(self.config.token),
            "has_client_secret": bool(self.config.client_secret),
            "org_aliases": self.config.org_aliases,
            "prefix_aliases": self.config.prefix_aliases
        }

    @classmethod
    def from_config(cls, config_path: str = None):
        """Create FlowClient from config file
        
        Args:
            config_path: Optional custom path to config file. If None, uses standard location.
        
        Returns:
            FlowClient instance with loaded configuration
        """
        config = FlowConfig.load(config_path)
        return cls(config)


# Export main classes
__all__ = ['FlowClient', 'FlowConfig', 'FlowEvent', 'Topic', 'TopicWatcher', 'FlowError', 'FlowAuthError', 'FlowConnectionError'] 