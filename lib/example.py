#!/usr/bin/env python3
"""
Example usage of the SuperCortex Flow Python library
"""

import asyncio
from supercortex_flow import FlowClient, FlowConfig

def config_loading_example():
    """Example of loading config from standard locations"""
    print("=== Config Loading Example ===")
    
    # Load from standard location (~/.flow/config.json, ~/.flow/token, ~/.flow/client_secret)
    try:
        client = FlowClient.from_config()
        print("✓ Loaded config from standard location")
        print(f"Config: {client.show_config()}")
    except Exception as e:
        print(f"No standard config found: {e}")
    
    # Load from custom path
    try:
        client = FlowClient.from_config("/path/to/custom/config.json")
        print("✓ Loaded config from custom path")
    except Exception as e:
        print(f"Custom config not found: {e}")
    
    # Create and save config
    config = FlowConfig(
        server="http://localhost:2222",
        token="example_token",
        org_id="a7f3d89c2b1e4068",
        client_secret="example_secret"
    )
    
    client = FlowClient(config)
    
    # Add aliases
    client.add_org_alias("my-backend", "a7f3d89c2b1e4068")
    client.add_prefix_alias("backend-errors", "a7f3d89c2b1e40683f8a2b1cd9e7f6a2")
    
    # Save config (will create ~/.flow/ directory and files)
    try:
        client.save_config()
        print("✓ Saved config to standard location")
    except Exception as e:
        print(f"Could not save config: {e}")

def alias_example():
    """Example of using aliases"""
    print("=== Alias Example ===")
    
    config = FlowConfig(
        server="http://localhost:2222",
        token="your_token",
        org_id="a7f3d89c2b1e4068",
        client_secret="your_secret"
    )
    
    client = FlowClient(config)
    
    # Add prefix alias for shared topic
    shared_prefix = client.share_topic("logs.errors")
    client.add_prefix_alias("backend-errors", shared_prefix)
    
    print(f"Added alias 'backend-errors' for prefix: {shared_prefix}")
    
    # Now you can use the alias instead of the long hex prefix
    try:
        events = client.get_history("backend-errors", limit=5)
        print(f"Found {len(events)} events using alias")
    except Exception as e:
        print(f"Could not get history: {e}")
    
    # Watch using alias
    def handle_event(event):
        print(f"Alias event: {event.body}")
    
    try:
        watcher = client.watch_topic("backend-errors", callback=handle_event)
        print("Watching using alias...")
        # watcher.start() - would start watching
    except Exception as e:
        print(f"Could not watch: {e}")

def sync_example():
    """Example of synchronous usage"""
    print("=== Sync Example ===")
    
    # Create client with explicit config
    config = FlowConfig(
        server="http://localhost:2222",
        token="your_token_here",
        org_id="a7f3d89c2b1e4068",
        client_secret="your_client_secret_here"
    )
    
    with FlowClient(config) as client:
        # Send events
        event_id = client.send_event("Database connection failed", topic="logs.errors")
        print(f"Sent event: {event_id}")
        
        # Get history
        events = client.get_history("logs.errors", limit=10)
        print(f"Found {len(events)} events")
        
        # Topic convenience
        topic = client.topic("logs.errors")
        topic.send("Another error message")
        
        # Watch with callback (non-blocking)
        def handle_event(event):
            print(f"Received: {event.body} at {event.timestamp}")
        
        watcher = topic.watch(callback=handle_event)
        watcher.start()
        
        # Do other work...
        import time
        time.sleep(5)
        
        watcher.stop()

async def async_example():
    """Example of asynchronous usage"""
    print("=== Async Example ===")
    
    # Create client
    config = FlowConfig(
        server="http://localhost:2222", 
        token="your_token_here",
        org_id="a7f3d89c2b1e4068",
        client_secret="your_client_secret_here"
    )
    
    async with FlowClient(config) as client:
        # Send events async
        event_id = await client.send_event_async("Async error message", topic="logs.errors")
        print(f"Sent async event: {event_id}")
        
        # Stream events (async generator)
        topic = client.topic("logs.errors")
        
        print("Streaming events for 10 seconds...")
        try:
            async for event in topic.stream():
                print(f"Streamed: {event.body}")
                
                # Break after first event for demo
                break
                
        except Exception as e:
            print(f"Stream error: {e}")

def context_manager_example():
    """Example using context managers"""
    print("=== Context Manager Example ===")
    
    client = FlowClient(server="http://localhost:2222", token="your_token")
    
    # Watch with context manager
    def handle_error(event):
        print(f"Error event: {event.body}")
    
    with client.watch_topic("logs.errors", callback=handle_error):
        print("Watching for 5 seconds...")
        import time
        time.sleep(5)
    
    print("Stopped watching")

def organization_example():
    """Example of organization management"""
    print("=== Organization Example ===")
    
    client = FlowClient(server="http://localhost:2222", token="admin_token")
    
    # Create organization
    org_id = client.create_organization(alias="my-backend")
    print(f"Created organization: {org_id}")
    
    # Now client is configured with this org
    client.send_event("First message", topic="logs.startup")
    
    # Share a topic
    prefix = client.share_topic("logs.errors")
    print(f"Shareable prefix: {prefix}")

def error_handling_example():
    """Example of error handling"""
    print("=== Error Handling Example ===")
    
    from supercortex_flow import FlowAuthError, FlowConnectionError, FlowError
    
    client = FlowClient(server="http://localhost:2222", token="invalid_token")
    
    try:
        client.send_event("This will fail")
    except FlowAuthError:
        print("Authentication failed - invalid token")
    except FlowConnectionError:
        print("Could not connect to server")
    except FlowError as e:
        print(f"Flow error: {e}")

if __name__ == "__main__":
    # Run config examples first
    try:
        config_loading_example()
    except Exception as e:
        print(f"Config loading example failed: {e}")
    
    try:
        alias_example()
    except Exception as e:
        print(f"Alias example failed: {e}")
    
    # Run sync examples
    try:
        sync_example()
    except Exception as e:
        print(f"Sync example failed: {e}")
    
    try:
        context_manager_example()
    except Exception as e:
        print(f"Context manager example failed: {e}")
    
    try:
        organization_example()
    except Exception as e:
        print(f"Organization example failed: {e}")
    
    try:
        error_handling_example()
    except Exception as e:
        print(f"Error handling example failed: {e}")
    
    # Run async example
    try:
        asyncio.run(async_example())
    except Exception as e:
        print(f"Async example failed: {e}") 