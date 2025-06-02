import click
import json
import sys
import os
import requests
import time
import base64
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path.home() / ".flow"
TOKEN_FILE = CONFIG_DIR / "token"
CONFIG_FILE = CONFIG_DIR / "config.json"

def ensure_config_dir():
    CONFIG_DIR.mkdir(exist_ok=True)

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"base_url": "http://localhost:2222"}

def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_token():
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None

def save_token(token):
    ensure_config_dir()
    TOKEN_FILE.write_text(token)
    TOKEN_FILE.chmod(0o600)  # Secure permissions

def parse_prefix(prefix_input: str, format_type: str = 'utf8') -> str:
    """
    Parse prefix input and convert to hex string (up to 8 bytes).
    Used for agent/event creation (no padding).
    """
    if format_type == 'utf8':
        # Convert UTF-8 string to bytes
        prefix_bytes = prefix_input.encode('utf-8')
    elif format_type == 'hex':
        # Parse hex string to bytes
        try:
            # Remove any spaces or common separators
            clean_hex = prefix_input.replace(' ', '').replace('-', '').replace(':', '')
            prefix_bytes = bytes.fromhex(clean_hex)
        except ValueError:
            raise click.ClickException(f"Invalid hex format: {prefix_input}")
    elif format_type == 'base64':
        # Parse base64 string to bytes
        try:
            prefix_bytes = base64.b64decode(prefix_input)
        except Exception:
            raise click.ClickException(f"Invalid base64 format: {prefix_input}")
    else:
        raise click.ClickException(f"Unknown format: {format_type}")
    
    if len(prefix_bytes) > 8:
        raise click.ClickException(f"Prefix too long: {len(prefix_bytes)} bytes (max 8 bytes)")
    
    # Convert to hex string (no padding for agent/event creation)
    return prefix_bytes.hex()

def add_event_with_prefix(message: str, prefix: str = None, format_type: str = 'utf8'):
    """Add an event, optionally with a prefix override."""
    try:
        data = {"body": message}
        if prefix:
            prefix_hex = parse_prefix(prefix, format_type)
            data["prefix_override"] = prefix_hex
            
        result = make_request("POST", "/events", data)
        prefix_info = f" (prefix: {prefix})" if prefix else ""
        click.echo(f"✓ Event added{prefix_info}: {result['id']}")
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
@click.option('-p', '--prefix', help='Prefix for event (UTF-8 by default)')
@click.option('--hex', 'prefix_format', flag_value='hex', help='Interpret prefix as hex')
@click.option('--base64', 'prefix_format', flag_value='base64', help='Interpret prefix as base64')
def cli(ctx, prefix, prefix_format):
    """SuperCortex Flow CLI - Event ingestion system"""
    # If no subcommand is provided, check for stdin input
    if ctx.invoked_subcommand is None:
        # Check if there's stdin data available
        if not sys.stdin.isatty():
            # Read from stdin
            stdin_content = sys.stdin.read().strip()
            if stdin_content:
                format_type = prefix_format or 'utf8'
                add_event_with_prefix(stdin_content, prefix, format_type)
            else:
                click.echo("❌ No input provided", err=True)
                sys.exit(1)
        else:
            # No stdin and no subcommand, show help
            click.echo(ctx.get_help())

@cli.command()
def login():
    """Login with server URL and token"""
    # Prompt for server URL with default
    server_url = click.prompt(
        'Server URL',
        default='http://localhost:2222',
        show_default=True
    ).rstrip('/')
    
    # Prompt for token with no default
    token = click.prompt(
        'Token',
        hide_input=True
    )
    
    # Save both config and token
    config = {"base_url": server_url}
    save_config(config)
    save_token(token)
    
    click.echo(f"✓ Logged in successfully to {server_url}")

@cli.command()
@click.argument('message')
@click.option('-p', '--prefix', help='Prefix for event (UTF-8 by default)')
@click.option('--hex', 'prefix_format', flag_value='hex', help='Interpret prefix as hex')
@click.option('--base64', 'prefix_format', flag_value='base64', help='Interpret prefix as base64')
def add(message, prefix, prefix_format):
    """Add an event to the stream"""
    format_type = prefix_format or 'utf8'
    add_event_with_prefix(message, prefix, format_type)

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
@click.option('--prefix', help='Prefix for agent (UTF-8 by default)')
@click.option('--hex', 'prefix_format', flag_value='hex', help='Interpret prefix as hex')
@click.option('--base64', 'prefix_format', flag_value='base64', help='Interpret prefix as base64')
def agent_cmd(subcommand, prefix, prefix_format):
    """Agent management"""
    if subcommand == "create":
        try:
            data = {}
            if prefix:
                format_type = prefix_format or 'utf8'
                try:
                    prefix_hex = parse_prefix(prefix, format_type)
                    data["prefix"] = prefix_hex
                except click.ClickException as e:
                    click.echo(f"❌ {e}", err=True)
                    sys.exit(1)
            
            result = make_request("POST", "/agents", data)
            click.echo(f"✓ Agent created:")
            click.echo(f"  ID: {result['id']}")
            click.echo(f"  Token: {result['token']}")
            if result.get('prefix'):
                click.echo(f"  Prefix: {result['prefix']}")
        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(f"❌ Unknown agent subcommand: {subcommand}", err=True)

@cli.command()
@click.argument('prefix', required=True)
@click.option('--hex', 'format_type', flag_value='hex', help='Interpret prefix as hex')
@click.option('--base64', 'format_type', flag_value='base64', help='Interpret prefix as base64')
def watch(prefix, format_type):
    """Watch for new events with specific prefix (server enforces 64-bit padding)"""
    
    # Default to UTF-8 if no format specified
    if format_type is None:
        format_type = 'utf8'
    
    click.echo(f"👀 Watching for events with prefix: '{prefix}' ({format_type} format)")
    click.echo("   Server will pad to 64-bits. (Ctrl+C to stop)")
    
    last_timestamp = None
    try:
        while True:
            try:
                # Use server-side filtering endpoint
                params = {
                    'prefix': prefix,
                    'prefix_format': format_type,
                    'limit': 100
                }
                if last_timestamp:
                    params['since'] = last_timestamp
                
                result = make_request("GET", "/events/watch", params=params)
                
                # Show the padded prefix from server on first run
                if last_timestamp is None:
                    click.echo(f"   Padded prefix: {result['prefix_used']}")
                
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

if __name__ == '__main__':
    cli() 