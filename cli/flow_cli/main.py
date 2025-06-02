import click
import json
import sys
import os
import requests
import time
import base64
import asyncio
import websockets
import urllib.parse
import hashlib
import hmac
import secrets
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path.home() / ".flow"
TOKEN_FILE = CONFIG_DIR / "token"
CONFIG_FILE = CONFIG_DIR / "config.json"
CLIENT_SECRET_FILE = CONFIG_DIR / "client_secret"

def ensure_config_dir():
    CONFIG_DIR.mkdir(exist_ok=True)

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}

def save_config(config):
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

def load_token():
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None

def save_token(token):
    ensure_config_dir()
    TOKEN_FILE.write_text(token)
    TOKEN_FILE.chmod(0o600)  # Secure permissions

def load_client_secret():
    """Load the client secret used for cryptographic operations"""
    if CLIENT_SECRET_FILE.exists():
        return CLIENT_SECRET_FILE.read_text().strip()
    return None

def save_client_secret(client_secret):
    """Save the client secret with secure permissions"""
    ensure_config_dir()
    CLIENT_SECRET_FILE.write_text(client_secret)
    CLIENT_SECRET_FILE.chmod(0o600)  # Secure permissions

def generate_client_secret():
    """Generate a new random client secret"""
    return secrets.token_urlsafe(32)

def derive_topic_key_from_client_secret(client_secret: str) -> bytes:
    """Derive a deterministic topic key from the client secret"""
    salt = b"supercortex_flow_topic_key_derivation_v1"
    return hmac.new(salt, client_secret.encode('utf-8'), hashlib.sha256).digest()

def generate_topic_hash(topic_path: str) -> str:
    """Generate 32-bit hash of topic path"""
    return hashlib.sha256(topic_path.encode('utf-8')).digest()[:4].hex()

def generate_topic_nonce(topic_key: bytes, topic_path: str) -> str:
    """Generate deterministic 32-bit nonce for topic using HMAC"""
    return hmac.new(topic_key, topic_path.encode('utf-8'), hashlib.sha256).digest()[:4].hex()

def compute_topic_prefix(org_id: str, topic_path: str, client_secret: str) -> str:
    """Compute the full topic prefix for watching/sharing"""
    topic_key = derive_topic_key_from_client_secret(client_secret)
    topic_hash = generate_topic_hash(topic_path)
    topic_nonce = generate_topic_nonce(topic_key, topic_path)
    return f"{org_id}{topic_hash}{topic_nonce}"

def generate_256bit_id(org_id: str = None, topic_path: str = None, topic_key: bytes = None) -> str:
    """
    Generate a 256-bit ID with structure:
    64-bit org_id + 32-bit topic_hash + 32-bit topic_nonce + 128-bit random
    
    Same logic as backend but client-controlled
    """
    import os
    import hashlib
    import hmac
    
    # 64-bit org ID (8 bytes)
    if org_id:
        org_bytes = bytes.fromhex(org_id)
        if len(org_bytes) != 8:
            raise ValueError("org_id must be exactly 64 bits (8 bytes)")
    else:
        org_bytes = os.urandom(8)
    
    # 32-bit topic hash (4 bytes)
    if topic_path:
        topic_hash_bytes = hashlib.sha256(topic_path.encode('utf-8')).digest()[:4]
    else:
        topic_hash_bytes = b'\x00' * 4
    
    # 32-bit topic nonce (4 bytes)  
    if topic_path and topic_key:
        topic_nonce_bytes = hmac.new(topic_key, topic_path.encode('utf-8'), hashlib.sha256).digest()[:4]
    else:
        topic_nonce_bytes = b'\x00' * 4
        
    # 128-bit random (16 bytes)
    random_bytes = os.urandom(16)
    
    # Combine all parts (32 bytes total = 256 bits)
    full_id = org_bytes + topic_hash_bytes + topic_nonce_bytes + random_bytes
    return full_id.hex()

