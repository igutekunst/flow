from fastapi import FastAPI, Depends, HTTPException, Header, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from models import Agent, Event, create_tables, get_db, generate_message, generate_id
from pydantic import BaseModel
from typing import Optional, List, Dict, Set
from datetime import datetime
import os
import secrets
import base64
import asyncio
import json
import logging

app = FastAPI(title="SuperCortex Flow", description="Event Ingestion System")

# Validate admin token is set in environment
FLOW_ADMIN_TOKEN = os.getenv("FLOW_ADMIN_TOKEN")
if not FLOW_ADMIN_TOKEN:
    raise ValueError("FLOW_ADMIN_TOKEN must be set in the environment")

# Event broker for WebSocket connections
class EventBroker:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}  # prefix_hex -> [websockets]
        
    async def connect(self, websocket: WebSocket, prefix_hex: str):
        await websocket.accept()
        if prefix_hex not in self.connections:
            self.connections[prefix_hex] = []
        self.connections[prefix_hex].append(websocket)
        
    def disconnect(self, websocket: WebSocket, prefix_hex: str):
        if prefix_hex in self.connections:
            self.connections[prefix_hex].remove(websocket)
            if not self.connections[prefix_hex]:
                del self.connections[prefix_hex]
                
    async def broadcast_event(self, event_data: dict, event_id: str):
        """Broadcast event to all relevant WebSocket connections"""
        disconnected_connections = []
        
        for prefix_hex, websockets in self.connections.items():
            if matches_prefix(event_id, prefix_hex):
                for websocket in websockets[:]:  # Copy list to avoid modification during iteration
                    try:
                        await websocket.send_text(json.dumps(event_data))
                    except Exception as e:
                        logging.warning(f"WebSocket send failed: {e}")
                        disconnected_connections.append((websocket, prefix_hex))
        
        # Clean up disconnected connections
        for websocket, prefix_hex in disconnected_connections:
            self.disconnect(websocket, prefix_hex)

# Global event broker instance
event_broker = EventBroker()

def safe_display_body(body_bytes: bytes) -> dict:
    """
    Smart display logic for binary event bodies.
    Try UTF-8 first, fall back to base64 for display.
    """
    try:
        # Try to decode as UTF-8
        text = body_bytes.decode('utf-8')
        return {
            "body": text,
            "body_format": "utf8",
            "body_length": len(body_bytes)
        }
    except UnicodeDecodeError:
        # Fall back to base64 for display
        return {
            "body": base64.b64encode(body_bytes).decode('ascii'),
            "body_format": "base64",
            "body_length": len(body_bytes)
        }

def parse_prefix_server(prefix_input: str, format_type: str = 'utf8') -> str:
    """
    Server-side prefix parsing with mandatory 64-bit padding.
    This prevents clients from blanket subscribing with short prefixes.
    """
    if format_type == 'utf8':
        prefix_bytes = prefix_input.encode('utf-8')
    elif format_type == 'hex':
        try:
            clean_hex = prefix_input.replace(' ', '').replace('-', '').replace(':', '')
            prefix_bytes = bytes.fromhex(clean_hex)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid hex format")
    elif format_type == 'base64':
        try:
            prefix_bytes = base64.b64decode(prefix_input)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 format")
    else:
        raise HTTPException(status_code=400, detail="Unknown format type")
    
    if len(prefix_bytes) > 8:
        raise HTTPException(status_code=400, detail="Prefix too long (max 8 bytes)")
    
    # MANDATORY 64-bit padding on server side
    padded_bytes = prefix_bytes + b'\x00' * (8 - len(prefix_bytes))
    return padded_bytes.hex()

def matches_prefix(event_id: str, prefix_hex: str) -> bool:
    """Check if event ID starts with the given prefix."""
    return event_id.lower().startswith(prefix_hex.lower())

# Create tables on startup
@app.on_event("startup")
def startup():
    create_tables()

class EventCreate(BaseModel):
    body: str  # We'll encode to bytes on the backend
    prefix_override: Optional[str] = None  # hex-encoded prefix override

class AgentCreate(BaseModel):
    prefix: Optional[str] = None  # hex-encoded prefix bytes

class AgentResponse(BaseModel):
    id: str
    token: str
    prefix: Optional[str] = None

