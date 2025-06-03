#!/usr/bin/env python3
"""
Simple temperature sensor subscriber - equivalent to: flow nc -l sensors.temperature

Prerequisites:
1. Run `flow login` to set up authentication
2. Run `flow config create-org --alias "sensors"` to create an organization
3. Then run this script: python simple_example.py

This will listen for temperature sensor events in real-time.
"""

import asyncio
from supercortex_flow import FlowClient, FlowError, FlowAuthError, FlowConnectionError

async def temperature_listener():
    """Listen to temperature sensor events (equivalent to flow nc -l sensors.temperature)"""
    print("🌡️  Temperature Sensor Listener")
    print("=" * 40)
    print("Listening for temperature events...")
    print("(Press Ctrl+C to stop)")
    print()
    
    try:
        # Load from default config (~/.flow/)
        client = FlowClient.from_config()
        
        async with client:
            # Stream temperature readings in real-time
            async for event in client.stream_topic("sensors.temperature"):
                # Just print the event body (like nc -l does)
                print(event.body)
                
    except FlowAuthError:
        print("❌ Authentication failed!")
        print("   Run: flow login")
        
    except FlowError as e:
        if "Organization ID and client secret required" in str(e):
            print("❌ No organization configured!")
            print("   Run: flow config create-org --alias sensors")
        else:
            print(f"❌ Flow error: {e}")
            
    except FlowConnectionError:
        print("❌ Could not connect to Flow server!")
        print("   Make sure the server is running and accessible")
        
    except FileNotFoundError:
        print("❌ No config found!")
        print("   Run: flow login")
        print("   Then: flow config create-org --alias sensors")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("🚀 SuperCortex Flow - Temperature Sensor Listener")
    print("=" * 50)
    
    # Check if config exists
    try:
        client = FlowClient.from_config()
        config = client.show_config()
        
        if not config['has_token']:
            print("❌ No authentication token found!")
            print("   Run: flow login")
            exit(1)
            
        if not config['org_id']:
            print("❌ No organization configured!")
            print("   Run: flow config create-org --alias sensors")
            exit(1)
            
        print("✅ Configuration looks good!")
        print(f"📡 Server: {config['server']}")
        print(f"🏢 Organization: {config['org_id']}")
        print()
        
    except Exception as e:
        print("❌ Configuration problem:")
        print(f"   {e}")
        print()
        print("🔧 Setup steps:")
        print("   1. flow login")
        print("   2. flow config create-org --alias sensors")
        print("   3. python simple_example.py")
        exit(1)
    
    # Run the listener
    try:
        asyncio.run(temperature_listener())
        
    except KeyboardInterrupt:
        print("\n👋 Stopped listening")
    except Exception as e:
        print(f"\n❌ Error: {e}") 