def add_event_with_topic(message: str, topic_path: str = None):
    """Add an event, optionally with a topic path."""
    try:
        config_data = load_config()
        org_id = config_data.get('default_org_id')
        client_secret = load_client_secret()
        
        if org_id and client_secret:
            # Generate ID client-side using config org_id
            if topic_path:
                topic_key = derive_topic_key_from_client_secret(client_secret)
                event_id = generate_256bit_id(org_id, topic_path, topic_key)
            else:
                event_id = generate_256bit_id(org_id)
            
            data = {
                "body": message,
                "id": event_id  # Send pre-computed ID
            }
        else:
            # Fallback for backwards compatibility
            data = {"body": message}
            
        if topic_path:
            data["topic_path"] = topic_path
            
        result = make_request("POST", "/events", data)
        topic_info = f" (topic: {topic_path})" if topic_path else ""
        click.echo(f"✓ Event added{topic_info}: {result['id']}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

def make_request(method, endpoint, data=None, params=None):
    token = load_token()
    if not token:
        click.echo("❌ Not logged in. Use 'flow login' first", err=True)
        sys.exit(1)
    
    config = load_config()
    url = f"{config['base_url']}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    
    if method == "POST":
        response = requests.post(url, json=data, headers=headers, params=params)
    elif method == "GET":
        response = requests.get(url, headers=headers, params=params)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    if not response.ok:
        try:
            error_detail = response.json().get("detail", "Unknown error")
        except:
            error_detail = response.text
        raise Exception(f"HTTP {response.status_code}: {error_detail}")
    
    return response.json()

@click.group(invoke_without_command=True)
@click.pass_context
@click.option('-t', '--topic', help='Topic path for event (e.g., logs.errors)')
def cli(ctx, topic):
    """SuperCortex Flow CLI - Event ingestion system with 256-bit addressing"""
    # If no subcommand is provided, check for stdin input
    if ctx.invoked_subcommand is None:
        # Check if there's stdin data available
        if not sys.stdin.isatty():
            # Read from stdin
            stdin_content = sys.stdin.read().strip()
            if stdin_content:
                add_event_with_topic(stdin_content, topic)
            else:
                click.echo("❌ No input provided", err=True)
                sys.exit(1)
        else:
            # No stdin and no subcommand, show help
            click.echo(ctx.get_help())

@cli.command()
def login():
    """Login with server URL and token"""
    # Prompt for user
    user = click.prompt('User')
    
    # Prompt for server URL with default
    server_url = click.prompt(
        'Server URL',
        default='localhost:2222',
        show_default=True
    ).rstrip('/')
    
    # Add http:// if no protocol specified
    if not server_url.startswith(('http://', 'https://')):
        server_url = f'http://{server_url}'
    
    # Prompt for token with no default (already masked with hide_input=True)
    token = click.prompt(
        'Token',
        hide_input=True
    )
    
    # Save both config and token
    config = load_config()
    config["base_url"] = server_url
    config["user"] = user
    save_config(config)
    save_token(token)
    
    click.echo(f"✓ Logged in successfully as {user} to {server_url}")

@cli.group()
def config():
    """Configuration management"""
    pass

@config.command("create-org")
@click.option('--alias', help='Human-readable alias for the organization (local only)')
def create_org(alias):
    """Create a new organization with random 64-bit ID"""
    try:
        # Check if we have a client secret, generate one if not
        client_secret = load_client_secret()
        if not client_secret:
            click.echo("🔑 No client secret found, generating one...")
            client_secret = generate_client_secret()
            save_client_secret(client_secret)
            click.echo("✓ Generated client secret for cryptographic operations")
        
        result = make_request("POST", "/agents", {})
        
        # Save org info in config
        config_data = load_config()
        config_data["default_org_id"] = result["id"]
        
        if alias:
            if "org_aliases" not in config_data:
                config_data["org_aliases"] = {}
            config_data["org_aliases"][alias] = result["id"]
            
        save_config(config_data)
        
        alias_info = f" (alias: {alias})" if alias else ""
        click.echo(f"✓ Created organization: {result['id']}{alias_info}")
        click.echo(f"✓ Set as default organization")
        click.echo(f"  Token: {result['token']}")
        click.echo(f"  Client secret is ready for topic key derivation")
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

@config.command("show")
def show_config():
    """Show current configuration"""
    config_data = load_config()
    client_secret = load_client_secret()
    
    click.echo("Current configuration:")
    click.echo(f"  User: {config_data.get('user', 'Not set')}")
    click.echo(f"  Server: {config_data.get('base_url', 'Not set')}")
    click.echo(f"  Default Org: {config_data.get('default_org_id', 'Not set')}")
    click.echo(f"  Client Secret: {'Set' if client_secret else 'Not set'}")
    
    aliases = config_data.get('org_aliases', {})
    if aliases:
        click.echo("  Org Aliases:")
        for alias, org_id in aliases.items():
            click.echo(f"    {alias}: {org_id}")

@config.command("set-org")  
@click.argument('org_alias')
def set_org(org_alias):
    """Set default organization by alias"""
    config_data = load_config()
    aliases = config_data.get('org_aliases', {})
    
    if org_alias not in aliases:
        click.echo(f"❌ Unknown org alias: {org_alias}", err=True)
        click.echo("Available aliases:", err=True)
        for alias in aliases.keys():
            click.echo(f"  {alias}", err=True)
        sys.exit(1)
    
    config_data["default_org_id"] = aliases[org_alias]
    save_config(config_data)
    click.echo(f"✓ Set default organization to: {org_alias} ({aliases[org_alias]})")

@config.command("generate-secret")
def generate_secret():
    """Generate a new client secret for cryptographic operations"""
    existing_secret = load_client_secret()
    
    if existing_secret:
        if not click.confirm("⚠️  A client secret already exists. Generating a new one will invalidate existing topic prefixes. Continue?"):
            click.echo("❌ Cancelled")
            return
    
    new_secret = generate_client_secret()
    save_client_secret(new_secret)
    
    click.echo("✓ Generated new client secret")
    click.echo("  This secret is used for generating topic keys and event IDs")
    click.echo("  To share with other clients, use 'flow config export-secret'")

@config.command("export-secret")
@click.option('--output', '-o', help='Output file (default: stdout)')
def export_secret(output):
    """Export client secret for sharing with other client instances"""
    client_secret = load_client_secret()
    
    if not client_secret:
        click.echo("❌ No client secret found. Run 'flow config generate-secret' first", err=True)
        sys.exit(1)
    
    # Create exportable format with metadata
    export_data = {
        "type": "supercortex_flow_client_secret",
        "version": "v1",
        "secret": client_secret,
        "exported_at": datetime.utcnow().isoformat() + 'Z'
    }
    
    export_json = json.dumps(export_data, indent=2)
    
    if output:
        with open(output, 'w') as f:
            f.write(export_json)
        click.echo(f"✓ Client secret exported to: {output}")
    else:
        click.echo("# SuperCortex Flow Client Secret Export")
        click.echo("# Share this securely with other client instances")
        click.echo(export_json)

@config.command("import-secret")
@click.option('--file', '-f', help='Import from file (default: stdin)')
@click.option('--force', is_flag=True, help='Overwrite existing secret without confirmation')
def import_secret(file, force):
    """Import client secret from another client instance"""
    existing_secret = load_client_secret()
    
    if existing_secret and not force:
        if not click.confirm("⚠️  A client secret already exists. Importing will overwrite it. Continue?"):
            click.echo("❌ Cancelled")
            return
    
    try:
        if file:
            with open(file, 'r') as f:
                import_json = f.read()
        else:
            click.echo("Paste the exported client secret JSON (Ctrl+D when done):")
            import_json = sys.stdin.read()
        
        import_data = json.loads(import_json)
        
        # Validate format
        if import_data.get("type") != "supercortex_flow_client_secret":
            raise ValueError("Invalid export format")
        
        if import_data.get("version") != "v1":
            raise ValueError("Unsupported export version")
        
        client_secret = import_data.get("secret")
        if not client_secret:
            raise ValueError("Missing secret in export data")
        
        save_client_secret(client_secret)
        
        click.echo("✓ Client secret imported successfully")
        click.echo("  All topic keys and event IDs will now match the source client")
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        click.echo(f"❌ Invalid import data: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"❌ File not found: {file}", err=True)
        sys.exit(1)

@cli.command()
@click.argument('message')
@click.option('-t', '--topic', help='Topic path for event (e.g., logs.errors)')
def add(message, topic):
    """Add an event to the stream"""
    add_event_with_topic(message, topic)

@cli.command()
@click.argument('event_id')
def get(event_id):
    """Get a specific event by ID"""
    try:
        event = make_request("GET", f"/events/{event_id}")
        click.echo(f"Event ID: {event['id']}")
        click.echo(f"Agent: {event['agent_id']}")
        click.echo(f"Timestamp: {event['timestamp']}")
        click.echo(f"Length: {event['body_length']} bytes")
        
        # Show format type
        format_type = event.get('body_format', 'unknown')
        if format_type == 'utf8':
            click.echo(f"Format: UTF-8 text")
            click.echo(f"Body:")
            click.echo(event['body'])
        elif format_type == 'base64':
            click.echo(f"Format: Binary (base64 encoded)")
            click.echo(f"Body (base64):")
            click.echo(event['body'])
        else:
            # Legacy format
            click.echo(f"Body:")
            click.echo(event['body'])
            
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

@cli.command("agent")
@click.argument('subcommand')
def agent_cmd(subcommand):
    """Agent management"""
    if subcommand == "create":
        try:
            result = make_request("POST", "/agents", {})
            click.echo(f"✓ Agent created:")
            click.echo(f"  ID: {result['id']}")
            click.echo(f"  Token: {result['token']}")
            click.echo(f"  Topic keys will be derived from token")
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(f"❌ Unknown agent subcommand: {subcommand}", err=True)

@cli.command("share-topic")
@click.argument('topic_path')
@click.option('--copy', is_flag=True, help='Copy to clipboard (if available)')
def share_topic(topic_path, copy):
    """Generate shareable prefix for a specific topic"""
    config_data = load_config()
    org_id = config_data.get('default_org_id')
    client_secret = load_client_secret()
    
    if not org_id or not client_secret:
        click.echo("❌ No default organization set. Run 'flow config create-org' first", err=True)
        sys.exit(1)
    
    try:
        # Compute the shareable prefix using derived topic key
        prefix = compute_topic_prefix(org_id, topic_path, client_secret)
        
        click.echo(f"✓ Shareable prefix for '{topic_path}':")
        click.echo(f"  {prefix}")
        
        if copy:
            try:
                import pyperclip
                pyperclip.copy(prefix)
                click.echo("✓ Copied to clipboard")
            except ImportError:
                click.echo("❌ Clipboard functionality not available (install pyperclip)")
                
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)

async def watch_with_websocket(prefix_or_topic: str):
    """Watch for events using WebSocket connection for real-time updates"""
    config = load_config()
    token = load_token()
    
    if not token:
        click.echo("❌ Not logged in. Use 'flow login' first", err=True)
        sys.exit(1)
    
    # Determine if this is a topic path or raw hex prefix
    if all(c in '0123456789abcdefABCDEF' for c in prefix_or_topic) and len(prefix_or_topic) >= 16:
        # Raw hex prefix
        prefix = prefix_or_topic.lower()
        display_name = f"prefix {prefix}"
    else:
        # Topic path - compute prefix
        config_data = load_config()
        org_id = config_data.get('default_org_id')
        client_secret = load_client_secret()
        
        if not org_id:
            click.echo("❌ No default organization set. For raw hex prefixes, use full prefix.", err=True)
            click.echo("❌ For topic paths, run 'flow config create-org' first", err=True)
            sys.exit(1)
        
        if not client_secret:
            click.echo("❌ No client secret found. Run 'flow config generate-secret' first", err=True)
            sys.exit(1)
        
        prefix = compute_topic_prefix(org_id, prefix_or_topic, client_secret)
        display_name = f"topic '{prefix_or_topic}'"
    
    # Convert HTTP URL to WebSocket URL
    ws_url = config['base_url'].replace('http://', 'ws://').replace('https://', 'wss://')
    
    # Build WebSocket URL with query parameters
    query_params = urllib.parse.urlencode({
        'prefix': prefix,
        'token': token
    })
    full_ws_url = f"{ws_url}/events/watch_ws?{query_params}"
    
    click.echo(f"👀 Watching for events on {display_name}")
    click.echo("   Connecting via WebSocket for real-time updates... (Ctrl+C to stop)")
    
    try:
        async with websockets.connect(full_ws_url) as websocket:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "connected":
                        click.echo(f"   Connected! Using prefix: {data['prefix_used']}")
                        continue
                    
                    # This is an event
                    event_time = data['timestamp']
                    agent_id = data['agent_id']
                    body_length = data['body_length']
                    event_id = data['id']
                    
                    click.echo(f"🔴 {event_time} | {agent_id} | {body_length} bytes | {event_id}")
                    
                except json.JSONDecodeError:
                    click.echo(f"❌ Invalid message received: {message}", err=True)
                except KeyError as e:
                    click.echo(f"❌ Missing field in message: {e}", err=True)
                    
    except websockets.exceptions.ConnectionClosedError as e:
        click.echo(f"❌ WebSocket connection closed: {e}", err=True)
    except websockets.exceptions.InvalidURI:
        click.echo(f"❌ Invalid WebSocket URL: {full_ws_url}", err=True)
    except Exception as e:
        click.echo(f"❌ WebSocket error: {e}", err=True)

@cli.command()
@click.argument('prefix_or_topic', required=True)
@click.option('--poll', is_flag=True, help='Use polling instead of WebSocket (fallback mode)')
def watch(prefix_or_topic, poll):
    """Watch for new events (topic path or hex prefix)"""
    
    if poll:
        # Use the old polling method as fallback
        watch_with_polling(prefix_or_topic)
    else:
        # Use WebSocket for real-time updates
        try:
            asyncio.run(watch_with_websocket(prefix_or_topic))
        except KeyboardInterrupt:
            click.echo("\n👋 Stopped watching")

def watch_with_polling(prefix_or_topic: str):
    """Original polling implementation (kept as fallback)"""
    config = load_config()
    token = load_token()
    
    # Determine if this is a topic path or raw hex prefix
    if all(c in '0123456789abcdefABCDEF' for c in prefix_or_topic) and len(prefix_or_topic) >= 16:
        # Raw hex prefix
        prefix = prefix_or_topic.lower()
        display_name = f"prefix {prefix}"
    else:
        # Topic path - compute prefix
        config_data = load_config()
        org_id = config_data.get('default_org_id')
        client_secret = load_client_secret()
        
        if not org_id:
            click.echo("❌ No default organization set. For raw hex prefixes, use full prefix.", err=True)
            click.echo("❌ For topic paths, run 'flow config create-org' first", err=True)
            sys.exit(1)
        
        if not client_secret:
            click.echo("❌ No client secret found. Run 'flow config generate-secret' first", err=True)
            sys.exit(1)
        
        prefix = compute_topic_prefix(org_id, prefix_or_topic, client_secret)
        display_name = f"topic '{prefix_or_topic}'"
    
    click.echo(f"👀 Watching for events on {display_name} (polling mode)")
    click.echo("   (Ctrl+C to stop)")
    
    last_timestamp = None
    try:
        while True:
            try:
                params = {
                    'prefix': prefix,
                    'limit': 100
                }
                if last_timestamp:
                    params['since'] = last_timestamp
                
                result = make_request("GET", "/events/watch", params=params)
                
                # Show the prefix from server on first run
                if last_timestamp is None:
                    click.echo(f"   Using prefix: {result['prefix_used']}")
                
                events = result['events']
                
                # Process events in reverse order (oldest first)
                for event in reversed(events):
                    event_time = event['timestamp']
                    if last_timestamp is None or event_time > last_timestamp:
                        click.echo(f"🔴 {event_time} | {event['agent_id']} | {event['body_length']} bytes | {event['id']}")
                        last_timestamp = event_time
                
                # Update timestamp even if no matching events found
                if events:
                    all_timestamps = [event['timestamp'] for event in events]
                    latest = max(all_timestamps)
                    if last_timestamp is None or latest > last_timestamp:
                        last_timestamp = latest
                elif last_timestamp is None:
                    # First run, set timestamp to now
                    last_timestamp = datetime.utcnow().isoformat() + 'Z'
                
                time.sleep(1)  # Poll every second
                
            except KeyboardInterrupt:
                click.echo("\n👋 Stopped watching")
                break
            except Exception as e:
                click.echo(f"❌ Error: {e}", err=True)
                time.sleep(5)  # Wait longer on error
                
    except KeyboardInterrupt:
        click.echo("\n👋 Stopped watching")

async def nc_listen_websocket(prefix_or_topic: str):
    """Netcat-style listen mode using WebSocket - streams raw event bodies to stdout"""
    config = load_config()
    token = load_token()
    
    if not token:
        click.echo("❌ Not logged in. Use 'flow login' first", err=True)
        sys.exit(1)
    
    # Determine if this is a topic path or raw hex prefix
    if all(c in '0123456789abcdefABCDEF' for c in prefix_or_topic) and len(prefix_or_topic) >= 16:
        # Raw hex prefix
        prefix = prefix_or_topic.lower()
    else:
        # Topic path - compute prefix
        config_data = load_config()
        org_id = config_data.get('default_org_id')
        client_secret = load_client_secret()
        
        if not org_id:
            click.echo("# Error: No default organization set", err=True)
            sys.exit(1)
        
        if not client_secret:
            click.echo("# Error: No client secret found", err=True)
            sys.exit(1)
        
        prefix = compute_topic_prefix(org_id, prefix_or_topic, client_secret)
    
    # Convert HTTP URL to WebSocket URL
    ws_url = config['base_url'].replace('http://', 'ws://').replace('https://', 'wss://')
    
    # Build WebSocket URL with query parameters
    query_params = urllib.parse.urlencode({
        'prefix': prefix,
        'token': token
    })
    full_ws_url = f"{ws_url}/events/watch_ws?{query_params}"
    
    try:
        async with websockets.connect(full_ws_url) as websocket:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "connected":
                        # Send connection info to stderr so it doesn't interfere with stdout piping
                        click.echo(f"# Connected to prefix: {data['prefix_used']}", err=True)
                        continue
                    
                    # For nc mode, we need to get the actual event body
                    # The WebSocket only sends metadata, so we need to fetch the full event
                    event_id = data['id']
                    
                    # Fetch the full event to get the body
                    try:
                        event = make_request("GET", f"/events/{event_id}")
                        
                        # Output just the raw body to stdout (perfect for piping)
                        if event.get('body_format') == 'utf8':
                            print(event['body'])
                        elif event.get('body_format') == 'base64':
                            # Decode base64 and output raw bytes
                            import base64
                            raw_bytes = base64.b64decode(event['body'])
                            sys.stdout.buffer.write(raw_bytes)
                            sys.stdout.buffer.write(b'\n')
                        else:
                            # Legacy format - assume UTF-8
                            print(event['body'])
                            
                        sys.stdout.flush()
                        
                    except Exception as e:
                        click.echo(f"# Error fetching event {event_id}: {e}", err=True)
                    
                except json.JSONDecodeError:
                    click.echo(f"# Invalid message received", err=True)
                except KeyError as e:
                    click.echo(f"# Missing field in message: {e}", err=True)
                    
    except websockets.exceptions.ConnectionClosedError as e:
        click.echo(f"# WebSocket connection closed: {e}", err=True)
    except websockets.exceptions.InvalidURI:
        click.echo(f"# Invalid WebSocket URL: {full_ws_url}", err=True)
    except Exception as e:
        click.echo(f"# WebSocket error: {e}", err=True)

@cli.command()
@click.argument('prefix_or_topic', required=True)
@click.option('-l', '--listen', is_flag=True, help='Listen mode - stream event bodies to stdout (netcat-style)')
def nc(prefix_or_topic, listen):
    """Netcat-style event streaming - raw bodies for scripting/piping"""
    
    if listen:
        # Listen mode - stream events to stdout
        try:
            asyncio.run(nc_listen_websocket(prefix_or_topic))
        except KeyboardInterrupt:
            click.echo("\n# Stopped listening", err=True)
    else:
        # Send mode - read from stdin and send as events
        click.echo("# Send mode: Reading from stdin...", err=True)
        click.echo("# (Ctrl+C to stop, Ctrl+D to end input)", err=True)
        
        # Determine topic from argument
        if all(c in '0123456789abcdefABCDEF' for c in prefix_or_topic) and len(prefix_or_topic) >= 16:
            # Raw hex prefix - can't send to specific prefix, would need topic
            click.echo("# Error: Cannot send to raw hex prefix. Use topic path instead.", err=True)
            sys.exit(1)
        
        topic_path = prefix_or_topic
        
        try:
            for line in sys.stdin:
                line = line.rstrip('\n\r')
                if line:  # Skip empty lines
                    try:
                        add_event_with_topic(line, topic_path)
                    except Exception as e:
                        click.echo(f"# Error sending event: {e}", err=True)
        except KeyboardInterrupt:
            click.echo("\n# Stopped sending", err=True)
        except EOFError:
            click.echo("# End of input", err=True)

if __name__ == '__main__':
    cli() 