def get_current_agent(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization.replace("Bearer ", "")
    
    # Check if it's the admin token
    if token == FLOW_ADMIN_TOKEN:
        return {"id": "admin", "is_admin": True, "prefix": None}
    
    # Check if it's a valid agent token
    agent = db.query(Agent).filter(Agent.token == token).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return {"id": agent.id, "is_admin": False, "prefix": agent.prefix}

@app.post("/events")
async def create_event(event: EventCreate, current_agent=Depends(get_current_agent), db: Session = Depends(get_db)):
    """Submit an event to the stream"""
    # Determine which prefix to use - override takes precedence
    prefix_to_use = event.prefix_override or current_agent.get("prefix")
    
    prefix_bytes = b''
    if prefix_to_use:
        try:
            prefix_bytes = bytes.fromhex(prefix_to_use)
            # Pad prefix to 64 bits (8 bytes) to match watch behavior
            if len(prefix_bytes) > 8:
                raise HTTPException(status_code=400, detail="Prefix too long (max 8 bytes)")
            prefix_bytes = prefix_bytes + b'\x00' * (8 - len(prefix_bytes))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid prefix format")
    
    # Generate message using the provided format (with binary body)
    body_bytes = event.body.encode('utf-8')
    message = generate_message(body_bytes, prefix_bytes)
    
    new_event = Event(
        id=message["id"],
        agent_id=current_agent["id"],
        timestamp=datetime.fromisoformat(message["timestamp"].replace('Z', '+00:00')),
        body=message["body"]  # This is now raw bytes
    )
    db.add(new_event)
    db.commit()
    
    # Broadcast to WebSocket connections
    event_data = {
        "id": new_event.id,
        "agent_id": new_event.agent_id,
        "timestamp": new_event.timestamp.isoformat() + 'Z',
        "body_length": len(new_event.body) if new_event.body else 0
    }
    await event_broker.broadcast_event(event_data, new_event.id)
    
    return {
        "id": new_event.id,
        "agent_id": new_event.agent_id,
        "timestamp": new_event.timestamp.isoformat() + 'Z'
    }

@app.websocket("/events/watch_ws")
async def websocket_watch_events(
    websocket: WebSocket,
    prefix: str = Query(..., description="Prefix to watch for"),
    prefix_format: str = Query('utf8', description="Format of prefix: utf8, hex, or base64"),
    token: str = Query(..., description="Authorization token")
):
    """WebSocket endpoint for real-time event watching"""
    
    # Authenticate the WebSocket connection
    try:
        # Check if it's the admin token
        if token == FLOW_ADMIN_TOKEN:
            current_agent = {"id": "admin", "is_admin": True, "prefix": None}
        else:
            # Check if it's a valid agent token
            db = next(get_db())
            agent = db.query(Agent).filter(Agent.token == token).first()
            if not agent:
                await websocket.close(code=1008, reason="Invalid token")
                return
            current_agent = {"id": agent.id, "is_admin": False, "prefix": agent.prefix}
    except Exception as e:
        await websocket.close(code=1011, reason="Authentication failed")
        return
    
    # Parse and validate prefix
    try:
        padded_prefix_hex = parse_prefix_server(prefix, prefix_format)
    except HTTPException as e:
        await websocket.close(code=1008, reason=str(e.detail))
        return
    
    # Connect to event broker
    await event_broker.connect(websocket, padded_prefix_hex)
    
    try:
        # Send initial confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "prefix_used": padded_prefix_hex,
            "message": f"Watching for events with prefix: {prefix} (padded to {padded_prefix_hex})"
        }))
        
        # Keep connection alive and handle disconnection
        while True:
            try:
                # Wait for ping/pong or other messages from client
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.ping()
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        event_broker.disconnect(websocket, padded_prefix_hex)

@app.get("/events/watch")
async def watch_events(
    prefix: str = Query(..., description="Prefix to watch for"),
    prefix_format: str = Query('utf8', description="Format of prefix: utf8, hex, or base64"),
    since: Optional[str] = Query(None, description="Return events after this timestamp"),
    limit: int = Query(100, description="Number of events to return"),
    current_agent=Depends(get_current_agent), 
    db: Session = Depends(get_db)
):
    """Watch for events with specific prefix (server-side filtering with mandatory 64-bit padding)"""
    
    # Server-side prefix parsing with mandatory padding
    try:
        padded_prefix_hex = parse_prefix_server(prefix, prefix_format)
    except HTTPException:
        raise
    
    # Build query
    query = db.query(Event).order_by(Event.timestamp.desc())
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.filter(Event.timestamp > since_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Get all events and filter by prefix
    events = query.limit(1000).all()  # Get more events for filtering
    
    # Filter events by prefix
    matching_events = []
    for event in events:
        if matches_prefix(event.id, padded_prefix_hex):
            matching_events.append({
                "id": event.id,
                "agent_id": event.agent_id,
                "timestamp": event.timestamp.isoformat() + 'Z',
                "body_length": len(event.body) if event.body else 0
            })
            
        # Stop if we have enough matching events
        if len(matching_events) >= limit:
            break
    
    return {
        "prefix_used": padded_prefix_hex,
        "events": matching_events
    }

@app.get("/events/{event_id}")
async def get_event(event_id: str, current_agent=Depends(get_current_agent), db: Session = Depends(get_db)):
    """Get a specific event by ID"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Handle both binary data and legacy text data
    if isinstance(event.body, bytes):
        body_info = safe_display_body(event.body)
    else:
        # Legacy text data - convert to bytes first
        legacy_bytes = event.body.encode('utf-8') if isinstance(event.body, str) else event.body
        body_info = safe_display_body(legacy_bytes)
    
    return {
        "id": event.id,
        "agent_id": event.agent_id,
        "timestamp": event.timestamp.isoformat() + 'Z',
        **body_info
    }

@app.post("/agents", response_model=AgentResponse)
async def create_agent(agent_data: AgentCreate, current_agent=Depends(get_current_agent), db: Session = Depends(get_db)):
    """Create a new agent (admin only for now)"""
    if not current_agent.get("is_admin"):
        raise HTTPException(status_code=403, detail="Only admin can create agents")
    
    # Validate prefix if provided
    prefix_bytes = b''
    if agent_data.prefix:
        try:
            prefix_bytes = bytes.fromhex(agent_data.prefix)
            if len(prefix_bytes) > 8:
                raise HTTPException(status_code=400, detail="Prefix too long (max 8 bytes)")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid prefix format (must be hex)")
    
    new_agent = Agent(
        id=generate_id(prefix_bytes),
        token=secrets.token_urlsafe(32),
        created_by=current_agent["id"],
        prefix=agent_data.prefix
    )
    db.add(new_agent)
    db.commit()
    
    return AgentResponse(id=new_agent.id, token=new_agent.token, prefix=new_agent.prefix)

@app.get("/health")
async def health():
    return {"status": "healthy"} 